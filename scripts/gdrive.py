import os.path
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

def folderlink_to_id(link):
  return link if not link else link.replace("https://drive.google.com/drive/folders/", "")

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
