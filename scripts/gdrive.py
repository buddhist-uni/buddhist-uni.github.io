import os.path
from pathlib import Path
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

# If modifying these scopes, have to redo the token.json.
SCOPES = ['https://www.googleapis.com/auth/drive']
CREDFILE = os.path.expanduser('~/gtoken.json')
FOLDERS_DATA_FILE = Path(os.path.normpath(os.path.join(os.path.dirname(__file__), "../_data/drive_folders.json")))
DRIVE_LINK = 'https://drive.google.com/file/d/{}/view?usp=drivesdk'

def link_to_id(link):
  return re.search(r'/([a-zA-Z0-9_-]{33})/', link).groups()[0]

def folderlink_to_id(link):
  return link if not link else link.replace("https://drive.google.com/drive/folders/", "")

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
def session(client_secrets):
    creds = None
    if os.path.exists(CREDFILE):
        creds = Credentials.from_authorized_user_file(CREDFILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.path.expanduser(client_secrets), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(CREDFILE, 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def upload_to_google_drive(file_path, client_file, filename=None, folder_id=None):
    drive_service = session(client_file)
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

def create_drive_shortcut(client_file, gfid, filename, folder_id):
  drive_service = session(client_file)
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

def move_drive_file(client_file, file_id, folder_id):
  service = session(client_file)
  # pylint: disable=maybe-no-member
  file = service.files().get(fileId=file_id, fields='parents').execute()
  previous_parents = ",".join(file.get('parents'))
  print(f"Moving {file_id} from [{previous_parents}] to [{folder_id}]...")
  file = service.files().update(
    fileId=file_id,
    addParents=folder_id,
    removeParents=previous_parents,
    fields='id, parents, name').execute()
  print(f"  \"{file.get('name')}\" moved to {file.get('parents')}")
  return file
