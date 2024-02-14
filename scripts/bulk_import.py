#!/bin/python3

from yaspin import yaspin

with yaspin(text="Loading..."):
  from collections import defaultdict
  import argparse
  from tqdm import tqdm
  from pathlib import Path

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
    return [item for item in items if item not in already]

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
  
