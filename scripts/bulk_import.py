#!/bin/python3

from yaspin import yaspin

with yaspin(text="Loading..."):
  from collections import defaultdict
  import argparse
  import re
  import enum
  import threading
  import concurrent.futures
  import requests
  import joblib
  from tqdm import tqdm
  from tqdm.contrib.concurrent import thread_map as tqdm_thread_map
  from pathlib import Path
  from datetime import datetime

  import json
  from yaml import load as read_yaml

  import gdrive_base
  import gdrive
  from tag_predictor import (
    TagPredictor,
    get_normalized_text_for_youtube_vid,
    get_ytdata_for_ids,
    normalize_text,
    save_normalized_text,
  )
  from pdfutils import readpdf

  LINK_SAVER = "LibraryUtils.LinkSaver"
  PDF_SAVER = "LibraryUtils.BulkPDFImporter"

with yaspin(text="Loading tag predictor..."):
  course_predictor = TagPredictor.load()
disk_memorizor = joblib.Memory(gdrive.gcache_folder, verbose=0)

def _do_parse_and_predict(item: Path) -> tuple[str, str]:
  text = normalize_text(readpdf(item, normalize=0))
  name = normalize_text((' '+item.stem) * 3)
  course = course_predictor.predict([text+name], normalized=True)[0]
  return text, course

_inference_pool = None
def get_inference_pool():
  global _inference_pool
  if _inference_pool is None:
    _inference_pool = concurrent.futures.ProcessPoolExecutor(max_workers=2)
  return _inference_pool

def synchronized(func):
  func.__lock__ = threading.Lock()
  from functools import wraps
  @wraps(func)
  def wrapper(*args, **kwargs):
    with func.__lock__:
      return func(*args, **kwargs)
  return wrapper

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
  key: gdrive_base.folderlink_to_id(value['private'])
  for key, value in json.loads(gdrive.FOLDERS_DATA_FILE.read_text()).items()
  if value.get('private')
}

class BulkItemImporter:
  def __init__(self) -> None:
    self.unread_folderid_for_course = dict()
    self.folder_getter_lock = threading.Lock()
  
  def get_unread_subfolder_name(self) -> str:
    return "⚡ Bulk Importer"

  def can_import_item(self, item: str) -> bool:
    return False

  def import_items(self, items: list[str]):
    # Go ahead and use a tqdm or somesuch to report your progess
    # as makes sense for this importer
    return False

  def get_folder_id_for_course(self, course:str) -> str:
    with self.folder_getter_lock:
      if course in self.unread_folderid_for_course:
        return self.unread_folderid_for_course[course]
      private_folder = PRIVATE_FOLDERID_FOR_COURSE[course]
      subfolders = gdrive.gcache.get_subfolders(private_folder, include_shortcuts=False)
      unread_folder = None
      for subfolder in subfolders:
        if 'unread' in subfolder['name'].lower():
          unread_folder = subfolder['id']
          break
      if not unread_folder:
        unread_folder = gdrive.gcache.create_folder(f"Unread ({course})", private_folder)
      subfolders = gdrive.gcache.get_subfolders(unread_folder, include_shortcuts=False)
      for subfolder in subfolders:
        if subfolder['name'] == self.get_unread_subfolder_name():
          self.unread_folderid_for_course[course] = subfolder['id']
          return subfolder['id']
      subfolder = gdrive.gcache.create_folder(
        self.get_unread_subfolder_name(),
        unread_folder,
      )
      self.unread_folderid_for_course[course] = subfolder
      return subfolder

class BulkPDFType(enum.StrEnum):
  ACADEMIA_EDU = 'academia.edu'
  TO_GO_THROUGH = 'togothrough'
  CORE_API = 'coreapi'

class BulkPDFImporter(BulkItemImporter):
  def __init__(self, pdf_type: BulkPDFType) -> None:
    super().__init__()
    self.pdf_type = pdf_type
    match pdf_type:
      # Make sure to update gdrive.select_ids_to_keep as well
      case BulkPDFType.ACADEMIA_EDU:
        self.folder_name = "🏛️ Academia.edu"
      case BulkPDFType.TO_GO_THROUGH:
        self.folder_name = "📥 To Go Through"
      case BulkPDFType.CORE_API:
        self.folder_name = "🔓 CORE API"
      case _:
        raise ValueError("Invalid PDF type: "+pdf_type)

  def get_unread_subfolder_name(self) -> str:
    return self.folder_name
  
  def can_import_item(self, item: str) -> bool:
    return item.lower().endswith('.pdf') \
      and Path(item).is_file() # so far, only support local files
  
  def import_item(self, item: Path, verbose: bool) -> str | None:
    text, course = get_inference_pool().submit(_do_parse_and_predict, item).result()
    if verbose:
      print(f"Placing \"{item.name}\" in \033[1m{course}\033[0m/Unread/{self.folder_name}")
    folder = self.get_folder_id_for_course(course)
    ret = gdrive_base.upload_to_google_drive(
      item,
      folder_id=folder,
      filename=item.name,
      creator=PDF_SAVER,
      verbose=verbose,
    )
    if ret:
      save_normalized_text(ret, text)
    return ret
  
  def import_items(self, items: list[str | Path]):
    files = [Path(item) for item in items]
    if self.pdf_type == BulkPDFType.ACADEMIA_EDU:
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
    def _upload_one_fp(fp):
      if gdrive.has_file_already(fp):
        tqdm.write(f"Skipping {fp} as that file is already on Drive!")
        fp.unlink()
        return
      uploaded = self.import_item(fp, False)
      if uploaded:
        fp.unlink()
      else:
        tqdm.write(f"Failed to upload {fp}!")
    
    tqdm_thread_map(_upload_one_fp, files, max_workers=8)

class GDocURLImporter(BulkItemImporter):
  def resort_docs(self, items: list[dict], auto_folder_to_course: dict[str, str]):
    """Takes a list of Google Doc File objects and moves them to the predicted folder"""
    raise NotImplementedError("GDocURLImporter doesn't know how to sort things itself")

  def filter_already_imported_items(self, items:list[str]) -> list[str]:
    already = self.already_imported_items(items)
    return [item for item in items if item not in already]
  
  def already_imported_items(self, items:list[str]) -> set[str]:
    print(f"Seeing if we've imported any of these already...")
    already = set()
    for url in items:
      if gdrive.get_url_doc(url):
        already.add(url)
    print(f"Found {len(already)} URLs already added")
    return already

def create_gdoc(url: str, title: str, html: str, folder_id: str):
  return gdrive.create_doc(
    filename=title,
    html=f"<h1>{title}</h1><h2><a href=\"{url}\">{url}</a></h2>{html}",
    custom_properties={
      "createdBy": LINK_SAVER,
      "url": url,
    },
    folder_id=folder_id,
  )

@disk_memorizor.cache()
def _get_html(url):
  req = requests.get(url)
  assert req.ok
  return req.text
  
def get_html(url):
  try:
    return _get_html(url)
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

  def resort_docs(self, items: list[dict], auto_folder_to_course: dict[str, str]):
    """Takes a list of Google Doc File objects and moves them to the predicted folder"""
    from bs4 import BeautifulSoup
    urls = [doc['properties']['url'] for doc in items]
    print("Fetching webpages...")
    htmls = tqdm_thread_map(
      get_html,
      urls,
      max_workers=8,
    )
    print("Parsing webpages...")
    pbar = tqdm(list(zip(items, htmls)))
    for doc, html in pbar:
      if not html:
        # fallback to using the Doc title. Better than nothing.
        doc['text'] = doc['name']
        continue
      soup = BeautifulSoup(html, features='lxml')
      try:
        title = soup.select_one('div.bodyhead').getText(strip=True)
        table = soup.select_one('div.talklist table table')
        rows = table.find_all('tr')
      except AttributeError as e:
        e.add_note(f"While trying to parse {doc['properties']['url']}")
        raise e
      assert title in rows[0].get_text(), f"The first table row should have the title"
      assert 'Listen' in rows[1].get_text(), f"The second row should have a Listen button"
      description = rows[2].get_text(strip=True)
      doc['text'] = title + ' ' + description
    print("Predicting courses...")
    for doc in tqdm(items):
      doc['course'] = str(course_predictor.predict([doc['text']])[0])
    print("Moving any, if needed...")
    moves = 0
    moves_lock = threading.Lock()
    def maybe_move_doc(doc):
      old_course = auto_folder_to_course[doc['parents'][0]]
      if old_course != doc['course']:
        tqdm.write(f"Moving \"{doc['name']}\"\n  {old_course}  ->  {doc['course']}")
        gdrive.gcache.move_file(
          doc['id'],
          self.get_folder_id_for_course(doc['course']),
          doc['parents'],
          verbose=False,
        )
        nonlocal moves
        with moves_lock:
          moves += 1
    tqdm_thread_map(maybe_move_doc, items, max_workers=8)
    print(f"  Moved {moves}/{len(items)} docs to new folders")

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
      text = [track['title']]
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
setTimeout(() => {setInterval(() => {
    document.querySelector('#items > ytd-menu-service-item-renderer:nth-child(3)').click();
}, 2000);}, 1000)
```

Note: the above may need to be updated slightly based on the latest YT HTML

Also, after importing the new documents, you'll probably have to
run fix_yttranscript_cache.py for a few days to get all the data,
then run "--resort" here to sort those docs again with the transcript data.
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
  
  def extract_ids_from_urls(self, urls: list[str]) -> list[str]:
    return [
      gdrive.yt_url_to_id_re.search(url).groups()[0]
      for url in urls
    ]

  def _add_folder_to_snippets(self, snippets: list[dict]):
    print("Predicting courses for videos...")
    for snippet in tqdm(snippets):
      course = course_predictor.predict(
        [get_normalized_text_for_youtube_vid(snippet)],
        normalized=True,
      )[0]
      snippet['course'] = course
      snippet['folder'] = self.get_folder_id_for_course(course)
  
  def resort_docs(self, items: list[dict], auto_folder_to_course: dict[str, str]):
    """Takes a list of Google Doc File objects and moves them to the predicted folder"""
    vid_urls = [doc['properties']['url'] for doc in items]
    vid_ids = self.extract_ids_from_urls(vid_urls)
    snippets = get_ytdata_for_ids(vid_ids)
    self._add_folder_to_snippets(snippets)
    print("Moving docs as needed:")
    moves = 0
    moves_lock = threading.Lock()
    def maybe_move_doc(doc, snippet):
      if snippet['folder'] != doc['parents'][0]:
        tqdm.write(f"Moving \"{doc['name']}\"\n  {auto_folder_to_course[doc['parents'][0]]}  ->  {snippet['course']}")
        gdrive.gcache.move_file(
          doc['id'],
          snippet['folder'],
          previous_parents=doc['parents'],
          verbose=False,
        )
        nonlocal moves
        with moves_lock:
          moves += 1
    tqdm_thread_map(maybe_move_doc, items, snippets, max_workers=8)
    print(f"  Moved {moves}/{len(snippets)} docs to new folders")

  def import_items(self, items: list[str]):
    vid_ids = self.extract_ids_from_urls(items)
    # dedupe based on normalized video id
    items = self.filter_already_imported_items([
      f"https://youtu.be/{vid}" for vid in vid_ids
    ])
    if len(items) == 0:
      return
    print("Getting all video data...")
    snippets = get_ytdata_for_ids(vid_ids)
    self._add_folder_to_snippets(snippets)
    print("Creating GDocs for Videos...")
    tqdm_thread_map(create_gdoc_for_yt_snippet, snippets, max_workers=8)

ITEM_IMPORTERS: list[tuple[str, GDocURLImporter]] = [
  ('YouTube Videos', BulkYouTubeVideoImporter()),
  ('DharmaSeed Talks', DharmaSeedURLImporter()),
]
IMPORTERS: dict[str, GDocURLImporter] = {k: v for k, v in ITEM_IMPORTERS}

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

def get_all_predictable_unread_folders(predictable_classes: list[str]) -> tuple[dict[str, str], dict[str, str]]:
  unread_id_to_course_name_map = dict()
  course_name_to_unread_id_map = dict()
  if not predictable_classes:
    predictable_classes = course_predictor.classes
  with yaspin(text="Loading all unread folders..."):
    for course_name in predictable_classes:
      _, private_id = gdrive.get_gfolders_for_course(course_name)
      assert bool(private_id), f"Why does {course_name} not have a private folder?"
      subfolders = gdrive.gcache.get_subfolders(private_id)
      for subfolder in subfolders:
        if str(subfolder['name']).lower().startswith('unread'):
          unread_id_to_course_name_map[subfolder['id']] = course_name
          course_name_to_unread_id_map[course_name] = subfolder['id']
          break
  print(f"Got {len(unread_id_to_course_name_map)} unread folders")
  return (unread_id_to_course_name_map, course_name_to_unread_id_map)

def all_folders_with_name_by_course(folder_name: str, importer_type: str, unread_id_to_course_name_map: dict[str, str]) -> tuple[dict, dict]:
  all_folders = gdrive.gcache.sql_query(
    "name = ? AND mime_type = ?",
    (folder_name, 'application/vnd.google-apps.folder', )
  )
  course_to_auto_folder = dict()
  auto_folder_to_course = dict()
  with yaspin(text=f"Loading all {importer_type} folders..."):
    for folder in all_folders:
      parent = folder['parents'][0]
      assert parent in unread_id_to_course_name_map, f"{gdrive_base.FOLDER_LINK_PREFIX}{parent} wasn't found in the predictable unread folders list"
      course_to_auto_folder[unread_id_to_course_name_map[parent]] = folder['id']
      auto_folder_to_course[folder['id']] = unread_id_to_course_name_map[parent]
  print(f"Got {len(course_to_auto_folder)} {importer_type} folders")
  return (course_to_auto_folder, auto_folder_to_course)

@synchronized
def get_or_create_autopdf_folder_for_course(
    new_course: str,
    folder_name: str,
    course_to_autopdf_folder: dict,
    course_name_to_unread_id_map: dict,
    unread_id_to_course_name_map: dict,
    autopdf_folder_to_course: dict,
) -> str:
  if new_course not in course_to_autopdf_folder:
    if new_course not in course_name_to_unread_id_map:
      course_name_to_unread_id_map[new_course] = gdrive.gcache.create_folder(
        "Unread",
        gdrive.get_gfolders_for_course(new_course)[1],
      )
      unread_id_to_course_name_map[course_name_to_unread_id_map[new_course]] = new_course
    new_folder = gdrive.gcache.create_folder(
      folder_name,
      course_name_to_unread_id_map[new_course],
    )
    course_to_autopdf_folder[new_course] = new_folder
    autopdf_folder_to_course[new_folder] = new_course
  else:
    new_folder = course_to_autopdf_folder[new_course]
  return new_folder

def resort_existing_link_docs():
  # We don't use the unread id map here as the importers will call
  # gdrive.gcache.get_subfolders themselves.
  unread_id_to_course_name_map, _ = get_all_predictable_unread_folders()
  for import_name, importer in ITEM_IMPORTERS:
    print(f"Resorting {import_name}...")
    _resort_link_docs_of_type(
      unread_id_to_course_name_map,
      import_name,
      importer,
    )

def _resort_link_docs_of_type(
  unread_id_to_course_name_map: dict[str, str],
  import_name: str,
  importer: GDocURLImporter,
):
  folder_name = importer.get_unread_subfolder_name()
  course_to_auto_folder, auto_folder_to_course = all_folders_with_name_by_course(
    folder_name,
    import_name,
    unread_id_to_course_name_map,
  )
  drive_files_to_reconsider = gdrive.gcache.properties_sql_query(
    f"prop.key = 'url' AND file.parent_id IN ({','.join('?' * len(course_to_auto_folder))})",
    tuple(course_to_auto_folder.values()),
  )
  print(f"Got {len(drive_files_to_reconsider)} {import_name} to resort")
  # Prime the importer's cache of auto_folder ids
  importer.unread_folderid_for_course.update(course_to_auto_folder)
  # Do the resorting
  importer.resort_docs(drive_files_to_reconsider, auto_folder_to_course)

def resort_existing_pdfs_of_type(pdf_type: str):
  # get all folders of pdf_type
  importer = BulkPDFImporter(pdf_type)
  folder_name = importer.get_unread_subfolder_name()
  unread_id_to_course_name_map, course_name_to_unread_id_map = get_all_predictable_unread_folders()
  course_to_autopdf_folder, autopdf_folder_to_course = all_folders_with_name_by_course(
    folder_name,
    pdf_type,
    unread_id_to_course_name_map,
  )
  # get all PDFs with one of those parents
  drive_files_to_reconsider = gdrive.gcache.sql_query(
    f"mime_type='application/pdf' AND parent_id IN ({','.join('?' * len(course_to_autopdf_folder))})",
    tuple(course_to_autopdf_folder.values()),
  )
  print(f"Got {len(drive_files_to_reconsider)} PDF files to resort")

  # Ensure we have their pickles
  print("Fetching their texts...")
  import joblib
  from train_tag_predictor import save_pdf_text_for_drive_file, NORMALIZED_TEXT_FOLDER
  tqdm_thread_map(
    save_pdf_text_for_drive_file,
    drive_files_to_reconsider,
    max_workers=4,
  )
  
  # Sort them into courses
  # and move the ones that need to be moved
  print("Resorting...")
  pbar = tqdm(drive_files_to_reconsider)
  for drive_file in pbar:
    normalized_text_file = NORMALIZED_TEXT_FOLDER.joinpath(f"{drive_file['id']}.pkl")
    assert normalized_text_file.exists(), f"Couldn't find the normalized text for {gdrive.DRIVE_LINK.format(drive_file['id'])}"
    normalized_text = joblib.load(normalized_text_file)
    new_course = course_predictor.predict([
      normalized_text + normalize_text((' '+drive_file['name'][:-4]) * 3)
    ], normalized=True)[0]
    new_folder = get_or_create_autopdf_folder_for_course(
      new_course,
      folder_name,
      course_to_autopdf_folder,
      course_name_to_unread_id_map,
      unread_id_to_course_name_map,
      autopdf_folder_to_course,
    )
    old_folder = drive_file['parents'][0]
    old_course = autopdf_folder_to_course[old_folder]
    if old_folder != new_folder:
      pbar.write(f"\"{drive_file['name']}\"")
      pbar.write(f"  {old_course}  \t->  {new_course}")
      gdrive.gcache.move_file(
        drive_file['id'],
        new_folder,
        drive_file['parents'],
        verbose=False,
      )

if __name__ == "__main__":
  argparser = argparse.ArgumentParser(
    prog="python3 bulk_import.py",
    description="Upload many unread items to Google Drive at once",
    formatter_class=argparse.RawTextHelpFormatter,
  )
  argparser.add_argument(
    "items",
    nargs="*",
    help="""The items (or source of the items) to upload.
These items can be:
  - A PDF of type --pdf-type
  - A YouTube Video Link
  - A YouTube Playlist Link (each video added seperately)
  - A YAML or JSON file containing a list of any of the above
""")
  argparser.add_argument(
    '--pdf-type',
    dest="pdf_type",
    nargs="?",
    choices=[str(v) for v in BulkPDFType],
    help="Which subfolder to sort PDFs into (required if importing PDFs)",
  )
  argparser.add_argument(
    '--resort',
    default=False,
    action='store_true',
    help="""Goes through all previously uploaded items and moves them
    if the new TagPredictor has changed its mind.
    If --pdf-type is specified, it'll do those PDFs.
    If no pdf-type is, then it'll resort the link docs.""",
  )
  args = argparser.parse_args()
  if args.resort:
    if args.pdf_type:
      resort_existing_pdfs_of_type(args.pdf_type)
    else:
      resort_existing_link_docs()
  raw_items = []
  if len(args.items):
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
  
