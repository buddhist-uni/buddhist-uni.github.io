#!/usr/bin/env python3

import json
import hashlib

from strutils import replace_text_across_repo
import gdrive

APP_NAME = "LibraryUtils.FolderCopier"
MY_EMAILS = {
  'aee5188bd988b0ab263a6b3003831c6e',
  'e55371a7e1b97300ea623338dbcc0694',
  '3945098d73ac3a594febd2c87d357971',
  '3b654b6ccfb53f233fbd798415b62624',
  'b9083baac482b28ac374ebe1856bfefc',
  '7f519cc091d7690b440aa4db74141a94',
  'd97d9501979b0a1442b0482418509a84',
}

SOURCE_FILE_FIELDS = "id,name,properties,shortcutDetails,mimeType"
GDRIVE_FOLDERS_DATA = json.loads(gdrive.FOLDERS_DATA_FILE.read_text())
COURSE_FOR_PUBLIC_FOLDER = {
  gdrive.folderlink_to_id(v['public']): k
  for k, v in GDRIVE_FOLDERS_DATA.items() if v['public']
}
COURSE_FOR_PRIVATE_FOLDER = {
  gdrive.folderlink_to_id(v['private']): k
  for k, v in GDRIVE_FOLDERS_DATA.items() if v['private']
}

def md5(text):
  return hashlib.md5(text.encode()).hexdigest()

def is_file_mine(file):
  for owner in file['owners']:
    if md5(owner['emailAddress']) in MY_EMAILS:
      return True
  return False

def get_previously_copied_version(fileid: str, filefields="id,name"):
  ret = gdrive.session().files().list(
    q=' and '.join([
      f"properties has {{ key='copiedFrom' and value='{fileid}' }}",
      "trashed=false",
    ]),
    pageSize=1,
    fields=f'files({filefields}),nextPageToken',
  ).execute()
  if 'nextPageToken' in ret:
    raise RuntimeError(f"Multiple copies of {fileid} found!")
  ret = ret['files']
  if len(ret) == 0:
    return None
  return ret[0]

def copy_shortcut(source_shortcut: dict, dest_parent_id: str = None) -> str:
  target_id = source_shortcut['shortcutDetails']['targetId']
  target_copy = get_previously_copied_version(target_id)
  if target_copy:
    return gdrive.create_drive_shortcut(
      target_copy['id'],
      source_shortcut['name'],
      dest_parent_id,
      custom_properties={"copiedFrom": source_shortcut['id'], "createdBy": APP_NAME}
    )
  target = gdrive.session().files().get(
    fileId=target_id,
    fields='name,owners'
  ).execute()
  if is_file_mine(target):
    raise RuntimeError(f"Shortcut target is to an uncopied file of mine: {target_id}")
  return gdrive.create_drive_shortcut(
    target_id,
    source_shortcut['name'],
    dest_parent_id,
    custom_properties={"copiedFrom": source_shortcut['id'], "createdBy": APP_NAME}
  )

def copy_file(source_file: dict, dest_parent_id: str = None) -> str:
  print(f"Copying \"{source_file['name']}\"...")
  dest_file = get_previously_copied_version(source_file['id'])
  if dest_file:
    print("  Already copied. Skipping...")
    return dest_file['id']
  if source_file.get('shortcutDetails'):
    return copy_shortcut(source_file, dest_parent_id)
  properties = {
    'copiedFrom': source_file['id'],
    'createdBy': APP_NAME
  }
  # The LibraryUtils.LinkSaver creator is more important
  # so allow that value to override our APP_NAME
  properties.update(source_file.get('properties', {}))
  dest_file = gdrive.session().files().copy(
    fileId=source_file['id'],
    body={
      'name': source_file['name'],
      'parents': [dest_parent_id] if dest_parent_id else None,
      'properties': properties
    },
    fields="id"
  ).execute()
  dest_file = dest_file['id']
  replace_text_across_repo(source_file['id'], dest_file)
  return dest_file

def copy_folder(source_folder_id: str, dest_parent_id: str = None):
  source_folder = gdrive.session().files().get(
    fileId=source_folder_id,
    fields="id,name,parents,ownedByMe"
  ).execute()
  print(f"Copying \"{source_folder['name']}\"...")
  dest_folder = get_previously_copied_version(source_folder_id)
  if dest_folder:
    print("Resuming previous copy...")
    dest_folder = dest_folder['id']
  else:
    print("Creating new folder...")
    dest_folder = gdrive.create_folder(
      source_folder['name'],
      dest_parent_id,
      custom_properties={"copiedFrom": source_folder_id, "createdBy": APP_NAME}
    )
    if source_folder_id in COURSE_FOR_PUBLIC_FOLDER:
      GDRIVE_FOLDERS_DATA[COURSE_FOR_PUBLIC_FOLDER[source_folder_id]]['new_public'] = gdrive.FOLDER_LINK.format(dest_folder)
      json.dump(GDRIVE_FOLDERS_DATA, open(gdrive.FOLDERS_DATA_FILE, 'w'), indent=1, sort_keys=True)
    if source_folder_id in COURSE_FOR_PRIVATE_FOLDER:
      GDRIVE_FOLDERS_DATA[COURSE_FOR_PRIVATE_FOLDER[source_folder_id]]['new_private'] = gdrive.FOLDER_LINK.format(dest_folder)
      json.dump(GDRIVE_FOLDERS_DATA, open(gdrive.FOLDERS_DATA_FILE, 'w'), indent=1, sort_keys=True)
  children_query = f"'{source_folder_id}' in parents and trashed=false"
  for child in gdrive.all_files_matching(children_query, SOURCE_FILE_FIELDS):
    if child['mimeType'] == 'application/vnd.google-apps.folder':
      copy_folder(child['id'], dest_folder)
    else:
      copy_file(child, dest_folder)

if __name__ == "__main__":
  current_user = gdrive.session().about().get(fields='user').execute()['user']
  print(f"Currently logged in as \"{current_user['displayName']}\"")
  print(f"All created folders and files will be owned by {current_user['emailAddress']}.")
  if not gdrive.prompt("Is this correct?", default="y"):
    print("Glad I asked! Please change ~/gtoken.json and try again.")
    quit(0)
  source_folder = input("Source Folder: ")
  if "http" in source_folder:
    source_folder = gdrive.folderlink_to_id(source_folder)
  copy_folder(source_folder)
  print("All done!")
