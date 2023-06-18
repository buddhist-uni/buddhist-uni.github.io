import requests, os, re, argparse, time, subprocess, json
from pathlib import Path
from strutils import input_with_prefill, prompt, system_open
from gdrive import upload_to_google_drive, get_gfolders_for_course, create_drive_shortcut, DRIVE_LINK

sutta_id_re = r'^([a-zA-Z]+)(\d+)[\.]?(\d*)$'
NONSC_TRANSLATORS = [{
  'author_short': 'Gnanananda',
  'author_uid': '"Ven. Kiribathgoda Gnanananda"',
  'author': "Ven. Gnanananda",
  'publication_date': 2020,
  'website_data': json.loads(Path(os.path.normpath(os.path.join(os.path.dirname(__file__), "../_data/suttafriends.json"))).read_text())
},
{
  'author_short': 'Thanissaro',
  'author_uid': 'geoff',
  'author': "Thanissaro Bhikkhu",
  'publication_date': "2009 # fake news!",
  'website_data': json.loads(Path(os.path.normpath(os.path.join(os.path.dirname(__file__), "../_data/dhammatalks.json"))).read_text())
}
]

def make_nonsc_url(website, book, nums):
  return f"{website['constants']['rootUrl']}{website[book]['links']['all']}{website['constants']['chapterConnector'].join(map(str,filter(None,nums)))}{website['constants']['suffixUrl']}"

def command_line_args():
    parser = argparse.ArgumentParser(
      description="Takes a sutta PDF and does the preliminary work of ingesting it into OBU.",
      epilog="",
      formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-s", "--source",
      help="The PDF file *or* the folder containing the PDF file(s) to injest.",
      type=Path, default=Path('../../Download/'))
    parser.add_argument("--client",
      help="The Google Drive Authorized Cloud App json secrets file.",
      type=Path, default=Path("~/library-utils-client-secret.json"))
    return parser.parse_args()

def get_page_count(pdf_path):
    try:
        result = subprocess.run(['exiftool', '-n', '-p', '$PageCount', str(pdf_path)], capture_output=True, text=True)
        page_count = int(result.stdout.strip())
        return page_count
    except:
        return None

def get_new_pdfs(directory):
    ret = []
    files = set(os.listdir(directory))
    while True:
        time.sleep(2)  # Adjust the interval (in seconds) between checks as desired
        new_files = set(os.listdir(directory))
        added_files = new_files - files
        for file in added_files:
            if file.lower().endswith('.pdf'):
                ret.append(Path(directory)/file)
        if ret:
            return ret
        files = new_files

def get_suttacentral_metadata(sutta):
  ret = requests.get(f"https://suttacentral.net/api/suttaplex/{sutta.lower().replace(' ','')}?language=en")
  return json.loads(ret.text)[0]

def guess_id_from_filename(name):
  # Iti 8_ Foobar baz -> Iti 8
  if "_" in name:
    return name.split("_")[0]
  # AN 8 -> AN 8.(?)
  return name+'.'

def is_in_website(website, book, nums):
  if not book in website:
    return False
  book = website[book]
  if "complete" in book and book["complete"]:
    return True
  if not "available" in book:
    return False
  book = book["available"]
  if not int(nums[0]) in book and not str(nums[0]) in book:
    return False
  if not nums[1]:
    return True
  book = book[str(nums[0])]
  return int(nums[1]) in book

def get_possible_trans(book, nums):
  return list(filter(lambda t: is_in_website(t['website_data'], book, nums), NONSC_TRANSLATORS))

def process_pdf(pdf_file):
  print(f"Processing {pdf_file}...")
  pdf_file = Path(pdf_file)
  pages = get_page_count(pdf_file)
  guess = guess_id_from_filename(pdf_file.stem)
  while True:
    sutta = input_with_prefill("Sutta ID? ", guess)
    scdata = get_suttacentral_metadata(sutta)
    if scdata['acronym'] == sutta:
      break
    print(f"Got \"{scdata['acronym']}\" instead. Try again.")
  en_trans = [t for t in scdata['translations'] if t['lang']=='en']
  slug = scdata['uid']
  mdfile = Path(os.path.normpath(os.path.join(os.path.dirname(__file__), f"../_content/canon/{slug}.md")))
  if mdfile.exists():
    if not prompt("File already exists! Continue anyway?"):
      return
  parsed = re.match(sutta_id_re, slug)
  book = parsed.group(1)
  nums = [parsed.group(2), parsed.group(3)]
  nums = list(map(lambda v: int(v) if v else None, nums))
  nonsc_trans = get_possible_trans(book, nums)
  print(f"Possible English translations: {list(map(lambda t: t['author_short'], en_trans+nonsc_trans))}")
  transidx = int(input_with_prefill("Which one is this [index]? ", "0", validator=lambda x: int(x)<len(en_trans)+len(nonsc_trans)))
  if transidx < len(en_trans):
    trans = en_trans[transidx]
  transidx -= len(en_trans)
  if transidx >= 0:
    trans = nonsc_trans[transidx]
  print(f"Going with {trans['author_short']}")
  pali_name = input_with_prefill("Pāli name? ", scdata['original_title'].replace("sutta", " Sutta").strip())
  eng_name = input_with_prefill("English title? ", scdata['translated_title'].strip())
  title = f"{sutta} {pali_name}: {eng_name}"
  filename = f"{title.replace(':','_')} - {trans['author']}.pdf"
  course = input("course: ")
  folder_id, shortcut_folder = get_gfolders_for_course(course)
  drive_links = "drive_links"
  if shortcut_folder and not folder_id:
    folder_id = shortcut_folder
    shortcut_folder = None
    drive_links = "hidden_links"
  slugfield = slug
  extra_fields = ""
  if book in ['sn', 'iti', 'snp', 'thig', 'thag', 'ud']:
    if prompt("Is this poetry?", "n"):
      extra_fields = f"""
subcat: poetry{extra_fields}"""
  match book:
    case "dn":
      slugfield = f"dn{nums[0]:02d}"
    case "mn":
      slugfield = f"mn{nums[0]:03d}"
    case "ma":
      slugfield = f"ma{nums[0]:03d}"
    case "sn":
      slugfield = f"sn.{nums[0]:03d}.{nums[1]:03d}"
    case "an":
      slugfield = f"an.{nums[0]:03d}.{nums[1]:03d}"
    case "ud":
      slugfield = slug
    case "vv":
      slugfield = f"vv.{nums[0]}.{nums[1]:02d}"
    case "snp":
      slugfield = f"snp.{nums[0]}.{nums[1]:02d}"
    case "thig":
      slugfield = f"thig.{nums[0]:02d}.{nums[1]:02d}"
    case "thag":
      slugfield = f"thag.{nums[0]:02d}.{nums[1]:02d}"
    case "pv":
      slugfield = f"pv{nums[0]}.{nums[1]:02d}"
    case "iti":
      slugfield = f"iti{nums[0]:03d}"
    case _:
      print(f"Haven't yet implemented slug logic for {book}")
      quit(1)
  if transidx < 0:
    external_url = f"https://suttacentral.net/{slug}/en/{trans['author_uid']}"
  else:
    external_url = make_nonsc_url(trans['website_data'], book, nums)
  year = trans['publication_date']
  if not year:
    if trans['author_uid'] == 'sujato':
      year = "2018"
    else:
      year = input_with_prefill("year: ", "19")
  if not pages:
    pages = input("pages: ")
  print(f"Attempting to upload \"{filename}\" to Google Drive...")
  filegid = upload_to_google_drive(pdf_file, args.client, filename=filename, folder_id=folder_id)
  if not filegid:
    print("Failed to upload!")
    quit(1)
  drive_link = DRIVE_LINK.format(filegid)
  if shortcut_folder:
    print("Creating the private shortcut...")
    shortcutid = create_drive_shortcut(args.client, filegid, filename, shortcut_folder)
    if not shortcutid:
      print("Warning! Failed to create the shortcut")
  title = title.replace('"', '\\"')
  mdfile.write_text(f"""---
title: "{title}"
translator: {trans['author_uid'].replace('thanissaro','geoff')}
slug: "{slugfield}"{extra_fields}
external_url: "{external_url}"
{drive_links}:
  - "{drive_link}"
course: {course}
tags:
  - 
  - {book}
year: {year}
pages: {pages}
---

> 
""")
  system_open(mdfile)
  pdf_file.unlink()

if __name__ == "__main__":
  global args 
  args = command_line_args()
  if not args.source.exists():
    print(f"{args.source} doesn't exist")
    quit(1)
  pdfs = []
  if args.source.is_file():
    pdfs = [args.source]
  else:
    if not args.source.is_dir():
      print(f"What kind of file is that??")
      quit(1)
    for child in args.source.iterdir():
      if child.is_file() and child.suffix.lower() == ".pdf":
        pdfs.append(child)
    if not pdfs:
      print("No PDF found. Waiting for one...")
      pdfs = get_new_pdfs(args.source)
  for pdf in pdfs:
    process_pdf(pdf)
