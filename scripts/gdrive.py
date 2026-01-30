#!/bin/python3

import requests
from datetime import datetime
from pathlib import Path
import readline
from typing import Callable
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

def download_folder_contents_to(folder_id: str, target_directory: Path | str, recursive = False, follow_links = False):
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
    with tqdm(unit='B', unit_scale=True, unit_divisor=1024, total=total_size) as pbar:
      for f in downloads:
        download_file(f[0], f[1], pbar)
  for cfid, child_path in subfolders:
    download_folder_contents_to(
      cfid,
      child_path,
      recursive=recursive,
      follow_links=follow_links,
    )

def process_duplicate_files(files: list[dict[str, any]], folder_slugs: dict[str, str], verbose: bool, dry_run: bool) -> list[dict]:
  """Takes a list of duplicate Google Drive Files and removes the extra versions intelligently.
  
  Args:
    files: the list of duplicates as API Dicts
    folder_slugs: a mapping from Drive folder IDs to their slug names
  
  Returns: the files selected for keeping (usually just one)
  """
  for file in files:
    file['parent'] = gcache.get_item(file['parents'][0])
  ids_to_keep = select_ids_to_keep(files, folder_slugs)
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
  return files_to_keep

def select_ids_to_keep(files: list[dict[str, any]], folder_slugs: dict) -> list[str]:
  """Maticulously applies hand-crafted heuristics to select the keepers"""

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
      return [files[slugs.index(important_slugs[0])]['id']]

  #####
  # Don't trash any publicly-launched files
  #####
  file_permissions = batch_get_files_by_id([f['id'] for f in files], "id,name,permissions")
  are_publics = [any(p['type'] == 'anyone' for p in f['permissions']) for f in file_permissions]
  num_public = sum(are_publics)
  if num_public > 0:
    # Never suggest a public-facing file for deletion
    return [files[i]['id'] for i in range(len(files)) if are_publics[i]]
  
  #####
  # Discard files in "unimportant" subfolders first
  #####
  for prefix in UNIMPORTANT_PREFIXES:
    if prefix == "DhammaTalks":
      unreads = ['1NTIsr31uhBXymkFUu2coGU72vdCjwfNp' in [f['parent']['parents'][0], f['parents'][0]] for f in files]
    else:
      unreads = [f['parent']['name'].lower().startswith(prefix) for f in files]
    unread_count = sum(unreads)
    if unread_count > 0 and unread_count < len(files):
      files = [file for i, file in enumerate(files) if not unreads[i]]
      if len(files) == 1:
        return [files[0]['id']]
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
      return [files[0]['id']]
    
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
      return [file['id'] for file in files]
    # That failing, pick the eldest
    modifies = [file['modifiedTime'] for file in files]
    eldest = min(modifies)
    idx = modifies.index(eldest)
    return [files[idx]['id']]
  
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
  return [deepest['id']]

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
