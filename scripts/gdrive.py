#!/bin/python3

import os.path
from pathlib import Path
import requests
from io import BytesIO
from strutils import (
  titlecase,
  git_root_folder,
  system_open,
  input_with_prefill,
  input_with_tab_complete
)
import json
import re
from functools import cache
try:
  from yaspin import yaspin
  from bs4 import BeautifulSoup
  from google.auth.transport.requests import Request
  from google.oauth2.credentials import Credentials
  from google_auth_oauthlib.flow import InstalledAppFlow
  from googleapiclient.discovery import build
  from googleapiclient.http import MediaIoBaseUpload, MediaFileUpload
except:
  print("pip install yaspin bs4 google google-api-python-client google_auth_oauthlib")
  quit(1)

# If modifying these scopes, have to login again.
SCOPES = ['https://www.googleapis.com/auth/drive','https://www.googleapis.com/auth/youtube.readonly']
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

def link_to_id(link):
  ret = re.search(r'/d/([a-zA-Z0-9_-]{33}|[a-zA-Z0-9_-]{44})/?(edit|view)?(\?usp=)?(sharing|drivesdk)?$', link)
  return ret.groups()[0] if ret else None

def folderlink_to_id(link):
  return link if not link else link.replace(FOLDER_LINK_PREFIX, "")

def get_known_courses():
  gfolders = json.loads(FOLDERS_DATA_FILE.read_text())
  return list(filter(None, gfolders.keys()))

def get_gfolders_for_course(course):
  """Returns a (public, private) tuple of GIDs"""
  gfolders = json.loads(FOLDERS_DATA_FILE.read_text())
  parts = course.split('/')
  course = parts[0]
  if course not in gfolders:
    print("Hmmm... I don't know that Google Drive folder! Let's add it:")
    publicurl = input("Public link: ") or None
    privateurl = input("Private link: ") or None
    gfolders[course] = {"public":publicurl,"private":privateurl}
    FOLDERS_DATA_FILE.write_text(json.dumps(gfolders, sort_keys=True, indent=1))
  
  private_folder = folderlink_to_id(gfolders[course]['private'])
  public_folder = folderlink_to_id(gfolders[course]['public'])
  if len(parts) > 1:
    if not parts[1]: # use "course/" syntax to move to the private version of the course
      return (None, private_folder)
    with yaspin(text="Loading subfolders..."):
      subfolders = get_subfolders(private_folder)
    print(f"Got subfolders: {[f.get('name') for f in subfolders]}")
    q = parts[1].lower()
    for subfolder in subfolders:
      if subfolder['name'].lower().startswith(q):
        print(f"Going with \"{subfolder['name']}\"")
        return (None, subfolder['id'])
    for subfolder in subfolders:
      if q in subfolder['name'].lower():
        print(f"Going with \"{subfolder['name']}\"")
        return (None, subfolder['id'])
    print(f"No subfolder found matching \"{q}\"")
    q = input_with_prefill("Create new subfolder: ", titlecase(parts[1]))
    if not q:
      print("Okay, will just put in the private folder then.")
      return (None, private_folder)
    subfolder = create_folder(q, private_folder)
    if not subfolder:
      raise RuntimeError("Error creating subfolder. Got null API response.")
    # system_open(FOLDER_LINK.format(private_folder))
    # input("Press enter to continue...")
    return (None, subfolder)
  return (public_folder, private_folder)

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
              raise RuntimeError(f"{CLIENTSECRETS} does not exist.")
            flow = InstalledAppFlow.from_client_secrets_file(
              CLIENTSECRETS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(CREDFILE, 'w') as token:
            token.write(creds.to_json())
    return creds

@cache
def session():
    return build('drive', 'v3', credentials=google_credentials())

@cache
def youtube():
    return build('youtube', 'v3', credentials=google_credentials())

def get_ytvideo_snippet(ytid):
  return youtube().videos().list(id=ytid,part="snippet").execute().get("items")[0].get("snippet")

def get_subfolders(folderid):
  folderquery = f"'{folderid}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
  childrenFoldersDict = session().files().list(
    q=folderquery,
    spaces='drive',
    fields='files(id, name)'
  ).execute()
  return childrenFoldersDict['files']

def create_doc(filename=None, html=None, rtf=None, folder_id=None):
  if html and rtf:
    raise ValueError("Please specify either rtf or html. Not both.")
  drive_service = session()
  metadata = {'mimeType': 'application/vnd.google-apps.document'}
  media = None
  if filename:
    metadata['name'] = filename
  if folder_id:
    metadata['parents'] = [folder_id]
  if html:
    media = MediaIoBaseUpload(BytesIO(bytes(html, 'UTF-8')), mimetype='text/html', resumable=True)
  if rtf:
    media = MediaIoBaseUpload(BytesIO(bytes(rtf, 'UTF-8')), mimetype='application/rtf', resumable=True)
  return _perform_upload(metadata, media)

def upload_to_google_drive(file_path, filename=None, folder_id=None):
    file_metadata = {'name': (filename or os.path.basename(file_path))}
    if folder_id:
        file_metadata['parents'] = [folder_id]
    media = MediaFileUpload(file_path, resumable=True)
    return _perform_upload(file_metadata, media)

def _perform_upload(file_metadata, media):
    drive_service = session()
    try:
        # Upload the file
        request = drive_service.files().create(body=file_metadata, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print("Uploaded %d%%." % int(status.progress() * 100))

        print("File uploaded successfully:")
        print(response)
        return response['id']
    except Exception as e:
        print("An error occurred: ", str(e))
        return False

def create_folder(name, parent_folder):
  metadata = {
    'name': name,
    'mimeType': 'application/vnd.google-apps.folder',
    'parents': [parent_folder]
  }
  ret = session().files().create(
    body=metadata,
    fields='id'
  ).execute()
  return ret.get('id')

def create_drive_shortcut(gfid, filename, folder_id):
  drive_service = session()
  shortcut_metadata = {
       'name': filename,
       'mimeType': 'application/vnd.google-apps.shortcut',
       'shortcutDetails': {
          'targetId': gfid
       },
       'parents': [folder_id]
  }
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

def move_drive_file(file_id, folder_id, previous_parents=None):
  service = session()
  if previous_parents is None:
    # pylint: disable=maybe-no-member
    file = service.files().get(fileId=file_id, fields='parents').execute()
    previous_parents = file.get('parents')
  if type(previous_parents) is list:
    previous_parents = ",".join(previous_parents)
  print(f"Moving {file_id} from [{previous_parents}] to [{folder_id}]...")
  file = service.files().update(
    fileId=file_id,
    addParents=folder_id,
    removeParents=previous_parents,
    fields='id, parents, name').execute()
  print(f"  \"{file.get('name')}\" moved to {file.get('parents')}")
  return file

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

if __name__ == "__main__":
  glink_gens = []
  # a list of generator lambdas not direct links
  # so that we can defer doc creation to the end
  while True:
    link = input("Link (None to continue): ")
    if not link:
      break
    if not link_to_id(link):
      if "youtu" in link:
        link = link.split("?si=")[0]
      title = input_with_prefill("title: ", guess_link_title(link))
      glink_gens.append(lambda title=title, link=link: DOC_LINK.format(create_doc(title, html=f"""<h2>{title}</h2><a href="{link}">{link}</a>""")))
    else:
      glink_gens.append(lambda r=link: r)
  course = input_with_tab_complete("course: ", get_known_courses())
  folders = get_gfolders_for_course(course)
  for glink_gen in glink_gens:
    move_gfile(glink_gen(), folders)
