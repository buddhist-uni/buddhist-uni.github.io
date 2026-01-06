import requests, os, re, argparse, time, subprocess, json
from pathlib import Path
from strutils import (
  git_root_folder,
  input_with_prefill,
  prompt,
  system_open,
  sutta_id_re
)
from add_external_descriptions import get_blurb_for_suttaid
from parallels import get_parallels_yaml
from gdrive_base import (
  upload_to_google_drive,
  DRIVE_LINK,
  share_drive_file_with_everyone,
  create_drive_shortcut,
)
from gdrive import (
  get_gfolders_for_course,
  input_course_string_with_tab_complete,
)
from archivedotorg import save_url_to_archiveorg
from pdfutils import readpdf, get_page_count
from tag_predictor import TagPredictor

yaml_list_prefix = '\n  - '
NONSC_TRANSLATORS = [{
  'author_short': 'Gnanananda',
  'author_uid': '"Ven. Kiribathgoda Gnanananda"',
  'author': "Ven. Gnanananda",
  'publication_date': 2020,
  'website_data': json.loads(git_root_folder.joinpath("_data", "suttafriends.json").read_text())
},
{
  'author_short': 'DT.org',
  'author_uid': 'geoff',
  'author': "Thanissaro Bhikkhu",
  'publication_date': None,
  'website_data': json.loads(git_root_folder.joinpath("_data", "dhammatalks.json").read_text())
},
{
  'author_short': 'ATI',
  'author_uid': None,
  'author': None,
  'publication_date': None,
  'website_data': json.loads(git_root_folder.joinpath("_data", "accesstoinsight_nongeoffsuttas.json").read_text())
}
]

def make_nonsc_url(website, book, nums):
  url = ""
  if website['constants']['rootUrl'] == "https://accesstoinsight.org":
    book = website[book]['available']
    if type(book) is dict:
      book = book[str(nums[0])]
      num = nums[1]
    else:
      num = nums[0]
    url = next(e[1] for e in book if e[0] == num)
    url = f"{website['constants']['rootUrl']}{url}"
  else:
    url = f"{website['constants']['rootUrl']}{website[book]['links']['all']}{website['constants']['chapterConnector'].join(map(str,filter(None,nums)))}{website['constants']['suffixUrl']}"
  print("Testing nonSC URL to make sure it's legit...")
  try:
    resp = requests.head(url)
    if resp.ok:
      print("Looks good!")
    else:
      raise Exception
  except:
    print(f"ERROR: Constructed unGETable url \"{url}\"")
    quit(1)
  return url

def command_line_args():
    parser = argparse.ArgumentParser(
      description="Takes a sutta PDF and does the preliminary work of ingesting it into OBU.",
      epilog="",
      formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-s", "--source",
      help="The PDF file *or* the folder containing the PDF file(s) to injest.",
      type=Path, default=Path('../../Download/'))
    return parser.parse_args()

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
  if type(book) is dict or type(book[0]) is int:
    return int(nums[1]) in book
  return int(nums[1]) in list(map(lambda e: int(e[0]), book))

def get_possible_trans(book, nums):
  return list(filter(lambda t: is_in_website(t['website_data'], book, nums), NONSC_TRANSLATORS))

def year_from_ati_data(text):
    m = re.search(r"\[SOURCE_COPYRIGHT_YEAR\]=\{([12][90][0-9][0-9])\}", text)
    if not m:
      m = re.search(r"\[ATI_YEAR\]=\{([12][90][0-9][0-9])\}", text)
    if not m:
      print(f"ERROR: Couldn't find YEAR metadata")
      quit(1)
    print(f"Got year: {m.groups(0)[0]}")
    return m.groups(0)[0]

def fill_in_trans_data(trans, url):
  # geoff year will be filled in later by source url (below)
  if not trans['author_short']=='ATI':
    return trans
  m = re.search(r"\.([a-z]+)\.html$", url)
  if not m:
    print(f"ERROR: Badly formatted ATI link {url}")
    quit(1)
  match m.groups(0)[0]:
    case "irel":
      trans['author_uid'] = "ireland"
      trans['author'] = "John D. Ireland"
      trans['author_short'] = "ATI (Ireland)"
    case 'piya':
      trans['author_uid'] = '"Piyadassi Thera"'
      trans['author'] = "Piyadassi Thera"
      trans['author_short'] = "ATI (Piya)"
    case _:
      print(f"ERROR: Unknown author '{m.groups(0)[0]}'")
      quit(1)
  resp = requests.get(url)
  if not resp.ok or resp.text.find("<title>Lost in samsara</title>") >= 0:
      print(f"ERROR: ATI request failed unexpectedly with status {resp.status_code}")
      quit(1)
  trans["publication_date"] = year_from_ati_data(resp.text)
  return trans

def get_geoff_source_url(trans, dturl, book, nums):
  url = get_possible_geoff_source_url(trans, book, nums)
  if url == "":
    return ""
  if not trans['publication_date']:
    # fetch url to pull pub data
    print("Trying to fetch ATI version for year...")
    resp = requests.get(url)
    if not resp.ok:
      print(f"ERROR: Request failed unexpectedly with status {resp.status_code}")
      quit(1)
    if resp.text.find("<title>Lost in samsara</title>") >= 0:
      print("ATI doesn't seem to have this sutta. Oh well.")
      print("Trying the Wayback Machine...")
      resp = requests.head("http://web.archive.org/web/1970/"+dturl)
      if resp.ok and '/save/' not in resp.headers.get('location'):
        m = re.search(r" at ([12][90][0-9][0-9])", resp.headers['x-archive-redirect-reason'])
        if not m:
          print("Got unexpected Archive.org response:\n\t"+resp.headers['x-archive-redirect-reason'])
          quit(1)
        print("Got year: "+m.groups(0)[0])
        trans['publication_date'] = f"{m.groups(0)[0]} # or earlier"
      else:
        print("Seems to have not been saved!")
        save_url_to_archiveorg(dturl)
      return ""
    trans['publication_date'] = year_from_ati_data(resp.text)
  return f"\nsource_url: \"{url}\""

def get_possible_geoff_source_url(trans, book, nums):
  ret = ""
  match book:
    case "dn":
      ret = f"dn/dn.{nums[0]:02d}.0.than.html"
    case "mn":
      ret = f"mn/mn.{nums[0]:03d}.than.html"
    case "sn":
      ret = f"sn/sn{nums[0]:02d}/sn{nums[0]:02d}.{nums[1]:03d}.than.html"
    case "an":
      ret = f"an/an{nums[0]:02d}/an{nums[0]:02d}.{nums[1]:03d}.than.html"
    case "ud":
      trans['publication_date'] = 2012
      ret = f"kn/ud/ud.{nums[0]}.{nums[1]:02d}.than.html"
    case "snp":
      ret = f"kn/snp/snp.{nums[0]}.{nums[1]:02d}.than.html"
    case "thag":
      ret = f"kn/thag/thag.{nums[0]:02d}.{nums[1]:02d}.than.html"
    case "thig":
      ret = f"kn/thig/thig.{nums[0]:02d}.{nums[1]:02d}.than.html"
    case "iti":
      trans['publication_date'] = 2001
      num = int(nums[0])
      ret = "kn/iti/iti."
      if num <= 27:
        ret += f"1.001-027.than.html#iti-{num:03d}"
      elif num <= 49:
        ret += f"2.028-049.than.html#iti-0{num}"
      elif num <= 99:
        ret += f"3.050-099.than.html#iti-0{num}"
      else:
        ret += f"4.100-112.than.html#iti-{num}"
    case _:
      print(f"WARNING: Haven't implemented Geoff logic for {book} yet! :(")
      return ""
  if ret == "":
    return ""
  return "https://accesstoinsight.org/tipitaka/" + ret

def process_pdf(pdf_file):
  print(f"Processing {pdf_file}...")
  pdf_file = Path(pdf_file)
  pages = get_page_count(pdf_file)
  pdf_text = readpdf(pdf_file)
  guess = guess_id_from_filename(pdf_file.stem)
  while True:
    sutta = input_with_prefill("Sutta ID? ", guess)
    scdata = get_suttacentral_metadata(sutta)
    if scdata and scdata['acronym'] and scdata['acronym'].replace('–','-') == sutta:
      break
    print(f"Got \"{scdata['acronym']}\" instead. Try again.")
  en_trans = [t for t in scdata['translations'] if t['lang']=='en']
  slug = scdata['uid']
  mdfile = git_root_folder.joinpath("_content", "canon", f"{slug}.md")
  if mdfile.exists():
    if not prompt("File already exists! Continue anyway?"):
      return
  blurb = get_blurb_for_suttaid(slug) or ''
  course = TagPredictor.load().predict([blurb + ' ' + pdf_text])[0]
  parsed = sutta_id_re.match(slug)
  book = parsed.group(1)
  nums = [parsed.group(2), parsed.group(3)]
  try:
    nums = list(map(lambda v: int(v) if v else None, nums))
    nonsc_trans = get_possible_trans(book, nums)
  except ValueError:
    nonsc_trans = [] # TODO: look up range suttas correctly
  print(f"Possible English translations: {list(map(lambda t: t['author_short'], en_trans+nonsc_trans))}")
  transidx = int(input_with_prefill("Which one is this [index]? ", "0", validator=lambda x: int(x)<len(en_trans)+len(nonsc_trans)))
  if transidx < len(en_trans):
    trans = en_trans[transidx]
    external_url = f"https://suttacentral.net/{slug}/en/{trans['author_uid']}"
  transidx -= len(en_trans)
  if transidx >= 0:
    trans = nonsc_trans[transidx]
    external_url = make_nonsc_url(trans['website_data'], book, nums)
    trans = fill_in_trans_data(trans, external_url)
  print(f"Going with {trans['author_short']}")
  pali_name = input_with_prefill("Pāli name? ", scdata['original_title'].replace("sutta", " Sutta").replace("aa", "a A").strip())
  eng_name = input_with_prefill("English title? ", scdata['translated_title'].strip())
  title = f"{sutta} {pali_name}{': '+eng_name if eng_name else ''}"
  filename = f"{title.replace(':','_')} - {trans['author']}.pdf"
  course = input_course_string_with_tab_complete(prefill=course)
  folder_id, shortcut_folder = get_gfolders_for_course(course)
  needs_sharing = False
  if shortcut_folder and not folder_id:
    folder_id = shortcut_folder
    shortcut_folder = None
    needs_sharing = True
  slugfield = slug
  extra_fields = ""
  if trans['author_uid'] == 'geoff':
    extra_fields = get_geoff_source_url(trans, external_url, book, nums)
  if book in ['sn', 'iti', 'snp', 'thig', 'thag', 'ud']:
    if prompt("Is this poetry?", "n"):
      extra_fields = f"""
subcat: poetry{extra_fields}"""
    print("Alright")
  match book:
    case "dn":
      slugfield = f"dn{nums[0]:02d}"
    case "mn":
      slugfield = f"mn{nums[0]:03d}"
    case "ma":
      slugfield = f"ma{nums[0]:03d}"
    case "sn":
      try:
        slugfield = f"sn.{nums[0]:03d}.{nums[1]:03d}"
      except ValueError: # Range sutta
        slugfield = f"sn.{int(nums[0]):03d}.{int(nums[1].split('-')[0]):03d}-{int(nums[1].split('-')[1]):03d}"
    case "an":
      try:
        slugfield = f"an.{nums[0]:03d}.{nums[1]:03d}"
      except ValueError:
        slugfield = f"an.{int(nums[0]):03d}.{int(nums[1].split('-')[0]):03d}-{int(nums[1].split('-')[1]):03d}"
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
    case "kp":
      slugfield = f"khp{nums[0]}"
    case _:
      print(f"Haven't yet implemented slug logic for {book}")
      quit(1)
  year = trans['publication_date']
  if not year:
    if trans['author_uid'] == 'sujato':
      year = "2018"
    else:
      year = input_with_prefill("year: ", "2010 # a wild guess")
  if not pages:
    pages = input("pages: ")
  parallels = get_parallels_yaml(scdata['uid'])
  if parallels:
    parallels += "\n"
  print(f"Attempting to upload \"{filename}\" to Google Drive...")
  author = trans['author_uid'].replace('thanissaro','geoff').replace('-thera','').replace('mills','mills-laurence')
  filegid = upload_to_google_drive(
    pdf_file,
    creator='LibraryUtils.SuttaUploader',
    custom_properties={'sutta':sutta,'slug':slugfield,'translator':author},
    filename=filename,
    folder_id=folder_id,
  )
  if not filegid:
    print("Failed to upload!")
    quit(1)
  if needs_sharing:
    print("Sharing the file publicly...")
    share_drive_file_with_everyone(filegid)
  drive_link = DRIVE_LINK.format(filegid)
  if shortcut_folder:
    print("Creating the private shortcut...")
    shortcutid = create_drive_shortcut(filegid, filename, shortcut_folder)
    if not shortcutid:
      print("Warning! Failed to create the shortcut")
  title = title.replace('"', '\\"')
  coursefields = ""
  if course:
    coursefields = f"""course: {course}
status: featured
"""
  blurb = f"\n\n{blurb}\n<!---->" if blurb else ""
  mdfile.write_text(f"""---
title: "{title}"
translator: {author}
slug: "{slugfield}"{extra_fields}
external_url: "{external_url}"
drive_links:
  - "{drive_link}"
{coursefields}tags:
  - 
  - {book}
year: {year}
pages: {pages}
{parallels}---

> {blurb}
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
