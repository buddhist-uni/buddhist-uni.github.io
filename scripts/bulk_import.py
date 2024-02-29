#!/bin/python3

from yaspin import yaspin

with yaspin(text="Loading..."):
  from collections import defaultdict
  import argparse
  import re
  import requests
  from tqdm import tqdm
  from tqdm.contrib.concurrent import thread_map as tqdm_thread_map
  from pathlib import Path
  from datetime import datetime

  import json
  from yaml import load as read_yaml

  import gdrive
  from tag_predictor import (
    TagPredictor,
    get_normalized_text_for_youtube_vid,
    get_ytdata_for_ids,
    normalize_text,
    save_normalized_text,
  )
  from pdfutils import readpdf

course_predictor = None

class ItemListParser:
  def __init__(self) -> None:
    pass
  def can_read_item(self, item: str) -> bool:
    return False
  def read_item(self, item: str) -> list[str]:
    """Reads the item and returns a list of addable items"""
    return []

class JSONListParser(ItemListParser):
  def can_read_item(self, item: str) -> bool:
    return item.lower().endswith(".json")
  def read_item(self, item: str) -> list[str]:
    with open(item, 'rt') as fp:
      ret = json.load(fp)
    return ret

class YAMLListParser(ItemListParser):
  def can_read_item(self, item: str) -> bool:
    l = item.lower()
    return l.endswith(".yaml") or l.endswith(".yml")
  def read_item(self, item: str) -> list[str]:
    with open(item, 'rt', encoding='UTF-8') as fp:
      ret = read_yaml(fp)
    return ret

class YouTubePlaylistListParser(ItemListParser):
  def can_read_item(self, item: str) -> bool:
    return (bool)(gdrive.yt_url_to_plid_re.search(item))
  def read_item(self, item: str) -> list[str]:
    plid = gdrive.yt_url_to_plid_re.search(item).groups()[0]
    snippets = gdrive.get_ytvideo_snippets_for_playlist(plid)
    return [
      f"https://youtu.be/{snippet['resourceId']['videoId']}"
      for snippet in snippets
    ]

LIST_PARSERS = [
  YAMLListParser(),
  JSONListParser(),
  YouTubePlaylistListParser(),
]

PRIVATE_FOLDERID_FOR_COURSE = {
  key: gdrive.folderlink_to_id(value['private'])
  for key, value in json.loads(gdrive.FOLDERS_DATA_FILE.read_text()).items()
  if value.get('private')
}

class BulkItemImporter:
  def __init__(self) -> None:
    self.unread_folderid_for_course = dict()
  
  def get_unread_subfolder_name(self) -> str:
    return "⚡ Bulk Importer"

  def can_import_item(self, item: str) -> bool:
    return False

  def import_items(self, items: list[str]):
    # Go ahead and use a tqdm or somesuch to report your progess
    # as makes sense for this importer
    return False

  def get_folder_id_for_course(self, course:str) -> str:
    if course in self.unread_folderid_for_course:
      return self.unread_folderid_for_course[course]
    private_folder = PRIVATE_FOLDERID_FOR_COURSE[course]
    subfolders = gdrive.get_subfolders(private_folder)
    unread_folder = None
    for subfolder in subfolders:
      if 'unread' in subfolder['name'].lower():
        unread_folder = subfolder['id']
        break
    if not unread_folder:
      unread_folder = gdrive.create_folder(f"Unread ({course})", parent_folder=private_folder)
    subfolders = gdrive.get_subfolders(unread_folder)
    for subfolder in subfolders:
      if subfolder['name'] == self.get_unread_subfolder_name():
        self.unread_folderid_for_course[course] = subfolder['id']
        return subfolder['id']
    subfolder = gdrive.create_folder(
      self.get_unread_subfolder_name(),
      parent_folder=unread_folder,
    )
    self.unread_folderid_for_course[course] = subfolder
    return subfolder

class BulkPDFImporter(BulkItemImporter):
  def __init__(self, pdf_type) -> None:
    super().__init__()
    self.pdf_type = pdf_type
    match pdf_type:
      case 'academia.edu':
        self.folder_name = "🏛️ Academia.edu"
      case _:
        raise ValueError("Invalid PDF type: "+pdf_type)

  def get_unread_subfolder_name(self) -> str:
    return self.folder_name
  
  def can_import_item(self, item: str) -> bool:
    return item.lower().endswith('.pdf') \
      and Path(item).is_file() # so far, only support local files
  
  def import_items(self, items: list[str]):
    files = [Path(item) for item in items]
    if self.pdf_type == "academia.edu":
      """Academia.edu PDFs use _s instead of spaces
      Replace them with spaces for my sanity"""
      for fp in list(files):
        name = fp.name
        if "_" in name:
          name = name.replace("_", " ")
          new_name = fp.parent.joinpath(name)
          fp.rename(new_name)
          files.remove(fp)
          files.append(new_name)
    for fp in tqdm(files):
      if gdrive.has_file_already(fp, default=False):
        tqdm.write(f"Skipping {fp} as that file is already on Drive!")
        fp.unlink()
        continue
      text = normalize_text(readpdf(fp, normalize=0))
      name = normalize_text((' '+fp.stem) * 3)
      course = course_predictor.predict([text+name], normalized=True)[0]
      folder = self.get_folder_id_for_course(course)
      uploaded = gdrive.upload_to_google_drive(
        fp,
        folder_id=folder,
        filename=fp.name,
        creator="LibraryUtils.BulkPDFImporter",
        verbose=False,
      )
      if uploaded:
        fp.unlink()
        save_normalized_text(uploaded, text)
      else:
        tqdm.write(f"Failed to upload {fp}!")

class GDocURLImporter(BulkItemImporter):
  def filter_already_imported_items(self, items:list[str]) -> list[str]:
    already = self.already_imported_items(items)
    return [item for item in items if item not in already]
  
  def already_imported_items(self, items:list[str]) -> set[str]:
    print(f"Seeing if we've imported any of these already...")
    files = gdrive.session().files()
    already = set()
    for i in range(0, len(items), 50):
      resp = files.list(
        q=' or '.join([
          f"properties has {{ key='url' and value='{url}' }}"
          for url in items[i:i+50]
        ]),
        pageSize=50,
        fields='files(properties)',
      ).execute()['files']
      for file in resp:
        already.add(file['properties']['url'])
    print(f"Found {len(already)} URLs already added")
    return already

def create_gdoc(url: str, title: str, html: str, folder_id: str):
  return gdrive.create_doc(
    filename=title,
    html=f"<h1>{title}</h1><h2><a href=\"{url}\">{url}</a></h2>{html}",
    custom_properties={
      "createdBy": "LibraryUtils.LinkSaver",
      "url": url,
    },
    folder_id=folder_id,
  )

def get_html(url):
  try:
    return requests.get(url).text
  except:
    tqdm.write(f"WARNING: There was an error fetching {url}! Skipping...")
    return ''

class DharmaSeedURLImporter(GDocURLImporter):
  DOMAIN = 'https://dharmaseed.org'
  MIN_DESC_LEN = 70
  MIN_MINS = 15
  TERM_BLACKLIST = [
    'Q&A',
    'Q & A',
    'Q and A',
    'Q And A',
    'Questions and Answers',
    'Question & Answer',
    'Opening Talk',
    'Conclusion Talk',
    ' Retreat '
    ' Part ',
    'PART',
    ' #',
  ]

  def get_unread_subfolder_name(self) -> str:
    return "🌱 Dharma Seed"

  def can_import_item(self, item: str) -> bool:
    # for now we only support importing teacher pages
    return item.startswith(self.DOMAIN + "/teacher/")

  def import_items(self, items: list[str]):
    from bs4 import BeautifulSoup
    tqdm.write("Getting first teacher pages...")
    single_page_urls = []
    all_pages_urls = []
    for url in items:
      if '?' in url:
        single_page_urls.append(url)
      else:
        all_pages_urls.append(url)
    htmls = tqdm_thread_map(
      get_html,
      [
        url+'?page=1&page_items=100'
        for url in all_pages_urls
      ] + single_page_urls,
      max_workers=min(len(items), 8)
    )
    further_items = []
    for i in range(len(all_pages_urls)):
      html = htmls[i]
      if not html:
        continue
      url = all_pages_urls[i]
      soup = BeautifulSoup(html, features='lxml')
      paginator = soup.find('div', class_="paginator")
      if not paginator:
        continue
      pages = paginator.find_all('a', class_="page")
      # a bit hacky but it works for now
      further_items.extend([
        url + l.attrs['href'] for l in pages
      ])
    if len(further_items) > 0:
      tqdm.write("Getting the rest of the pages...")
      htmls.extend(tqdm_thread_map(get_html, further_items, max_workers=min(len(further_items), 8)))
    tqdm.write("Importing items from pages...")
    for html in tqdm(htmls):
      if html:
        self._import_item(html)

  def _import_item(self, html: str):
    """Takes a teacher page and saves a gdoc for each talk.
    
    Filters out talks that are:
      - retreats
      - unavailable
      - undescribed (desc < self.MIN_DESC_LEN)
      - longer than 2 hours
      - shorter than self.MIN_MINS
      - "Q&A" (or other self.TERM_BLACKLIST terms)
    
    This function aggressively asserts that values are as expected, so that
    if the parser ever gets a page structured differently, you'll know.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, features='lxml')
    teacher_name = soup.select_one('a.talkteacher b').get_text()
    talks = soup.select("div.talklist > table")
    if len(talks) < 1:
      raise AssertionError(f"Failed to find at least 1 talk on {teacher_name}'s page")
    tracks = []
    for talk in talks:
      tds = talk.find('table').find_all('td')
      if len(tds) < 3:
        continue
      unavailable = bool(tds[1].find('i'))
      button_count = len(tds[1].find_all('a'))
      if button_count == 3: # this is a retreat
        continue
      assert unavailable != (button_count == 2)
      if unavailable:
        continue
      track = dict()
      track['duration'] = tds[0].find('i').get_text().strip()
      timeparts = track['duration'].split(':')
      assert len(timeparts) in [2, 3]
      if len(timeparts) == 2 and int(timeparts[0]) < self.MIN_MINS:
        continue
      if len(timeparts) == 3 and int(timeparts[0]) > 1:
        continue
      desc = talk.find('div', class_="talk-description")
      if desc:
        track['desc'] = re.sub(r'\(.{4,60}\)', '', desc.get_text().strip())
      else:
        continue
      if len(track['desc']) < self.MIN_DESC_LEN:
        continue
      link = tds[0].contents[1]
      assert link.name == 'a'
      track['title'] = link.get_text().strip()
      if any(
        needle in track['title'] or needle in track['desc']
        for needle in self.TERM_BLACKLIST
      ):
        continue
      track['date'] = tds[0].contents[0].strip()
      # This will raise a ValueError if the date is invalid
      datetime.strptime(track['date'], '%Y-%m-%d')
      track['url'] = self.DOMAIN + link.attrs['href']
      tracks.append(track)
    if len(tracks) == 0:
      return
    already = self.already_imported_items([d['url'] for d in tracks])
    tracks = [d for d in tracks if d['url'] not in already]
    if len(tracks) == 0:
      return
    for track in tqdm(tracks, desc="Predicting courses"):
      text = [track['title']] * 3
      text.append(track['desc'])
      text = ' '.join(text)
      track['course'] = course_predictor.predict([text])[0]
      track['folder'] = self.get_folder_id_for_course(track['course'])
    for track in tqdm(tracks, desc="Uploading"):
      create_gdoc(
        url=track['url'],
        title=f"{track['title']} ({track['date']}) - {teacher_name}",
        html=f"""<h2>Duration</h2><p>{track['duration']}</p>
          <h2>Description (from DharmaSeed)</h2><p>{track['desc']}</p>""",
        folder_id=track['folder'],
      )


"""
INSTRUCTIONS FOR IMPORTING THE WATCH LATER PLAYLIST
---------------------------------------------------

Scroll through the whole list so it's all in memory.
Then run:
```js
var videos = document.querySelectorAll('.yt-simple-endpoint.style-scope.ytd-playlist-video-renderer');
var r = [];
var json = [];

r.forEach.call(videos, function(video) {
	var url = 'https://www.youtube.com' + video.getAttribute('href');
	url = url.split('&list=WL&index=');
	url = url[0];
	json.push(url);
});
console.log(json)
```
Copy object and paste to a .json file

Then clear the playlist via:
```js
setInterval(() => {
    document.querySelector('#contents > ytd-playlist-video-renderer:nth-child(1) #button').click();
}, 2000)
// A second later, pasting in:
setInterval(() => {
    document.querySelector('#items > ytd-menu-service-item-renderer:nth-child(3)').click();
}, 2000)
```

Note: the above may need to be updated slightly based on the latest YT HTML
"""

def create_gdoc_for_yt_snippet(snippet: dict):
  html = gdrive._make_ytvideo_summary_html(
    snippet['id'],
    snippet,
    snippet['transcript'],
  )
  return create_gdoc(
    f"https://youtu.be/{snippet['id']}",
    snippet['title'],
    html,
    snippet['folder'],
  )

class BulkYouTubeVideoImporter(GDocURLImporter):
  def get_unread_subfolder_name(self) -> str:
    return "📼 YouTube Videos"

  def can_import_item(self, item: str) -> bool:
    return (bool)(gdrive.yt_url_to_id_re.search(item))

  def import_items(self, items: list[str]):
    vid_ids = [
      gdrive.yt_url_to_id_re.search(item).groups()[0]
      for item in items
    ]
    # dedupe based on normalized video id
    items = self.filter_already_imported_items([
      f"https://youtu.be/{vid}" for vid in vid_ids
    ])
    if len(items) == 0:
      return
    vid_ids = [
      gdrive.yt_url_to_id_re.search(item).groups()[0]
      for item in items
    ]
    print("Getting all video data...")
    snippets = get_ytdata_for_ids(vid_ids)
    print("Predicting courses for videos...")
    for snippet in tqdm(snippets):
      course = course_predictor.predict(
        [get_normalized_text_for_youtube_vid(snippet)],
        normalized=True,
      )[0]
      snippet['folder'] = self.get_folder_id_for_course(course)
    print("Creating GDocs for Videos...")
    # TODO Figure out how to parallelize this
    for snippet in tqdm(snippets):
      create_gdoc_for_yt_snippet(snippet)

ITEM_IMPORTERS = [
  ('YouTube Videos', BulkYouTubeVideoImporter()),
  ('DharmaSeed Talks', DharmaSeedURLImporter()),
]
IMPORTERS = {k: v for k, v in ITEM_IMPORTERS}

def import_items(items: list[str], pdf_type=None):
  if pdf_type:
    pdf_importer = BulkPDFImporter(pdf_type)
    ITEM_IMPORTERS.append(('PDFs', pdf_importer))
    IMPORTERS['PDFs'] = pdf_importer
  grouped_items = defaultdict(list)
  for item in items:
    has_match = False
    for iname, importer in ITEM_IMPORTERS:
      if importer.can_import_item(item):
        grouped_items[iname].append(item)
        has_match = True
        break
    if not has_match:
      print(f"Warning! No importer found for \"{item}\"!")
      if item.lower().endswith('.pdf') and not pdf_type:
        print(f"You need to specify a \"pdf type\" to import PDFs!")
  for k in grouped_items:
    items = grouped_items[k]
    if len(items) <= 50:
      print(f"Importing {len(items)} {k}...")
      IMPORTERS[k].import_items(items)
    else:
      print(f"Importing {len(items)} {k} in batches of 50...")
      for j in range(0, len(items), 50):
        print(f"Batch {j+1}->{j+50} of {len(items)} {k}...")
        IMPORTERS[k].import_items(items[j:j+50])


if __name__ == "__main__":
  argparser = argparse.ArgumentParser(
    prog="python3 bulk_import.py",
    description="Upload many unread items to Google Drive at once",
    formatter_class=argparse.RawTextHelpFormatter,
  )
  argparser.add_argument(
    "items",
    nargs="+",
    help="""The items (or source of the items) to upload.
These items can be:
  - A YouTube Video Link
  - A YouTube Playlist Link (each video added seperately)
  - A YAML or JSON file containing a list of any of the above
""")
  argparser.add_argument(
    '--pdf-type',
    dest="pdf_type",
    nargs="?",
    choices=['academia.edu'],
    help="Which subfolder to sort PDFs into (required if importing PDFs)",
  )
  args = argparser.parse_args()
  with yaspin(text="Loading tag predictor..."):
    course_predictor = TagPredictor.load()
  raw_items = []
  with yaspin(text="Parsing items..."):
    for item in args.items:
      sublist = []
      for parser in LIST_PARSERS:
        if parser.can_read_item(item):
          sublist = parser.read_item(item)
          break
      if sublist:
        raw_items.extend(sublist)
      else:
        raw_items.append(item)
  print(f"Got {len(raw_items)} items to import.")
  import_items(raw_items, pdf_type=args.pdf_type)
  
