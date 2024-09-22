#!/usr/bin/env python3

import json
import hashlib

from strutils import FileSyncedMap, replace_text_across_repo
import gdrive

DEFERRED_SHORTCUTS = []

NEW_FILE_IDS_FILE = gdrive.git_root_folder / "scripts/.gcache/new_file_ids.json"
NEW_FILE_IDS = FileSyncedMap(NEW_FILE_IDS_FILE)
MY_EMAILS = {
  'aee5188bd988b0ab263a6b3003831c6e',
  'e55371a7e1b97300ea623338dbcc0694',
  '3945098d73ac3a594febd2c87d357971',
  '3b654b6ccfb53f233fbd798415b62624',
  'b9083baac482b28ac374ebe1856bfefc',
  '7f519cc091d7690b440aa4db74141a94',
  'd97d9501979b0a1442b0482418509a84',
}
APP_NAME = "LibraryUtils.FolderCopier"
SOURCE_FILE_FIELDS = "id,name,properties,shortcutDetails,mimeType,parents"

def md5(text):
  return hashlib.md5(text.encode()).hexdigest()

def is_file_mine(file):
  for owner in file['owners']:
    if md5(owner['emailAddress']) in MY_EMAILS:
      return True
  return False

def get_previously_copied_version(fileid: str, filefields="id,name"):
  if fileid in NEW_FILE_IDS:
    return NEW_FILE_IDS[fileid]
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
  NEW_FILE_IDS[fileid] = ret[0]
  return ret[0]

def copy_shortcut(
    source_shortcut: dict,
    dest_parent_id: str = None,
    defer_uncopied_targets: list[dict] = None,
) -> str:
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
    if defer_uncopied_targets is None:
      print(f"WARNING! Not making a copy of \"{source_shortcut['name']}\" in {dest_parent_id} because {target['name']} is mine and unmigrated!")
      return None
    defer_uncopied_targets.append(target)
    assert NEW_FILE_IDS[source_shortcut['parents'][0]] == dest_parent_id
    return None
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
  NEW_FILE_IDS[source_file['id']] = dest_file
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
    NEW_FILE_IDS[source_folder_id] = dest_folder
  children_query = f"'{source_folder_id}' in parents and trashed=false"
  for child in gdrive.all_files_matching(children_query, SOURCE_FILE_FIELDS):
    if child['mimeType'] == 'application/vnd.google-apps.folder':
      copy_folder(child['id'], dest_folder)
    elif child['id'] in NEW_FILE_IDS:
      print(f"Skipping already-copied file \"{child['name']}\"...")
    elif child.get('shortcutDetails'):
      copy_shortcut(child, dest_parent_id, DEFERRED_SHORTCUTS)
    else:
      copy_file(child, dest_folder)
  replace_text_across_repo(source_folder_id, dest_folder)

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
  if len(DEFERRED_SHORTCUTS) > 0:
    print("\nRetrying deferred shortcut files...")
    for shortcut in gdrive.tqdm(DEFERRED_SHORTCUTS):
      copy_shortcut(shortcut, NEW_FILE_IDS[shortcut['parents'][0]])
  print("All done!")
