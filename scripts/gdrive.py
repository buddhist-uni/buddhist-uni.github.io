#!/bin/python3

import os.path
from pathlib import Path
from strutils import (
  git_root_folder,
  input_with_tab_complete
)
import json
import re
from functools import cache
try:
  from google.auth.transport.requests import Request
  from google.oauth2.credentials import Credentials
  from google_auth_oauthlib.flow import InstalledAppFlow
  from googleapiclient.discovery import build
  from googleapiclient.http import MediaFileUpload
except:
  print("pip install google google-api-python-client google_auth_oauthlib")
  quit(1)

# If modifying these scopes, have to redo the client secrets json.
SCOPES = ['https://www.googleapis.com/auth/drive']
# The client secrets file can be made and downloaded from your developer console:
# https://console.developers.google.com/apis/credentials
CLIENTSECRETS = os.path.expanduser("~/library-utils-client-secret.json")
# This credentials file is created automatically by this script when the user logs in
CREDFILE = os.path.expanduser('~/gtoken.json')
FOLDERS_DATA_FILE = git_root_folder.joinpath("_data", "drive_folders.json")
FOLDER_LINK_PREFIX = "https://drive.google.com/drive/folders/"
FOLDER_LINK = FOLDER_LINK_PREFIX+"{}"
DRIVE_LINK = 'https://drive.google.com/file/d/{}/view?usp=drivesdk'

def link_to_id(link):
  return re.search(r'/([a-zA-Z0-9_-]{33}|[a-zA-Z0-9_-]{44})/?(edit|view)?(\?usp=drivesdk)?$', link).groups()[0]

def folderlink_to_id(link):
  return link if not link else link.replace(FOLDER_LINK_PREFIX, "")

def get_known_courses():
  gfolders = json.loads(FOLDERS_DATA_FILE.read_text())
  return list(filter(None, gfolders.keys()))

def get_gfolders_for_course(course):
  gfolders = json.loads(FOLDERS_DATA_FILE.read_text())
  if course not in gfolders:
    print("Hmmm... I don't know that Google Drive folder! Let's add it:")
    folderurl = input("Public link: ") or None
    shortcuturl = input("Private link: ") or None
    gfolders[course] = {"public":folderurl,"private":shortcuturl}
    FOLDERS_DATA_FILE.write_text(json.dumps(gfolders, sort_keys=True, indent=1))
  shortcut_folder = folderlink_to_id(gfolders[course]['private'])
  folder_id = folderlink_to_id(gfolders[course]['public'])
  return (folder_id, shortcut_folder)

@cache
def session():
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
    return build('drive', 'v3', credentials=creds)

def upload_to_google_drive(file_path, filename=None, folder_id=None):
    drive_service = session()
    file_metadata = {'name': (filename or os.path.basename(file_path))}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    # Create media file upload object
    media = MediaFileUpload(file_path, resumable=True)

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
        print("An error occurred:", str(e))
        return False

def create_drive_shortcut(gfid, filename, folder_id):
  drive_service = session()
  shortcut_metadata = {
       'Name': filename,
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
  return session().files().list(q=f"shortcutDetails.targetId='{target_id}'", spaces='drive', fields='files(id,name,parents)').execute()['files']

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

if __name__ == "__main__":
  glinks = []
  while True:
    glink = input("Google Drive Link (None to continue): ")
    if not glink:
      break
    glinks.append(glink)
  course = input_with_tab_complete("course: ", get_known_courses())
  folders = get_gfolders_for_course(course)
  for glink in glinks:
    move_gfile(glink, folders)
