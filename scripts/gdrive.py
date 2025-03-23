#!/bin/python3

import os.path
from pathlib import Path
import requests
import socket
from math import floor
from io import BytesIO, BufferedIOBase
from strutils import (
  titlecase,
  git_root_folder,
  input_with_prefill,
  input_with_tab_complete,
  file_info,
  prompt,
  approx_eq,
  whitespace,
  yt_url_to_plid_re,
  yt_url_to_id_re,
)
import pdfutils
import json
import re
from functools import cache
from archivedotorg import archive_urls
try:
  import joblib
  from yaspin import yaspin
  from tqdm import tqdm
  from bs4 import BeautifulSoup
  from google.auth.transport.requests import Request
  from google.oauth2.credentials import Credentials
  from google_auth_oauthlib.flow import InstalledAppFlow
  from googleapiclient.discovery import build
  from googleapiclient.http import (
    MediaIoBaseUpload,
    MediaIoBaseDownload,
    MediaFileUpload,
    BatchHttpRequest,
  )
  from youtube_transcript_api import YouTubeTranscriptApi
except:
  print("pip install yaspin bs4 google google-api-python-client google_auth_oauthlib joblib youtube-transcript-api")
  exit(1)

# If modifying these scopes, have to login again.
SCOPES = [
  'https://www.googleapis.com/auth/drive',
  'https://www.googleapis.com/auth/youtube.readonly',
]
# The client secrets file can be made and downloaded from your developer console:
# https://console.developers.google.com/apis/credentials
CLIENTSECRETS = os.path.expanduser("~/library-utils-client-secret.json")
# This credentials file is created automatically by this script when the user logs in
CREDFILE = os.path.expanduser('~/gtoken.json')
FOLDERS_DATA_FILE = git_root_folder.joinpath("_data", "drive_folders.json")
FOLDER_LINK_PREFIX = "https://drive.google.com/drive/folders/"
FOLDER_LINK = FOLDER_LINK_PREFIX+"{}"
DRIVE_LINK = 'https://drive.google.com/file/d/{}/view?usp=drivesdk'
DOC_LINK = 'https://docs.google.com/document/d/{}/edit?usp=drivesdk'
GFIDREGEX = '([a-zA-Z0-9_-]{28}|[a-zA-Z0-9_-]{33}|[a-zA-Z0-9_-]{44})'
LINKIDREGEX = re.compile(rf'/d/{GFIDREGEX}/?(edit|view)?(\?usp=)?(sharing|drivesdk|drive_link|share_link)?(&|$)')
GFIDREGEX = re.compile(GFIDREGEX)

disk_memorizor = joblib.Memory(git_root_folder.joinpath("scripts/.gcache"), verbose=0)

def link_to_id(link):
  if not link:
    return None
  ret = GFIDREGEX.fullmatch(link)
  if ret:
    return ret.groups()[0]
  ret = LINKIDREGEX.search(link)
  if ret:
    return ret.groups()[0]
  ret = folderlink_to_id(link)
  if ret:
    return ret
  if link.startswith("https://drive.google.com/open?id="):
    return link[len("https://drive.google.com/open?id="):].split('&')[0]
  return None

def folderlink_to_id(link):
  if not link:
    return None
  if link.startswith(FOLDER_LINK_PREFIX):
    ret = link[len(FOLDER_LINK_PREFIX):]
    return ret.split('?')[0].split('/')[0]
  if link.startswith("https://drive.google.com/folderview?id="):
    return link[len("https://drive.google.com/folderview?id="):].split('&')[0]
  return None

def get_known_courses():
  gfolders = json.loads(FOLDERS_DATA_FILE.read_text())
  return list(filter(None, gfolders.keys()))

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
    with yaspin(text="Loading subfolders..."):
      subfolders = get_subfolders(private_folder)
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
      print("Okay, will just put in the private folder then.")
      return (None, private_folder)
    subfolder = create_folder(q, private_folder)
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

@cache
def google_credentials():
    creds = None
    if os.path.exists(CREDFILE):
        creds = Credentials.from_authorized_user_file(CREDFILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENTSECRETS):
              raise RuntimeError(f"{CLIENTSECRETS} does not exist.\nDownload it at https://console.developers.google.com/apis/credentials")
            flow = InstalledAppFlow.from_client_secrets_file(
              CLIENTSECRETS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(CREDFILE, 'w') as token:
            token.write(creds.to_json())
    return creds

@cache
def session():
    socket.setdefaulttimeout(300) # some of our uploads take a while...
    return build('drive', 'v3', credentials=google_credentials(), num_retries=5)

@cache
def youtube():
    return build('youtube', 'v3', credentials=google_credentials(), num_retries=3)

@cache
def docs():
  return build('docs', 'v1', credentials=google_credentials()).documents()

def get_ytvideo_snippets(ytids):
  snippets = []
  if len(ytids) > 50:
    for i in range(0, len(ytids), 50): # YTAPI has a 50 id limit
      snippets.extend(get_ytvideo_snippets(ytids[i:i+50]))
    return snippets
  data = youtube().videos().list(id=','.join(ytids),part="snippet,contentDetails").execute().get("items", [])
  for vid in data:
    ret = {k: vid['snippet'][k] for k in ['title', 'description', 'tags', 'thumbnails'] if k in vid['snippet']}
    ret['contentDetails'] = vid.get('contentDetails', {})
    if not ret.get('tags'):
      ret['tags'] = []
    ret['id'] = vid['id']
    snippets.append(ret)
  return snippets

def get_ytvideo_snippets_for_playlist(plid, maxResults=None, pageToken=None):
  if maxResults is None or maxResults < 1:
    maxResults = 0 # let 0 => Inf
    page_size = 50 # YouTube API has a max page size of 50
  else:
    page_size = min(50, maxResults)
  deets = youtube().playlistItems().list(
    playlistId=plid,
    part='snippet',
    maxResults=page_size,
    pageToken=pageToken,
  ).execute()
  ret = [e['snippet'] for e in deets.get("items",[])]
  if (maxResults == 0 or maxResults > 50) and deets.get("nextPageToken"):
    ret.extend(get_ytvideo_snippets_for_playlist(
      plid,
      maxResults=(maxResults-50),
      pageToken=deets.get('nextPageToken'),
    ))
  return ret

def get_ytplaylist_snippet(plid):
  deets = youtube().playlists().list(
    id=plid,
    part='snippet',
  ).execute()
  return deets['items'][0]['snippet']

@disk_memorizor.cache(cache_validation_callback=joblib.expires_after(days=28))
def get_subfolders(folderid):
  folderquery = f"'{folderid}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
  childrenFoldersDict = session().files().list(
    q=folderquery,
    spaces='drive',
    fields='files(id, name)'
  ).execute()
  return childrenFoldersDict['files']

def string_to_media(s, mimeType):
  return MediaIoBaseUpload(
    BytesIO(bytes(s, 'UTF-8')),
    mimetype=mimeType,
    resumable=True,
  )

def create_doc(filename=None, html=None, rtf=None, folder_id=None, creator=None, custom_properties: dict[str, str] = None, replace_doc=False):
  if bool(html) == bool(rtf):
    raise ValueError("Please specify either rtf OR html.")
  drive_service = session()
  metadata = {'mimeType': 'application/vnd.google-apps.document'}
  media = None
  if filename:
    metadata['name'] = filename
  if folder_id:
    metadata['parents'] = [folder_id]
  if custom_properties:
    metadata['properties'] = custom_properties
  else:
    metadata['properties'] = dict()
  if 'createdBy' not in metadata['properties']:
    metadata['properties']['createdBy'] = creator or 'LibraryUtils'
  if html:
    media = string_to_media(html, 'text/html')
  if rtf:
    media = string_to_media(rtf, 'application/rtf')
  return _perform_upload(metadata, media, verbose=False, update_file=replace_doc)

def get_file_contents(fileid, verbose=True):
  """Downloads and returns the contents of fileid in a BytesIO buffer"""
  buffer = BytesIO()
  download_file(fileid, buffer, verbose=verbose)
  return buffer
  
def download_file(fileid, destination: Path | str | BufferedIOBase, verbose=True):
  """Downloads the contents of the file to destination"""
  if isinstance(destination, BufferedIOBase):
    buffer = destination
  else:
    if os.path.exists(str(destination)):
      if verbose is True:
        if prompt(f"File {destination} already exists. Overwrite?"):
          os.remove(str(destination))
        else:
          return
      else:
        raise FileExistsError(f"Attempting to download {destination} which already exists")
    buffer = open(str(destination)+'.part', 'wb')
  request = session().files().get_media(fileId=fileid)
  downloader = MediaIoBaseDownload(buffer, request, chunksize=1048576)
  yet = False
  if verbose is True:
      print(f"Downloading {fileid}")
  prev = 0
  while not yet:
    status, yet = downloader.next_chunk(3)
    if verbose is not False:
      if isinstance(verbose, tqdm):
        cur = status.resumable_progress
        verbose.update(cur - prev)
        prev = cur
      else:
        print(f"Downloading {fileid} {status.progress()*100:.1f}% complete")
  if not isinstance(destination, BufferedIOBase):
    buffer.close()
    Path(str(destination)+'.part').rename(destination)

def upload_to_google_drive(file_path, creator=None, filename=None, folder_id=None, custom_properties: dict[str,str] = None, verbose=True):
    file_metadata = {'name': (filename or os.path.basename(file_path))}
    if folder_id:
        file_metadata['parents'] = [folder_id]
    file_metadata['properties'] = custom_properties or dict()
    file_metadata['properties']['createdBy'] = creator or 'LibraryUtils'
    media = MediaFileUpload(file_path, resumable=True)
    return _perform_upload(file_metadata, media, verbose=verbose)

def _perform_upload(file_metadata, media, verbose=True, update_file=False):
    drive_service = session()
    try:
        # Upload the file
        request = None
        if update_file:
          request = drive_service.files().update(fileId=update_file, body=file_metadata, media_body=media)
        else:
          request = drive_service.files().create(body=file_metadata, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status and verbose:
                print("Uploaded %d%%." % int(status.progress() * 100))
        if verbose:
          print("File uploaded successfully:")
          print(response)
        return response['id']
    except Exception as e:
        print("An error occurred: ", str(e))
        return False

def create_folder(name, parent_folder, custom_properties: dict[str, str] = None):
  # dance to invalidate the get_subfolders cache
  cachekey = get_subfolders._get_args_id(parent_folder)
  get_subfolders.store_backend.clear_item((get_subfolders.func_id, cachekey))
  metadata = {
    'name': name,
    'mimeType': 'application/vnd.google-apps.folder',
    'parents': [parent_folder]
  }
  if custom_properties:
    metadata['properties'] = custom_properties
  ret = session().files().create(
    body=metadata,
    fields='id'
  ).execute()
  return ret.get('id')

def create_drive_shortcut(gfid, filename, folder_id, custom_properties: dict[str, str] = None):
  drive_service = session()
  shortcut_metadata = {
       'name': filename,
       'mimeType': 'application/vnd.google-apps.shortcut',
       'shortcutDetails': {
          'targetId': gfid
       },
       'parents': [folder_id]
  }
  if custom_properties:
    shortcut_metadata['properties'] = custom_properties
  shortcut = drive_service.files().create(
    body=shortcut_metadata,
    fields='id,shortcutDetails'
  ).execute()
  return shortcut.get('id')

def deref_possible_shortcut(gfid):
  """Returns the id of what gfid is pointing to OR gfid"""
  service = session()
  res = service.files().get(fileId=gfid, fields="shortcutDetails").execute()
  if "shortcutDetails" in res:
    return res["shortcutDetails"]["targetId"]
  return gfid

def move_drive_file(file_id, folder_id, previous_parents=None, verbose=True):
  service = session()
  if previous_parents is None:
    # pylint: disable=maybe-no-member
    file = service.files().get(fileId=file_id, fields='parents').execute()
    previous_parents = file.get('parents')
  if type(previous_parents) is list:
    previous_parents = ",".join(previous_parents)
  if verbose:
    print(f"Moving {file_id} from [{previous_parents}] to [{folder_id}]...")
  file = service.files().update(
    fileId=file_id,
    addParents=folder_id,
    removeParents=previous_parents,
    fields='id, parents, name').execute()
  if verbose:
    print(f"  \"{file.get('name')}\" moved to {file.get('parents')}")
  return file

def has_file_matching(query: str):
  resp = session().files().list(
    q=query,
    pageSize=1,
    fields='files(id)',
  ).execute()
  resp = resp.get('files')
  if not resp:
    return None
  return resp[0]['id']

def all_files_matching(query: str, fields: str):
  files = session().files()
  fields = f"files({fields}),nextPageToken"
  params = {
    'q': query,
    'fields': fields,
    'pageSize': 100,
    'orderBy': "createdTime", # go in chronological order by default
  }
  retries = 0
  results = None
  while not results:
    try:
      results = files.list(**params).execute()
    except Exception as e:
      print(f"Error fetching all_files_matching: {e}")
      if retries < 5:
        retries += 1
        print(f"Retrying ({retries})...")
        continue
      else:
        raise
  for item in results.get('files', []):
    yield item
  while 'nextPageToken' in results:
    params['pageToken'] = results['nextPageToken']
    try:
      results = files.list(**params).execute()
    except Exception as e:
      print(f"Error fetching all_files_matching: {e}")
      if retries < 5:
        retries += 1
        print(f"Retrying ({retries})...")
        continue
      else:
        raise
    if retries > 0:
      retries = 0
      print("Success!")
    for item in results.get('files', []):
      yield item

def download_folder_contents_to(gdfid: str, target_directory: Path | str, recursive=False, follow_links=False):
  target_directory = Path(target_directory)
  target_directory.mkdir(exist_ok=True)
  total_size = 0
  subfolders = []
  linked_files = []
  downloads = []
  with yaspin(text="Loading file list..."):
    for child in all_files_matching(
      f"'{gdfid}' in parents and trashed=false",
      "size,name,id,mimeType,shortcutDetails"
    ):
      childpath = target_directory.joinpath(child['name'])
      if child['mimeType'] == 'application/vnd.google-apps.shortcut':
        if not follow_links:
          continue
        if child['shortcutDetails']['targetMimeType'] == 'application/vnd.google-apps.folder':
          if recursive:
            subfolders.append((child['shortcutDetails']['targetId'], childpath))
        else:
          linked_files.append(child['shortcutDetails']['targetId'])
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
      total_size += size
      downloads.append((child['id'], childpath))
    if linked_files:
      for child in batch_get_files_by_id(linked_files, "size,id,name"):
        size = int(child.get('size',0))
        if size:
          total_size += size
          downloads.append((child['id'], target_directory.joinpath(child['name'])))
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

def share_drive_file_with_everyone(file_id: str):
  return session().permissions().create(
    fileId=file_id,
    body={"role": "reader", "type": "anyone"},
  ).execute()

def batch_get_files_by_id(IDs: list, fields: str):
  ret = []
  if len(IDs) > 100:
    for i in range(0, len(IDs), 100):
      ret.extend(batch_get_files_by_id(IDs[i:i+100],fields))
    return ret
  def _getter_callback(rid, resp, error):
    if error:
      print(f"Warning! Failed to `get` fileId={rid}")
    else:
      ret.append(resp)
  batcher = BatchHttpRequest(
    callback=_getter_callback,
    batch_uri="https://www.googleapis.com/batch/drive/v3",
  )
  for fid in IDs:
    request = session().files().get(fileId=fid, fields=fields)
    batcher.add(request_id=fid, request=request)
  batcher.execute()
  return ret

def ensure_these_are_shared_with_everyone(file_ids: list[str]):
  all_files = batch_get_files_by_id(file_ids, "id,name,permissions")
  for file in all_files:
    if 'permissions' not in file:
      print(f"  Skipping {file['id']} ({file['name']}) because I can't change its permissions...")
      continue
    is_publicly_shared = False
    for permission in file['permissions']:
      if permission['type'] == 'anyone':
        is_publicly_shared = True
        break
    if not is_publicly_shared:
      print(f"Sharing \"{file['name']}\" with everyone...")
      share_drive_file_with_everyone(file['id'])

EXACT_MATCH_FIELDS = "files(id,mimeType,name,md5Checksum,originalFilename,size,parents)"

def files_exactly_named(file_name):
  f = file_name.replace("'", "\\'")
  return session().files().list(
    q=f"name='{f}' AND 'me' in owners AND mimeType!='application/vnd.google-apps.shortcut' AND trashed=false",
    fields=EXACT_MATCH_FIELDS,
  ).execute()['files']

def my_pdfs_containing(text):
  text = text.replace("'", "\\'")
  return session().files().list(
    q=f"fullText contains '{text}' AND 'me' in owners AND mimeType='application/pdf'",
    fields=EXACT_MATCH_FIELDS,
  ).execute()['files']

def has_file_already(file_in_question, default="prompt") -> bool:
  hash, size = file_info(file_in_question)
  file_in_question = Path(file_in_question)
  cfs = files_exactly_named(file_in_question.name)
  for gf in cfs:
    if hash == gf['md5Checksum'] or (approx_eq(size, int(gf['size']), absdiff=1024, percent=2.0) or len(gf['name']) > 11):
      return True
    else:
      if default=="prompt":
        print(f"  Found file with that name sized {gf['size']} instead of {size}.")
        if prompt("Consider that a match?"):
          return True
      else:
        if default:
          return True
  if file_in_question.suffix == ".pdf":
    try:
      text = pdfutils.readpdf(file_in_question, max_len=1500, normalize=3)
    except:
      text = ""
    if len(text) < 16:
      # failed to extract text from the PDF
      return False
    cfs = my_pdfs_containing(text)
    for gf in cfs:
        if hash == gf['md5Checksum'] or approx_eq(size, int(gf['size']), absdiff=512):
            return True
        if gf['originalFilename'] == file_in_question.name:
          if approx_eq(size, int(gf['size']), percent=5.0) and len(gf['originalFilename']) > 7:
            return True
          if default=="prompt":
            print(f"  Found a file now named {gf['name']} sized {gf['size']} instead of {size}.")
            if prompt("Consider that a match?"):
              return True
          else:
            if default:
              return True
    if len(cfs) == 1 and default == "prompt":
      gf = cfs[0]
      print(f"  Found file \"{gf['name']}\" with that text sized {gf['size']} instead of {size}.")
      if prompt("Consider that a match?"):
        return True
    if len(cfs) > 1 and default=="prompt":
      print(f"  Found {len(cfs)} fuzzy matches:")
      for gf in cfs:
        print(f"    {gf['name']}")
      if prompt("Are any of those a match?"):
          return True
  return False

def get_shortcuts_to_gfile(target_id):
  # note the following assumes only one page of results
  # if you are expecting >100 results
  # please implement paging when calling files.list
  return session().files().list(q=f"shortcutDetails.targetId='{target_id}' and trashed=false", spaces='drive', fields='files(id,name,parents)').execute()['files']

def trash_drive_file(target_id):
  return session().files().update(fileId=target_id, body={"trashed": True}).execute()

def move_gfile(glink, folders):
  gfid = link_to_id(glink)
  public_fid, private_fid = folders
  file = move_drive_file(gfid, public_fid or private_fid)
  shortcuts = get_shortcuts_to_gfile(gfid)
  if public_fid and private_fid:
    if len(shortcuts) != 1:
      print("Creating a (new, private) shortcut...")
      create_drive_shortcut(gfid, file.get('name'), private_fid)
    else:
      s=shortcuts[0]
      print(f"Moving existing shortcut from  {FOLDER_LINK.format(s['parents'][0])}  to  {FOLDER_LINK.format(private_fid)}  ...")
      move_drive_file(s['id'], private_fid, previous_parents=s['parents'])
  else:
    if len(shortcuts) == 1:
      s=shortcuts[0]
      print(f"Trashing the existing shortcut in {FOLDER_LINK.format(s['parents'][0])} ...")
      trash_drive_file(s['id'])
  if len(shortcuts)>1:
    urls = "     ".join(map(lambda f: FOLDER_LINK.format(f['parents'][0]), shortcuts))
    raise NotImplementedError(f"Please decide what to do with the multiple old shortcuts in:    {urls}")
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

def htmlify_ytdesc(description):
  return description.replace('\n\n', '<br /').replace('\n', '<br />')

def _yt_thumbnail(snippet):
  if 'high' in snippet['thumbnails']:
    return snippet['thumbnails']['high']['url']
  if 'default' in snippet['thumbnails']:
    return snippet['thumbnails']['default']['url']
  return ''

def make_ytvideo_summary_html(vid):
  from tag_predictor import YOUTUBE_DATA_FOLDER
  cachef = YOUTUBE_DATA_FOLDER.joinpath(f"{vid}.json")
  if cachef.exists():
    snippet = json.loads(cachef.read_text())
    transcript = snippet.get('transcript',[])
  else:
    snippet = get_ytvideo_snippets([vid])[0]
    transcript = None
    try:
      transcript = YouTubeTranscriptApi.get_transcript(vid)
      snippet['transcript'] = transcript
    except:
      pass
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
  if snippet.get('description'):
    desc = htmlify_ytdesc(snippet['description'])
    ret += f"""<h2>Video Description (from YouTube)</h2><p>{desc}</p>"""
  ret += f"""<h2>Thumbnail</h2><p><img src="{_yt_thumbnail(snippet)}" /></p>"""
  if len(snippet.get('tags',[])) > 0:
    ret += f"""<h2>Video Tags</h2><p>{snippet['tags']}</p>"""
  if transcript:
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
  course = input_with_tab_complete("course: ", get_known_courses())
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
