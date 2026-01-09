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
except:
  print("pip install yaspin bs4")
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
)
import local_gdrive

FOLDERS_DATA_FILE = git_root_folder.joinpath("_data", "drive_folders.json")

gcache_folder = git_root_folder.joinpath("scripts/.gcache")
gcache = local_gdrive.DriveCache(gcache_folder.joinpath("drive.sqlite"))
gcache.update()
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

def has_file_already(file_in_question) -> bool:
  hash, _ = file_info(file_in_question)
  file_in_question = Path(file_in_question)
  cfs = gcache.get_items_with_md5(hash)
  if len(cfs) > 0:
    return True
  if len(file_in_question.name) > 16:
    cfs = gcache.files_exactly_named(file_in_question.name)
    if len(cfs) > 0:
      return True
    cfs = gcache.files_originally_named_exactly(file_in_question.name)
    if len(cfs) > 0:
      return True
  return False
