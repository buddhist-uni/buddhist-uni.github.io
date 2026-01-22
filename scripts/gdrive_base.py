#!/bin/python3

import os.path
from pathlib import Path
import socket
from datetime import datetime, timezone
from time import sleep
from io import BytesIO, BufferedIOBase
from strutils import (
  file_info,
  prompt,
)
import re
from functools import cache
try:
  from yaspin import yaspin
  from tqdm import tqdm
  from tqdm.contrib.concurrent import thread_map as tqdm_thread_map
  from google.auth.transport.requests import Request
  from google.oauth2.credentials import Credentials
  from google_auth_oauthlib.flow import InstalledAppFlow
  from googleapiclient.discovery import build
  from googleapiclient.http import (
    MediaIoBaseUpload,
    MediaIoBaseDownload,
    MediaFileUpload,
    BatchHttpRequest,
    HttpError,
  )
  from youtube_transcript_api import YouTubeTranscriptApi
  from youtube_transcript_api import _errors as YouTubeTranscriptErrors
except:
  print("pip install yaspin google google-api-python-client google_auth_oauthlib youtube-transcript-api")
  exit(1)

# Override these three global variables before calling anything
# if your scopes, secrets or credfile locations need to be customized
SCOPES = [
  'https://www.googleapis.com/auth/drive',
  'https://www.googleapis.com/auth/youtube.readonly',
]
# The client secrets file can be made and downloaded from your developer console:
# https://console.developers.google.com/apis/credentials
CLIENTSECRETS = os.path.expanduser("~/library-utils-client-secret.json")
# This credentials file is created automatically by this script when the user logs in
CREDFILE = os.path.expanduser('~/gtoken.json')


FOLDER_LINK_PREFIX = "https://drive.google.com/drive/folders/"
FOLDER_LINK = FOLDER_LINK_PREFIX+"{}"
DRIVE_LINK = 'https://drive.google.com/file/d/{}/view?usp=drivesdk'
DOC_LINK = 'https://docs.google.com/document/d/{}/edit?usp=drivesdk'
GFIDREGEX = '([a-zA-Z0-9_-]{28}|[a-zA-Z0-9_-]{33}|[a-zA-Z0-9_-]{44})'
LINKIDREGEX = re.compile(rf'/d/{GFIDREGEX}/?(edit|view)?(\?usp=)?(sharing|drivesdk|drive_link|share_link)?(&|$)')
GFIDREGEX = re.compile(GFIDREGEX)

YTTranscriptAPI = None # Initialized on-demand below

def execute(gapicall, retries=4, backoff=1):
  try:
    return gapicall.execute()
  except (HttpError, socket.error, socket.timeout, ConnectionError) as e:
    if retries <= 0:
      raise e
    print(e)
    print(f"Retrying in {backoff}s...")
    sleep(backoff)
    return execute(gapicall, retries=retries-1, backoff=backoff*2)

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

# Don't cache the session service as this object is not thread-safe
def session():
    socket.setdefaulttimeout(300) # some of our uploads take a while...
    return build('drive', 'v3', credentials=google_credentials(), num_retries=4) # only retries 429s natively. See execute() for retrying other errors

# If you ever want to use the docs or youtube services in a multithreaded context, go ahead and uncache this
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
  data = execute(youtube().videos().list(id=','.join(ytids),part="snippet,contentDetails")).get("items", [])
  for vid in data:
    ret = {k: vid['snippet'][k] for k in ['title', 'description', 'tags', 'thumbnails', 'publishedAt'] if k in vid['snippet']}
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
  deets = execute(youtube().playlistItems().list(
    playlistId=plid,
    part='snippet',
    maxResults=page_size,
    pageToken=pageToken,
  ))
  ret = [e['snippet'] for e in deets.get("items",[])]
  if (maxResults == 0 or maxResults > 50) and deets.get("nextPageToken"):
    ret.extend(get_ytvideo_snippets_for_playlist(
      plid,
      maxResults=(maxResults-50),
      pageToken=deets.get('nextPageToken'),
    ))
  return ret

def get_ytplaylist_snippet(plid):
  deets = execute(youtube().playlists().list(
    id=plid,
    part='snippet',
  ))
  return deets['items'][0]['snippet']

def get_subfolders(folderid):
  folderquery = f"'{folderid}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
  childrenFoldersDict = execute(session().files().list(
    q=folderquery,
    spaces='drive',
    fields='files(id, name)'
  ))
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
  if 'createdBy' not in metadata['properties'] and creator:
    metadata['properties']['createdBy'] = creator
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
        raise FileExistsError(f"Attempting to download {fileid} to \"{destination}\" which already exists")
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
    if verbose:
      print(f"Uploading {file_path.name}...")
    file_metadata = {'name': (filename or os.path.basename(file_path))}
    if folder_id:
        file_metadata['parents'] = [folder_id]
    file_metadata['properties'] = custom_properties or dict()
    if creator:
        file_metadata['properties']['createdBy'] = creator
    media = MediaFileUpload(file_path, resumable=True)
    return _perform_upload(file_metadata, media, verbose=verbose)

def rename_file(file_id: str, new_name: str):
  execute(session().files().update(
    fileId=file_id,
    body={'name': new_name},
  ))

def _perform_upload(file_metadata, media, verbose=True, update_file=False):
    try:
        # Upload the file
        request = None
        if update_file:
          request = session().files().update(fileId=update_file, body=file_metadata, media_body=media)
        else:
          request = session().files().create(body=file_metadata, media_body=media)
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

def create_folder(name, parent_folder, custom_properties: dict[str, str] = None) -> str:
  metadata = {
    'name': name,
    'mimeType': 'application/vnd.google-apps.folder',
    'parents': [parent_folder]
  }
  if custom_properties:
    metadata['properties'] = custom_properties
  ret = execute(session().files().create(
    body=metadata,
    fields='id'
  ))
  return ret.get('id')

def create_drive_shortcut(gfid, filename, folder_id, custom_properties: dict[str, str] = None):
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
    
  shortcut = execute(session().files().create(
    body=shortcut_metadata,
    fields='id,shortcutDetails'
  ))
  return shortcut.get('id')

def deref_possible_shortcut(gfid):
  """Returns the id of what gfid is pointing to OR gfid"""
  service = session()
  res = execute(service.files().get(fileId=gfid, fields="shortcutDetails"))
  if "shortcutDetails" in res:
    return res["shortcutDetails"]["targetId"]
  return gfid

def move_drive_file(file_id, folder_id, previous_parents=None, verbose=True):
  service = session()
  if previous_parents is None:
    # pylint: disable=maybe-no-member
    file = execute(service.files().get(fileId=file_id, fields='parents'))
    previous_parents = file.get('parents')
  if type(previous_parents) is list:
    previous_parents = ",".join(previous_parents)
  if verbose:
    print(f"Moving {file_id} from [{previous_parents}] to [{folder_id}]...")
  file = execute(service.files().update(
    fileId=file_id,
    addParents=folder_id,
    removeParents=previous_parents,
    fields='id, parents, name'))
  if verbose:
    print(f"  \"{file.get('name')}\" moved to {file.get('parents')}")
  return file

def has_file_matching(query: str):
  resp = execute(session().files().list(
    q=query,
    pageSize=1,
    fields='files(id)',
  ))
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
      results = execute(files.list(**params))
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
      results = execute(files.list(**params))
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

def upload_folder_contents_to(local_directory: Path | str, gdfid: str, recursive=False, replace_all=False, parallelism=8):
  if recursive:
    raise NotImplementedError("Teach gdrive_base.upload_folder_contents_to to handle recursion")
  local_directory = Path(local_directory)
  if not local_directory.is_dir():
    raise ValueError(f"{local_directory} is not a directory")
  local_files = dict()
  upload_jobs = [] # a tuple of (local_filepath, existing_id, size)
  total_size = 0
  with yaspin(text="Loading local file list...") as ys:
    for child in local_directory.iterdir():
      if child.is_dir():
        continue # TODO: Handle recursion
      s_obj = child.stat()
      info = {k: getattr(s_obj, k) for k in dir(s_obj) if k.startswith('st_')}
      info['md5'] = file_info(child)[0]
      local_files[child] = info
  with yaspin(text="Loading remote file list...") as ys:
    for child in all_files_matching(
      f"'{gdfid}' in parents and trashed=false",
      "size,name,id,mimeType,md5Checksum,modifiedTime"
    ):
      local_filepath = local_directory.joinpath(child['name'])
      if child['mimeType'] == 'application/vnd.google-apps.shortcut':
        continue # This uploader (for now) ignores existing links
      if child['mimeType'] == 'application/vnd.google-apps.folder':
        continue # TODO: Handle recursion
      if local_filepath not in local_files:
        continue # Just ignore files that we don't have
      if local_files[local_filepath]['md5'] == child['md5Checksum']:
        del local_files[local_filepath] # no need to upload this one
        continue
      if not replace_all:
        local_mtime = datetime.fromtimestamp(local_files[local_filepath]['st_mtime'], timezone.utc)
        remote_mtime = datetime.fromisoformat(child['modifiedTime'].replace('Z', "+00:00"))
        if local_mtime < remote_mtime:
          ys.write(f"Warning: not uploading {local_filepath.relative_to(local_directory)} as the remote version seems newer? Pass `replace_all=True` to override.")
          del local_files[local_filepath]
          continue
      size = local_files[local_filepath]['st_size']
      upload_jobs.append(
        (local_filepath, child['id'], size)
      )
      total_size += size
      del local_files[local_filepath]
  with yaspin(text="Loading upload file list..."):
    for local_filepath, stats in local_files.items():
      upload_jobs.append(
        (local_filepath, None, stats['st_size'])
      )
      total_size += stats['st_size']
  print(f"Uploading {len(upload_jobs)} files to Google Drive:")
  def _upload_job(args: tuple):
    local_filepath, existing_id, size = args
    if existing_id:
      execute(session().files().update(
        fileId=existing_id,
        body={}, # We're keeping the file name, etc the same
        media_body=MediaFileUpload(local_filepath, resumable=True),
      ))
    else:
      execute(session().files().create(
        body={
          'name': local_filepath.name,
          'parents': [gdfid], # TODO: Handle recursion,
          'properties': {'createdBy': 'LibraryUtils'},
        },
        media_body=MediaFileUpload(local_filepath, resumable=True),
      ))
  tqdm_thread_map(
    _upload_job,
    upload_jobs,
    max_workers=parallelism,
  )

def download_folder_contents_to(gdfid: str, target_directory: Path | str, recursive=False, follow_links=False):
  target_directory = Path(target_directory)
  target_directory.mkdir(exist_ok=True)
  total_size = 0
  subfolders = []
  linked_files = []
  downloads = []
  with yaspin(text="Loading file list...") as ys:
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
      if any(d[1] == childpath for d in downloads):
        ys.write(f"WARNING: Skipping duplicate file \"{childpath}\"")
        continue
      total_size += size
      downloads.append((child['id'], childpath))
    if linked_files:
      for child in batch_get_files_by_id(linked_files, "size,id,name"):
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

def share_drive_file_with_everyone(file_id: str):
  return execute(session().permissions().create(
    fileId=file_id,
    body={"role": "reader", "type": "anyone"},
  ))

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

def ensure_these_are_shared_with_everyone(file_ids: list[str], verbose=True):
  all_files = batch_get_files_by_id(file_ids, "id,name,permissions")
  count = 0
  if not verbose:
    all_files = tqdm(all_files, unit='files', total=len(file_ids))
  for file in all_files:
    if 'permissions' not in file:
      if verbose:
        print(f"  Skipping {file['id']} ({file['name']}) because I can't change its permissions...")
      continue
    is_publicly_shared = False
    for permission in file['permissions']:
      if permission['type'] == 'anyone':
        is_publicly_shared = True
        break
    if not is_publicly_shared:
      if verbose:
        print(f"Sharing \"{file['name']}\" with everyone...")
      share_drive_file_with_everyone(file['id'])
      count += 1
  return count

EXACT_MATCH_FIELDS = "files(id,mimeType,name,md5Checksum,originalFilename,size,parents)"

def files_exactly_named(file_name):
  f = file_name.replace("'", "\\'")
  return execute(session().files().list(
    q=f"name='{f}' AND 'me' in owners AND mimeType!='application/vnd.google-apps.shortcut' AND trashed=false",
    fields=EXACT_MATCH_FIELDS,
  ))['files']

def my_pdfs_containing(text):
  text = text.replace("'", "\\'")
  return execute(session().files().list(
    q=f"fullText contains '{text}' AND 'me' in owners AND mimeType='application/pdf'",
    fields=EXACT_MATCH_FIELDS,
  ))['files']

def get_shortcuts_to_gfile(target_id):
  # note the following assumes only one page of results
  # if you are expecting >100 results
  # please implement paging when calling files.list
  return execute(session().files().list(q=f"shortcutDetails.targetId='{target_id}' and trashed=false", spaces='drive', fields='files(id,name,parents)'))['files']

def trash_drive_file(target_id):
  return execute(session().files().update(fileId=target_id, body={"trashed": True}))

def htmlify_ytdesc(description):
  return description.replace('\n\n', '<br /').replace('\n', '<br />')

def _yt_thumbnail(snippet):
  if 'high' in snippet['thumbnails']:
    return snippet['thumbnails']['high']['url']
  if 'default' in snippet['thumbnails']:
    return snippet['thumbnails']['default']['url']
  return ''

def fetch_youtube_transcript(vid):
  """Returns a list of {"text": "", "start": 0, "duration": 0}s OR a string if subtitles are unavailable for that video"""
  global YTTranscriptAPI
  if not YTTranscriptAPI:
    YTTranscriptAPI = YouTubeTranscriptApi()
  try:
    transcripts_available = YTTranscriptAPI.list(vid)
    transcript = transcripts_available.find_transcript(('en',))
    ret = transcript.fetch()
  except (YouTubeTranscriptErrors.TranscriptsDisabled, YouTubeTranscriptErrors.VideoUnplayable, YouTubeTranscriptErrors.VideoUnavailable):
    return "disabled"
  except (YouTubeTranscriptErrors.AgeRestricted, YouTubeTranscriptErrors.PoTokenRequired):
    return "restricted"
  except YouTubeTranscriptErrors.NoTranscriptFound:
    if transcripts_available:
      for transcript in transcripts_available:
        if transcript.is_translatable: # The API doesn't pull translations automatically
          if any(tlang.language_code == 'en' for tlang in transcript.translation_languages):
            try:
              # Currently the translate API is broken
              # return transcript.translate('en').fetch().to_raw_data()
              return "foreign"
            except YouTubeTranscriptErrors.CouldNotRetrieveTranscript as e:
              print(f"Warning ({vid}): {e.cause}")
              return []
    return "disabled"
  except YouTubeTranscriptErrors.CouldNotRetrieveTranscript as e:
    print(f"Warning ({vid}): {e.cause}")
    return []
  return ret.to_raw_data()

def fetch_youtube_transcripts(vids):
  """Returns a dict mapping vid to the transcript list (see above)"""
  ret = dict()
  # Just a simple loop for now
  # Might get fancy with threading later...
  for vid in vids:
    t = fetch_youtube_transcript(vid)
    ret[vid] = t
  return ret
