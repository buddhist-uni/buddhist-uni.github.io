#!/bin/python3

########
# Personal Google Drive Utilities
#
# This file contains a number of utility functions for interacting with my
# Google Drive Library which are specifically tailored to my Drive's structure.
#
# This file can be run as a script, in which case it takes links and moves them
# to a Drive folder according to the slugs in _data/drive_folders.json
#   (see get_gfolders_for_course for how those slugs are parsed)
########

import requests
import enum
from datetime import datetime
from pathlib import Path
import readline
from typing import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from math import floor
import atexit
from strutils import (
  titlecase,
  git_root_folder,
  input_with_prefill,
  prompt,
  whitespace,
  yt_url_to_plid_re,
  yt_url_to_id_re,
  file_info,
  radio_dial,
  system_open,
)
import json
import re
from archivedotorg import archive_urls
try:
  from yaspin import yaspin
  from bs4 import BeautifulSoup
  from tqdm import tqdm
except:
  print("pip install yaspin bs4 tqdm")
  exit(1)

from gdrive_base import (
  folderlink_to_id,
  FOLDER_LINK,
  link_to_id,
  move_drive_file,
  get_shortcuts_to_gfile,
  create_drive_shortcut,
  trash_drive_file,
  get_ytvideo_snippets,
  fetch_youtube_transcript,
  htmlify_ytdesc,
  _yt_thumbnail,
  get_ytplaylist_snippet,
  get_ytvideo_snippets_for_playlist,
  DOC_LINK,
  create_doc,
  download_file,
  DRIVE_LINK,
  FOLDER_LINK_PREFIX,
  batch_get_files_by_id,
  GFIDREGEX,
)
import local_gdrive
from google.auth.exceptions import TransportError
from httplib2 import ServerNotFoundError

FOLDERS_DATA_FILE = git_root_folder.joinpath("_data", "drive_folders.json")

gcache_folder = git_root_folder.joinpath("scripts/.gcache")
gcache = local_gdrive.DriveCache(gcache_folder.joinpath("drive.sqlite"))
try:
  gcache.update()
except (ServerNotFoundError, TransportError):
  pass # We're offline. No big deal. That's why it's a local cache :)
atexit.register(gcache.close)

OLD_VERSIONS_FOLDER_ID = "1LBHbz_2prpqqrb_TQxRhuqNTrU9CIZga"



def course_input_completer_factory() -> Callable[[str, int], str]:
  gfolders: dict[str, dict[str, str]]
  gfolders = json.loads(FOLDERS_DATA_FILE.read_text())
  suggestions_cache: dict[str, list[str]]
  suggestions_cache = dict()
  subfolders_cache = dict()
  def _ret(so_far: str, suggestion_idx: int) -> str:
    if so_far not in suggestions_cache:
      if '/' not in so_far:
        suggestions_cache[so_far] = [
          course_name for course_name in gfolders.keys()
          if course_name and course_name.startswith(so_far)
        ]
      else:
        parts = so_far.split('/')
        course = parts[0]
        if course not in gfolders:
          suggestions_cache[so_far] = []
        else:
          links = gfolders[course]
          flink = links['private'] or links['public']
          fid = folderlink_to_id(flink)
          pidx = 1
          prefix = course
          while True:
            if fid in subfolders_cache:
              subfolders = subfolders_cache[fid]
            else:
              subfolders = gcache.get_subfolders(fid)
              subfolders_cache[fid] = subfolders
            matches = [f for f in subfolders if parts[pidx].lower() in f['name'].lower()]
            for f in matches:
              if f['id'] not in subfolders_cache:
                subfolders_cache[f['id']] = gcache.get_subfolders(f['id'])
            if len(parts) <= pidx + 1:
              suggestions_cache[so_far] = [f"{prefix}/{f['name']}{'/' if subfolders_cache[f['id']] else ''}" for f in matches]
              break
            if len(matches) != 1: # Don't know which, so we better run
              suggestions_cache[so_far] = []
              break
            fid = matches[0]['id']
            prefix = f"{prefix}/{matches[0]['name']}"
            pidx += 1
    return suggestions_cache[so_far][suggestion_idx]

  return _ret

def input_course_string_with_tab_complete(prompt='course: ', prefill=None):
    prev_complr = readline.get_completer()
    prev_delims = readline.get_completer_delims()
    readline.set_completer(course_input_completer_factory())
    readline.set_completer_delims('')
    readline.parse_and_bind('tab: complete')
    if prefill:
      ret = input_with_prefill(prompt, prefill)
    else:
      ret = input(prompt)
    readline.set_completer(prev_complr)
    readline.set_completer_delims(prev_delims)
    return ret


def add_tracked_folder(slug, public, private, gfolders=None):
  gfolders = gfolders or json.loads(FOLDERS_DATA_FILE.read_text())
  gfolders[slug] = {'public': public, 'private': private}
  FOLDERS_DATA_FILE.write_text(json.dumps(gfolders, sort_keys=True, indent=1))
  return gfolders

def get_gfolders_for_course(course):
  """Returns a (public, private) tuple of GIDs given a human course string"""
  gfolders = json.loads(FOLDERS_DATA_FILE.read_text())
  parts = course.split('/')
  course = parts[0]
  if course not in gfolders:
    print("Hmmm... I don't know that Google Drive folder! Let's add it:")
    publicurl = input("Public link: ") or None
    privateurl = input("Private link: ") or None
    gfolders = add_tracked_folder(course, publicurl, privateurl, gfolders=gfolders)
  
  private_folder = folderlink_to_id(gfolders[course]['private'])
  public_folder = folderlink_to_id(gfolders[course]['public'])
  del parts[0]
  while len(parts) > 0:
    if not parts[0]: # use "course/" syntax to move to the private version of the course
      return (None, private_folder)
    subfolders = gcache.get_subfolders(private_folder)
    print(f"Got subfolders: {[f.get('name') for f in subfolders]}")
    q = parts[0].lower()
    found = False
    for subfolder in subfolders:
      if subfolder['name'].lower().startswith(q):
        print(f"Going with \"{subfolder['name']}\"")
        private_folder = subfolder['id']
        public_folder = None
        found = True
        break
    if not found:
      for subfolder in subfolders:
        if q in subfolder['name'].lower():
          print(f"Going with \"{subfolder['name']}\"")
          private_folder = subfolder['id']
          public_folder = None
          found = True
          break
    if found:
      del parts[0]
      continue
    print(f"No subfolder found matching \"{q}\"")
    q = input_with_prefill("Create new subfolder: ", titlecase(parts[0]))
    if not q:
      if public_folder:
        if prompt("Okay, won't make a new subfolder, but should I put this in the public folder?"):
          return (public_folder, private_folder)
      print("Okay, will just put in the private folder then.")
      return (None, private_folder)
    subfolder = gcache.create_folder(q, private_folder)
    if not subfolder:
      raise RuntimeError("Error creating subfolder. Got null API response.")
    private_folder = subfolder
    public_folder = None
    del parts[0]
  return (public_folder, private_folder)

def get_course_for_folder(folderid):
  gfolders = json.loads(FOLDERS_DATA_FILE.read_text())
  courselist = {v['public']: k for k, v in gfolders.items()}
  if not folderid.startswith("http"):
    folderid = FOLDER_LINK.format(folderid)
  if folderid in courselist:
    return courselist[folderid]
  courselist = {v['private']: k for k, v in gfolders.items()}
  return courselist.get(folderid, None)

def move_gfile(glink, folders):
  gfid = link_to_id(glink)
  public_fid, private_fid = folders
  file = move_drive_file(gfid, public_fid or private_fid)
  shortcuts = get_shortcuts_to_gfile(gfid)
  if public_fid and private_fid:
    if len(shortcuts) != 1:
      print("Creating a (new, private) shortcut...")
      create_drive_shortcut(gfid, file.get('name'), private_fid)
    elif len(shortcuts) == 1:
      s=shortcuts[0]
      print(f"Moving existing shortcut from  {FOLDER_LINK.format(s['parents'][0])}  to  {FOLDER_LINK.format(private_fid)}  ...")
      move_drive_file(s['id'], private_fid, previous_parents=s['parents'])
  if not public_fid or not private_fid or len(shortcuts) > 1:
    for s in shortcuts:
      print(f"Trashing the old shortcut in {FOLDER_LINK.format(s['parents'][0])} ...")
      trash_drive_file(s['id'])
  print("Done!")

def guess_link_title(url):
  try:
    title = BeautifulSoup(requests.get(url).text, "html.parser").find("title").get_text().replace(" - YouTube", "")
    return re.sub(r"\(GDD-([0-9]+) Master Sheng Yen\)", r" (GDD-\1) - Master Sheng Yen", title)
  except:
    return ""

def make_link_doc_html(title, link):
  ret = f"""<h1>{title}</h1><h2><a href="{link}">{link}</a></h2>"""
  if 'youtu' in link:
    if 'playlist' in link:
      ret += make_ytplaylist_summary_html(yt_url_to_plid_re.search(link).groups()[0])
    else:
      vid = yt_url_to_id_re.search(link)
      if vid:
        ret += make_ytvideo_summary_html(vid.groups()[0])
  return ret

def make_ytvideo_summary_html(vid):
  from tag_predictor import YOUTUBE_DATA_FOLDER
  cachef = YOUTUBE_DATA_FOLDER.joinpath(f"{vid}.json")
  if cachef.exists():
    snippet = json.loads(cachef.read_text())
    transcript = snippet.get('transcript',[])
  else:
    snippet = get_ytvideo_snippets([vid])[0]
    transcript = fetch_youtube_transcript(vid)
    snippet['transcript'] = transcript
    cachef.write_text(json.dumps(snippet))
  return _make_ytvideo_summary_html(vid, snippet, transcript)

def _make_ytvideo_summary_html(vid, snippet, transcript):
  ret = ""
  duration = (snippet.get('contentDetails') or {}).get('duration')
  if duration:
    if duration.startswith('PT'):
      duration = duration[2:]
    duration = re.sub(r'([HM])([0-9])', r'\1 \2', duration)
    ret += f"<h2>Duration</h2><p>{duration}</p>"
  if snippet.get('publishedAt'):
    uploaded_on = datetime.fromisoformat(snippet['publishedAt'])
    ret += f"""<h2>Uploaded</h2><p>{uploaded_on.strftime('%a %d %b %Y, %I:%M%p')}</p>"""
  else:
    print(f"  No upload date found. Snippet keys are: {list(snippet.keys())}")
  if snippet.get('description'):
    desc = htmlify_ytdesc(snippet['description'])
    ret += f"""<h2>Video Description (from YouTube)</h2><p>{desc}</p>"""
  ret += f"""<h2>Thumbnail</h2><p><img src="{_yt_thumbnail(snippet)}" /></p>"""
  if len(snippet.get('tags',[])) > 0:
    ret += f"""<h2>Video Tags</h2><p>{snippet['tags']}</p>"""
  if transcript and not isinstance(transcript, str): # string values are failure modes (disabled, restricted, etc)
    ret += "<h2>Video Subtitles</h2>"
    for line in transcript:
      ret += f"""<p><a href="https://youtu.be/{vid}?t={floor(line['start'])}">{floor(line['start']/60)}:{round(line['start']%60):02d}</a> {whitespace.sub(' ', line['text'])}</p>"""
  return ret

def make_ytplaylist_summary_html(ytplid):
  ret = ""
  plsnip = get_ytplaylist_snippet(ytplid)
  desc = htmlify_ytdesc(plsnip.get('description', ''))
  defaultimg = _yt_thumbnail(plsnip)
  if desc:
    ret += f"""<h2>Description (from YouTube)</h2><p>{desc}</p>"""
  videos = get_ytvideo_snippets_for_playlist(ytplid, maxResults=500)
  if len(videos) > 0:
    ret += "<h2>Videos</h2>"
    for video in videos:
      ret += f"""<h3>{int(video['position'])+1}. <a href="https://youtu.be/{video['resourceId']['videoId']}">{video['title']}</a></h3>"""
      ret += f"""<p><img src="{_yt_thumbnail(video) or defaultimg}" /></p>"""
  return ret

def has_file_already(file_in_question) -> list:
  hash, _ = file_info(file_in_question)
  file_in_question = Path(file_in_question)
  mine = lambda l: [f for f in l if f['owners'][0]['me']]
  cfs = mine(gcache.get_items_with_md5(hash))
  if len(cfs) > 0:
    return cfs
  if len(file_in_question.name) > 16:
    cfs = mine(gcache.files_exactly_named(file_in_question.name))
    if len(cfs) > 0:
      return cfs
    cfs = mine(gcache.files_originally_named_exactly(file_in_question.name))
    if len(cfs) > 0:
      return cfs
  return []

def download_folder_contents_to(folder_id: str, target_directory: Path | str, recursive = False, follow_links = False, parallelism=6):
  """
  Downloads all files from folder_id to target_directory

  This is mostly a copypasta from gdrive_base but using the local gcache
  """
  target_directory = Path(target_directory)
  target_directory.mkdir(exist_ok=True)
  total_size = 0
  subfolders = []
  linked_files = []
  downloads = []
  with yaspin(text="Loading file list...") as ys:
    for child in gcache.get_children(folder_id):
      childpath = target_directory.joinpath(child['name'])
      if child['mimeType'] == 'application/vnd.google-apps.shortcut':
        if not follow_links:
          continue
        if child['shortcutDetails']['targetMimeType'] == 'application/vnd.google-apps.folder':
          if recursive:
            subfolders.append((child['shortcutDetails']['targetId'], childpath))
        else:
          linked_files.append(gcache.get_item(child['shortcutDetails']['targetId']))
        continue
      if child['mimeType'] == 'application/vnd.google-apps.folder':
        if not recursive:
          continue
        subfolders.append((child['id'], childpath))
        continue
      if childpath.exists():
        continue
      size = int(child.get('size',0))
      if not size:
        continue
      if any(d[1] == childpath for d in downloads):
        ys.write(f"WARNING: Skipping duplicate file \"{childpath}\"")
        continue
      total_size += size
      downloads.append((child['id'], childpath))
    if linked_files:
      for child in linked_files:
        size = int(child.get('size',0))
        if not size:
          continue
        childpath = target_directory.joinpath(child['name'])
        if childpath.exists():
          continue
        total_size += size
        downloads.append((child['id'], childpath))
  if not downloads:
    print(f"Nothing to download in '{target_directory.name}'")
  else:
    print(f"Downloading {len(downloads)} files to '{target_directory.name}'")
    if parallelism <= 1:
      with tqdm(unit='B', unit_scale=True, unit_divisor=1024, total=total_size) as pbar:
        for f in downloads:
          download_file(f[0], f[1], pbar)
    else:
      with ThreadPoolExecutor(max_workers=parallelism) as executor:
        futures = [executor.submit(download_file, f[0], f[1], False) for f in downloads]
        for future in tqdm(as_completed(futures), total=len(downloads), unit='f'):
          pass
  for cfid, child_path in subfolders:
    download_folder_contents_to(
      cfid,
      child_path,
      recursive=recursive,
      follow_links=follow_links,
      parallelism=parallelism,
    )

def load_folder_slugs() -> dict[str, str]:
  "A mapping from GFolder IDs to slug names (inverse of FOLDERS_DATA_FILE)"
  drive_folders = json.loads(FOLDERS_DATA_FILE.read_text())
  private_folder_slugs = {
    folderlink_to_id(drive_folders[k]['private']): k
    for k in drive_folders
  }
  public_folder_slugs = {
    folderlink_to_id(drive_folders[k]['public']): k
    for k in drive_folders
  }
  return {**private_folder_slugs, **public_folder_slugs}

def process_duplicate_files(files: list[dict[str, any]], folder_slugs: dict[str, str], verbose: bool, dry_run: bool) -> list[dict]:
  """Takes a list of duplicate Google Drive Files and removes the extra versions intelligently.
  
  Args:
    files: the list of duplicates as API Dicts
    folder_slugs: a mapping from Drive folder IDs to their slug names
  
  Returns: the files selected for keeping (usually just one)
  """
  for file in files:
    file['parent'] = gcache.get_item(file['parents'][0])
  ids_to_keep, reason = select_ids_to_keep(files, folder_slugs)
  files_to_keep = [f for f in files if f['id'] in ids_to_keep]
  files_to_trash = [f for f in files if f['id'] not in ids_to_keep]
  if verbose or len(files_to_keep) > 1:
    if len(files_to_keep) > 1:
      print("!!vvPLEASE Review the below duplicates manually vv!!")
    for file in files_to_keep:
      print(f"  Keeping \"{file['name']}\" in \"{(file['parent'] or {}).get('name')}\"")
      if len(files_to_keep) > 1:
        print(f"    {DRIVE_LINK.format(file['id'])}")
        print(f"    {FOLDER_LINK_PREFIX}{file['parent_id']}")
    if len(files_to_keep) > 1:
      print("!!^^PLEASE Review the above duplicates manually^^!!")
  for f in files_to_trash:
    if verbose:
      print(f"    Trashing \"{f['name']}\" in \"{f['parent']['name']}\"...")
    if not dry_run:
      gcache.trash_file(f['id'])
  longest_name = max((f['name'] for f in files), key=lambda n: len(n))
  if len(files_to_keep) == 1:
    if len(files_to_keep[0]['name']) < len(longest_name):
      if verbose:
        print(f"    Renaming kept file to longer name")
      if not dry_run:
        gcache.rename_file(files_to_keep[0]['id'], longest_name)
  return files_to_keep

class IDSelectionReason(enum.StrEnum):
  TAG_FOLDER = 'tag folder'
  IS_PUBLIC = 'is public'
  GENERIC_SUBFOLDER = 'generic subfolder'
  TAG_PRIORITY = 'tag priority'
  NAME_LENGTH = 'name length'
  ELDEST_FILE = 'eldest file'
  FOLDER_DEPTH = 'folder depth'
  

def select_ids_to_keep(files: list[dict[str, any]], folder_slugs: dict[str, str]) -> tuple[list[str], IDSelectionReason]:
  """Maticulously applies hand-crafted heuristics to select the keepers
  
  folder_slugs is a map from gid to tag slug, passed in to avoid recompute

  Returns: a list of ids to keep AND a string enum giving the reason for the choice
  """

  import website
  if not website.content:
    with yaspin(text="Loading website..."):
      website.load()
  UNIMPORTANT_SLUGS = [
    'to-go-through',
    'to-split',
    None,
  ]
  UNIMPORTANT_PREFIXES = [
    # Keep up-to-date with bulk_import.py
    "🔓 core api",
    "🏛️ academia.edu",
    "🌱 dharma seed",
    "📼 youtube videos",
    "📥 to go through",
    "DhammaTalks",
    "unread",
    'archive', # normally we wouldn't delete these losing data,
              # however, by this point in the code,
              # we have already eliminated unreads
              # so this leaves items that are archived in one place
              # and accepted somewhere deeper. In those cases we
              # should give such files a second chance at life.
  ]
  TAG_ORDER = {
    str(tf).removesuffix('.md'): idx+1
    for idx, tf in enumerate(website.config['collections']['tags']['order'])
  }
  LO_PRI = len(TAG_ORDER)+1000

  #####
  # If only one is in a slugged folder, keep that one
  ####
  slugs = [folder_slugs.get(f['parents'][0]) for f in files]
  filter_list = []
  for unimportant in UNIMPORTANT_SLUGS:
    filter_list.append(unimportant)
    important_slugs = [slug for slug in slugs if slug not in filter_list]
    num_slugs = len(important_slugs)
    if num_slugs == 1:
      # if there's only one file in a slugged folder, keep that one
      # no need to even check for permissions
      return [files[slugs.index(important_slugs[0])]['id']], IDSelectionReason.TAG_FOLDER

  #####
  # Don't trash any publicly-launched files
  #####
  file_permissions = batch_get_files_by_id([f['id'] for f in files], "id,name,permissions")
  are_publics = [any(p['type'] == 'anyone' for p in f['permissions']) for f in file_permissions]
  num_public = sum(are_publics)
  if num_public > 0:
    # Never suggest a public-facing file for deletion
    return [files[i]['id'] for i in range(len(files)) if are_publics[i]], IDSelectionReason.IS_PUBLIC
  
  #####
  # Discard files in "unimportant" subfolders first
  #####
  if 'parent' not in files[0]:
    for f in files:
      f['parent'] = gcache.get_item(f['parent_id'])
  for prefix in UNIMPORTANT_PREFIXES:
    if prefix == "DhammaTalks":
      unreads = ['1NTIsr31uhBXymkFUu2coGU72vdCjwfNp' in [f['parent']['parents'][0], f['parents'][0]] for f in files]
    else:
      unreads = [f['parent']['name'].lower().startswith(prefix) for f in files]
    unread_count = sum(unreads)
    if unread_count > 0 and unread_count < len(files):
      files = [file for i, file in enumerate(files) if not unreads[i]]
      if len(files) == 1:
        return [files[0]['id']], IDSelectionReason.GENERIC_SUBFOLDER
      slugs = [slug for i, slug in enumerate(slugs) if not unreads[i]]
  
  #####
  # Next, try to use the site's TAG_ORDER to prioritize placement
  #   Keep files placed in more important subfolders and trash those deeper
  #####
  if not any(slugs):
    slugs = [folder_slugs.get(f['parent']['parents'][0]) for f in files]
  if any(slug in TAG_ORDER for slug in slugs):
    priorities = [TAG_ORDER.get(slug, LO_PRI) for slug in slugs]
    highest = min(priorities)
    assert len(files) == len(priorities)
    files = [files[i] for i in range(len(files)) if priorities[i] == highest]
    if len(files) == 1:
      return [files[0]['id']], IDSelectionReason.TAG_PRIORITY
    
  #####
  # If some couldn't be disambiguated by folder because they are in
  #   the same subfolder, then just pick one
  #####
  if len(set(file['parent_id'] for file in files)) == 1:
    # All files are in the same folder and have the same md5
    # first try to pick the longest name
    name_lens = [len(file['name']) for file in files]
    longest = max(name_lens)
    files = [file for file in files if len(file['name'])==longest]
    if len(files) == 1:
      return [file['id'] for file in files], IDSelectionReason.NAME_LENGTH
    # That failing, pick the eldest
    modifies = [file['modifiedTime'] for file in files]
    eldest = min(modifies)
    idx = modifies.index(eldest)
    return [files[idx]['id']], IDSelectionReason.ELDEST_FILE
  
  #####
  # Disambiguate remaining folders by depth
  #  This time we prefer deeper folders as likely more accurate placement
  ####
  max_depth = 0
  deepest = None
  for file in files:
    depth = 0
    parent = file['parent']
    while parent and parent['parent_id']:
      depth += 1
      new_parent = gcache.get_item(parent['parent_id'])
      if new_parent:
        parent = new_parent
      else:
        break
    file['depth'] = depth
    if depth > max_depth:
      max_depth = depth
      deepest = file
    file['root'] = parent
  roots = set(file['root']['id'] for file in files)
  assert len(roots) == 1, f"Multiple roots found for {files}"
  return [deepest['id']], IDSelectionReason.FOLDER_DEPTH

def remote_file_for_local_file(fp: Path, folder_slugs: dict[str, str], default_folder_id=None) -> dict | None:
  """Ensures that there is exactly one copy of `fp` on Drive and returns it.
  
  Args:
    fp: the Path to the local file we're looking for on the server
    folder_slugs: a mapping of folder ids to slugs (used by the deduper)
    default_folder_id: where to upload the file if it isn't found
  
  Returns: the Google API dict for the file {'id': ..."""
  remotes = has_file_already(fp)
  if not remotes:
    new_id = gcache.upload_file(fp, folder_id=default_folder_id)
    return gcache.get_item(new_id)
  if len(remotes) > 1:
    print(f"Found multiple matching uploads for {fp.name}...")
    kept = process_duplicate_files(remotes, folder_slugs, verbose=True, dry_run=False)
    if len(kept) != 1:
      raise ValueError("Unable to select which to keep. Please clean this up manually.")
    remotes = kept
  return remotes[0]


def get_url_doc(url: str) -> dict | None:
    """
    If we already have a Google Doc pointing to url, return it, else None
    """
    # Join with drive_items to check mime_type
    with gcache._lock:
        gcache.cursor.execute(
            """
            SELECT di.* 
            FROM drive_items di
            JOIN item_properties ip ON di.id = ip.file_id
            WHERE ip.key = 'url' AND ip.value = ? AND di.mime_type = ?
            LIMIT 1
            """,
            (url, 'application/vnd.google-apps.document'),
        )
        row = gcache.cursor.fetchone()
        return gcache.row_dict_to_api_dict(dict(row)) if row else None


def find_duplicate_urls() -> list[str]:
    """
    Finds all urls that have more than one pointing doc in the user's files
    """
    with gcache._lock:
        sql = """
            SELECT ip.value
            FROM item_properties ip
            JOIN drive_items di ON ip.file_id = di.id
            WHERE ip.key = 'url' AND di.owner = 1
            GROUP BY ip.value
            HAVING COUNT(*) > 1
            ORDER BY ip.value
        """
        gcache.cursor.execute(sql)
        return [row['value'] for row in gcache.cursor.fetchall()]

def fetch_files_distinction_pointer(gc: local_gdrive.DriveCache, file_id: str) -> str | None:
  with gc._lock:
    gc.cursor.execute("SELECT value FROM item_properties WHERE key = 'distinctFrom' AND file_id = ?", (file_id,))
    pointing_to = gc.cursor.fetchone()
  if not pointing_to:
    return None
  return pointing_to['value']

def fetch_distinct_file_pointing_to(gc: local_gdrive, target_file_id: str) -> str | None:
  with gc._lock:
      gc.cursor.execute("SELECT file_id FROM item_properties WHERE key = 'distinctFrom' AND value = ?", (target_file_id,))
      pointing_neighbor = gc.cursor.fetchone()
  if pointing_neighbor:
    return pointing_neighbor['file_id']
  return None

class ClosePairDecision(enum.StrEnum):
  FIRST_IS_OLD_VERSION = 'old a'
  SECOND_IS_OLD_VERSION = 'old b'
  THEY_ARE_THE_SAME = 'either'
  THEY_ARE_DISTINCT = 'different'

def is_duplicate_prompt(fa: dict, fb: dict, similariy: float=None) -> ClosePairDecision:
  pa = gcache.get_item(fa['parent_id'])
  pb = gcache.get_item(fb['parent_id'])
  def _print_file(gfile, gparent):
    if not gparent:
      gparent = {'name': 'Root Folder', 'id': '../my-drive'}
    print(f"\"{gfile['name']}\" in \"{gparent['name']}\" {FOLDER_LINK.format(gparent['id'])}")
  if not similariy:
    print("Which of these two files is the better version?")
  _print_file(fa, pa)
  if similariy:
    print(f"  was found to be {similariy:.3f} similar to")
  _print_file(fb, pb)
  while True:
    options = ["Open both", "A is better (B is an older version)", "B is better (A is an older version)", "Exactly the same file", "Completely different files"]
    match radio_dial(options):
      case 0:
          system_open(DRIVE_LINK.format(fa['id']))
          system_open(DRIVE_LINK.format(fb['id']))
      case 1:
          return ClosePairDecision.SECOND_IS_OLD_VERSION
      case 2:
          return ClosePairDecision.FIRST_IS_OLD_VERSION
      case 3:
          return ClosePairDecision.THEY_ARE_THE_SAME
      case 4:
          return ClosePairDecision.THEY_ARE_DISTINCT

class FileDistinctionManager:
  """
  Stores the file pairs that have been manually marked as being distinct.

  Uses a custom Google Drive file property "distinctFrom" set to another fileid
  to create rings of known-distinct files.
  """
  def __init__(self, gc: local_gdrive.DriveCache=None):
    if gc is None:
      gc = gcache
    self._folder_slugs = None
    self.gcache = gc
    self.fileid_to_distinct_neighbors: dict[str, set[str]]
    self.fileid_to_distinct_neighbors = dict()
    with gc._lock:
      pointers = [
        dict(row) for row in
        gc.cursor.execute(
          """SELECT prop.file_id, prop.value
          FROM item_properties prop
          JOIN drive_items item
          ON prop.file_id = item.id
          WHERE key = ?""",
          ('distinctFrom',)
        )
      ]
    pointers = {p['file_id']: p['value'] for p in pointers}
    pointers = self._fix_pointers(pointers)
    for k in pointers.keys():
      self.fileid_to_distinct_neighbors[k] = set()
      node = pointers[k]
      # Because we've fixed the pointers above, we're guarenteed cycles here
      while node != k:
        self.fileid_to_distinct_neighbors[k].add(node)
        node = pointers[node]
  
  def are_distinct(self, file_a: str, file_b: str) -> bool:
    """Returns True iff file_a and file_b are marked distinct already"""
    return file_a in self.fileid_to_distinct_neighbors and file_b in self.fileid_to_distinct_neighbors[file_a]

  def folder_slugs(self):
    if self._folder_slugs:
      return self._folder_slugs
    self._folder_slugs = load_folder_slugs()
    return self._folder_slugs
  
  def handle_close_pair_decision(self, decision: ClosePairDecision, actual_file_a: dict, actual_other_file: dict):
    """
    Handles whatever file moving, trashing, and Distinction pointer swapping as needed to actualize `decision`

    Args:
      `decision` is relative to `is_duplicate_prompt(actual_file_a, actual_other_file)` in that order
    """
    if decision == ClosePairDecision.THEY_ARE_DISTINCT:
      return self.mark_distinct(actual_other_file['id'], actual_file_a['id'])
    def _print_shortcuts(shortcuts: list[dict]):
      for shortcut in shortcuts:
        print(f"  \"{shortcut['name']}\"")
        print(f"     in {FOLDER_LINK.format(shortcut['parent_id'])}")
    would_keep, reason = select_ids_to_keep(
      [actual_other_file, actual_file_a],
      folder_slugs=self.folder_slugs(),
    )
    selected_to_keep = None
    selected_to_not = None
    if len(would_keep) > 1 and decision == ClosePairDecision.THEY_ARE_THE_SAME:
      assert reason == IDSelectionReason.IS_PUBLIC
      print("Both files are publicly launched!")
      print("Please handle manually and select one of these to keep:")
      choice = radio_dial([
        DRIVE_LINK.format(actual_file_a['id']),
        DRIVE_LINK.format(actual_other_file['id']),
      ])
      if choice == 0:
        decision = ClosePairDecision.SECOND_IS_OLD_VERSION
      elif choice == 1:
        decision = ClosePairDecision.FIRST_IS_OLD_VERSION
      else:
        raise ValueError("radio_dial should output 0 or 1 for a binary choice, no?")
    if decision == ClosePairDecision.FIRST_IS_OLD_VERSION:
      selected_to_not, selected_to_keep = actual_file_a, actual_other_file
    elif decision == ClosePairDecision.SECOND_IS_OLD_VERSION:
      selected_to_not, selected_to_keep = actual_other_file, actual_file_a
    else:
      assert decision == ClosePairDecision.THEY_ARE_THE_SAME
      assert len(would_keep) == 1
      if would_keep[0] == actual_file_a['id']:
        selected_to_keep = actual_file_a
        selected_to_not = actual_other_file
      else:
        assert would_keep[0] == actual_other_file['id']
        selected_to_keep = actual_other_file
        selected_to_not = actual_file_a
    if len(would_keep) == 1 and would_keep[0] != selected_to_keep['id']:
      if reason == IDSelectionReason.IS_PUBLIC:
        print("The file you've selected as the old version is public")
        print("Please resolve this manually and then we'll move it to Old Versions.")
        input("Press enter to continue...")
      elif selected_to_not['parent_id'] != selected_to_keep['parent_id']:
        shortcuts = self.gcache.get_shortcuts_to_file(selected_to_keep['id'])
        if shortcuts:
          print(f"The file you've chosen to keep and move to {FOLDER_LINK.format(selected_to_not['parent_id'])} has shortcuts:")
          _print_shortcuts(shortcuts)
          input("Please handle them and then press enter to continue...")
        self.gcache.move_file(selected_to_keep['id'], selected_to_not['parent_id'], selected_to_keep['parents'])
    if 'distinctFrom' in selected_to_not['properties']:
      if 'distinctFrom' not in selected_to_keep['properties']:
        # simply swap out keep for not
        point_to_not_id = fetch_distinct_file_pointing_to(self.gcache, selected_to_not['id'])
        self._write_pointer(point_to_not_id, selected_to_keep['id'])
        self._write_pointer(selected_to_keep['id'], selected_to_not['properties']['distinctFrom'])
        self._write_pointer(selected_to_not['id'], None)
        self.fileid_to_distinct_neighbors[selected_to_keep['id']] = self.fileid_to_distinct_neighbors[selected_to_not['id']]
        del self.fileid_to_distinct_neighbors[selected_to_not['id']]
        for n in self.fileid_to_distinct_neighbors[selected_to_keep['id']]:
          self.fileid_to_distinct_neighbors[n].remove(selected_to_not['id'])
          self.fileid_to_distinct_neighbors[n].add(selected_to_keep['id'])
      else:
        # We can assume they aren't in the same cluster as they were just
        # marked as the same, ergo not distinct
        assert selected_to_not['id'] not in self.fileid_to_distinct_neighbors[selected_to_keep['id']]
        # since these two are marked the same, we should merge their clusters into a super-cluster
        super_cluster = self.fileid_to_distinct_neighbors[select_ids_to_keep['id']] | \
          self.fileid_to_distinct_neighbors[selected_to_not['id']]
        super_cluster.add(selected_to_keep['id'])
        points_to_not = fetch_distinct_file_pointing_to(self.gcache, selected_to_not['id'])
        assert points_to_not in self.fileid_to_distinct_neighbors[selected_to_not['id']]
        self._write_pointer(points_to_not, selected_to_keep['properties']['distinctFrom'])
        self._write_pointer(selected_to_keep['id'], selected_to_not['properties']['distinctFrom'])
        self._write_pointer(selected_to_not['id'], None)
        for n in super_cluster:
          nn = super_cluster.copy()
          nn.remove(n)
          self.fileid_to_distinct_neighbors[n] = nn
    # else: # the one we've marked for removal isn't part of the distinctions graph, so nothing to do here
    # Now, all that's left is to handle the marking!
    print(f"[Action] Moving old version to Old Versions...")
    move_gfile(selected_to_not['id'], (OLD_VERSIONS_FOLDER_ID, None))
    if len(selected_to_keep['name']) < len(selected_to_not['name']):
      if prompt("Swap file names?", default='y'):
        print("[Action] Swapping file names...")
        self.gcache.rename_file(selected_to_keep['id'], selected_to_not['name'])
        self.gcache.rename_file(selected_to_not['id'], selected_to_keep['name'])
    return
  
  def mark_distinct(self, file_a: str, file_b: str):
    """Writes to the DB the fact that file_a and file_b are distinctFrom eachother"""
    assert re.fullmatch(GFIDREGEX, file_a)
    assert re.fullmatch(GFIDREGEX, file_b)
    if self.are_distinct(file_a, file_b):
      return
    if file_a not in self.fileid_to_distinct_neighbors and file_b not in self.fileid_to_distinct_neighbors:
      self._write_pointer(file_a, file_b)
      self._write_pointer(file_b, file_a)
      self.fileid_to_distinct_neighbors[file_a] = set([file_b])
      self.fileid_to_distinct_neighbors[file_b] = set([file_a])
      return
    if file_b not in self.fileid_to_distinct_neighbors:
      file_a, file_b = file_b, file_a
    actual_file_a = self.gcache.get_item(file_a)
    actual_file_b = self.gcache.get_item(file_b)
    file_b_points_to = actual_file_b['properties']['distinctFrom']
    print(f"Adding {file_a} to the {file_b} cluster:")
    for other_file in self.fileid_to_distinct_neighbors[file_b]:
      actual_other_file = self.gcache.get_item(other_file)
      decision = is_duplicate_prompt(
        actual_file_a,
        actual_other_file,
      )
      if decision == ClosePairDecision.THEY_ARE_DISTINCT:
        continue
      return self.handle_close_pair_decision(
        decision,
        actual_file_a,
        actual_other_file,
      )
    if file_a not in self.fileid_to_distinct_neighbors:
      # file_a is distinct from the entire file_b cluster
      # and has no cluster of its own, so just add it to the group
      self._write_pointer(file_a, file_b_points_to)
      self._write_pointer(file_b, file_a)
      self.fileid_to_distinct_neighbors[file_a] = self.fileid_to_distinct_neighbors[file_b].copy()
      self.fileid_to_distinct_neighbors[file_a].add(file_b)
      for other_fid in self.fileid_to_distinct_neighbors[file_a]:
        self.fileid_to_distinct_neighbors[other_fid].add(file_a)
      return
    # else, file_a has its own cluster
    print(f"Adding {file_b} to the {file_a} cluster:")
    for other_file in self.fileid_to_distinct_neighbors[file_a]:
      actual_other_file = self.gcache.get_item(other_file)
      decision = is_duplicate_prompt(
        actual_file_b,
        actual_other_file,
      )
      if decision == ClosePairDecision.THEY_ARE_DISTINCT:
        continue
      return self.handle_close_pair_decision(
        decision,
        actual_file_b,
        actual_other_file,
      )
    # At this point we have two clusters and all are distinct, so merge them
    self._write_pointer(file_b, actual_file_a['properties']['distinctFrom'])
    self._write_pointer(file_a, file_b_points_to)
    super_cluster = self.fileid_to_distinct_neighbors[file_a] | \
      self.fileid_to_distinct_neighbors[file_b] | set([file_a, file_b])
    for n in super_cluster:
      nn = super_cluster.copy()
      nn.remove(n)
      self.fileid_to_distinct_neighbors[n] = nn
    return
  
  def _write_pointer(self, from_id: str, to_id: str | None):
    """Commits this new pointer to the DB"""
    if to_id is not None:
      assert re.fullmatch(GFIDREGEX, to_id), f"_write_pointer got a non-ID: {to_id}"
    print(f"[Info] Marking {from_id} distinctFrom {to_id}")
    self.gcache.write_property(from_id, 'distinctFrom', to_id)
  
  def _make_new_cycle(self, nodes: Iterable[str]) -> dict[str, str]:
    """Takes a collection of nodes and writes them as a cycle to the DB.

    NOTE: Does not update self.fileid_to_distinct_neighbors (hence an _method)
    
    Returns: the pointers map of which were made to point to which."""
    node_iter = iter(nodes)
    first_node = next(node_iter)
    last_node = first_node
    ret = dict()
    while next_node := next(node_iter, None):
      ret[last_node] = next_node
      self._write_pointer(last_node, next_node)
      last_node = next_node
    assert len(ret) >= 1, "Need to supply multiple nodes to make a cycle"
    ret[last_node] = first_node
    self._write_pointer(last_node, first_node)
    return ret


  def _fix_pointers(self, pointers: dict[str, str]) -> dict[str, str]:
    """Takes a dictionary of file ids to the file ids they point to
    It ensures that there are no dangling nodes, writing corrections to the DB
    as necessary and it returns the cleaned graph.
    """
    parents = {v: set() for v in pointers.values()}
    for k, v in pointers.items():
      parents[v].add(k)
    
    for k, v in parents.items():
      if len(v) > 1:
        print(f"INFO: {k} marked distinctFrom {v}: remaking the complete subgraph")
        to_add_up = v.copy()
        added_up = set()
        to_add_down = set([k])
        added_down = set()
        while len(to_add_up) > 0:
          n = to_add_up.pop()
          for p in parents.get(n, []):
            if p not in added_up:
              to_add_up.add(p)
          added_up.add(n)
        while len(to_add_down) > 0:
          n = to_add_down.pop()
          for c in pointers[n]:
            if c not in added_down:
              to_add_down.add(c)
          added_down.add(n)
        new_pointers = self._make_new_cycle(added_up | added_down)
        pointers.update(new_pointers)
        return self._fix_pointers(pointers)
    for k in pointers.keys():
      if k not in parents:
        leaf = k
        # because k has no parents, leaf can never
        # come back around to k, guarenteeing that
        # this isn't an infinite loop
        while leaf in pointers:
          leaf = pointers[leaf]
        living_leaf = self.gcache.get_item(leaf)
        if not living_leaf:
          leaf = parents[leaf]
          assert len(leaf) == 1, "Multiple parents should be handled alread"
          leaf = list(leaf)[0]
        print(f"INFO: Fixing broken distinctFrom chain from {k} to {leaf}")
        if leaf == k:
          self._write_pointer(leaf, None)
          del pointers[k]
          return self._fix_pointers(pointers)
        else:
          self._write_pointer(leaf, k)
          pointers[leaf] = k
          return self._fix_pointers(pointers)
    return pointers
  
  def clear_distinctions_from(self, file_id: str, pointing_to: str = None):
    if file_id not in self.fileid_to_distinct_neighbors:
      return
    neighbors = self.fileid_to_distinct_neighbors[file_id]
    assert len(neighbors) > 0, f"Why is there an empty neighbors list?"
    if len(neighbors) == 1:
      neighbor = list(neighbors)[0]
      self._write_pointer(neighbor, None)
      self._write_pointer(file_id, None)
      del self.fileid_to_distinct_neighbors[file_id]
      del self.fileid_to_distinct_neighbors[neighbor]
      return
    pointing_neighbor = fetch_distinct_file_pointing_to(self.gcache, file_id)
    assert pointing_neighbor in neighbors
    if not pointing_to:
      pointing_to = fetch_files_distinction_pointer(self.gcache, file_id)
    assert pointing_to in neighbors
    assert pointing_to != pointing_neighbor
    self._write_pointer(pointing_neighbor, pointing_to)
    self._write_pointer(file_id, None)
    for neighbor in neighbors:
      self.fileid_to_distinct_neighbors[neighbor].remove(file_id)
    del self.fileid_to_distinct_neighbors[file_id]

def move_distinctions_off_file(gc: local_gdrive.DriveCache, file_id: str) -> None:
  pointing_to = fetch_files_distinction_pointer(gc, file_id)
  if not pointing_to:
    return
  distinctions = FileDistinctionManager(gc)
  distinctions.clear_distinctions_from(file_id, pointing_to)

gcache.register_trash_callback(move_distinctions_off_file)


if __name__ == "__main__":
  glink_gens = []
  urls_to_save = []
  # a list of generator lambdas not direct links
  # so that we can defer doc creation to the end
  while True:
    link = input("Link (None to continue): ")
    if not link:
      break
    if not link_to_id(link):
      if "youtu" in link:
        link = link.split("?si=")[0]
      else:
        urls_to_save.append(link)
      title = input_with_prefill("title: ", guess_link_title(link))
      if len(link) > 121:
        with yaspin(text="Shortening long URL..."):
          link = requests.get('http://tinyurl.com/api-create.php?url='+link).text
      glink_gens.append(
        lambda title=title, link=link: DOC_LINK.format(
            create_doc(
              filename=title,
              html=make_link_doc_html(title, link),
              custom_properties={
                "createdBy": "LibraryUtils.LinkSaver",
                "url": link,
              },
            )
        )
      )
    else:
      glink_gens.append(lambda r=link: r)
  course = input_course_string_with_tab_complete()
  if course == "trash":
    print("Trashing...")
    for glink_gen in glink_gens:
      fid = link_to_id(glink_gen())
      shorts = get_shortcuts_to_gfile(fid)
      for short in shorts:
        print("  trashing shortcut first...")
        trash_drive_file(short['id'])
      trash_drive_file(fid)
    print("Done!")
  else:
    folders = get_gfolders_for_course(course)
    for glink_gen in glink_gens:
      move_gfile(glink_gen(), folders)
    print("Files moved!")
    if len(urls_to_save) > 0:
      print("Ensuring URLs are saved to Archive.org...")
      archive_urls(urls_to_save)
