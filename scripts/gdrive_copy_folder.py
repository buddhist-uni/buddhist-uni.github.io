#!/usr/bin/env python3

import hashlib

from strutils import (
  FileSyncedMap, 
  replace_text_across_repo,
  DelayedKeyboardInterrupt,
)
import gdrive
from googleapiclient.errors import HttpError

# This horrible, hacked together code uses global variables
# deal with it B-)
DEFERRED_SHORTCUTS = []
PENDING_FILE_COPY_OPS = []

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
    print(f"WARNING! Multiple copies of {fileid} found! Trashing the first copy...")
    gdrive.trash_drive_file(ret['files'][0]['id'])
    return get_previously_copied_version(fileid, filefields)
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
    with DelayedKeyboardInterrupt():
      ret = gdrive.create_drive_shortcut(
        target_copy['id'],
        source_shortcut['name'],
        dest_parent_id,
        custom_properties={"copiedFrom": source_shortcut['id'], "createdBy": APP_NAME}
      )
      NEW_FILE_IDS[source_shortcut['id']] = ret
    return ret
  try:
    target = gdrive.session().files().get(
      fileId=target_id,
      fields='name,owners'
    ).execute()
  except HttpError:
    print(f"WARNING! Bad target for shortcut \"{source_shortcut['name']}\"")
    return None
  if is_file_mine(target):
    if defer_uncopied_targets is None:
      print(f"WARNING! Not making a copy of \"{source_shortcut['name']}\" in {dest_parent_id} because {target['name']} is mine and unmigrated!")
      return None
    defer_uncopied_targets.append(target)
    if NEW_FILE_IDS[source_shortcut['parents'][0]] != dest_parent_id:
      raise RuntimeError(f"Shortcut \"{source_shortcut['name']}\" in {source_shortcut['parents']} didn't match the expected destination {dest_parent_id}. Got {NEW_FILE_IDS[source_shortcut['parents'][0]]} instead.")
    return None
  with DelayedKeyboardInterrupt():
    ret = gdrive.create_drive_shortcut(
      target_id,
      source_shortcut['name'],
      dest_parent_id,
      custom_properties={"copiedFrom": source_shortcut['id'], "createdBy": APP_NAME}
    )
    NEW_FILE_IDS[source_shortcut['id']] = ret
  return ret

def copy_file(source_file: dict, dest_parent_id: str = None) -> str:
  # Uncomment the below check if you have to
  # dest_id = get_previously_copied_version(source_file['id'])
  # if dest_id:
  #   print(f"Skipping already-copied file \"{source_file['name']}\"...")
  #   NEW_FILE_IDS[source_file['id']] = dest_id
  #   return dest_id
  properties = {
    'copiedFrom': source_file['id'],
    'createdBy': APP_NAME
  }
  # The LibraryUtils.LinkSaver creator is more important
  # so allow that value to override our APP_NAME
  properties.update(source_file.get('properties', {}))
  copy_request = gdrive.session().files().copy(
    fileId=source_file['id'],
    body={
      'name': source_file['name'],
      'parents': [dest_parent_id] if dest_parent_id else None,
      'properties': properties
    },
    fields="id"
  )
  PENDING_FILE_COPY_OPS.append((source_file['id'], copy_request))
  if len(PENDING_FILE_COPY_OPS) == 100:
    perform_pending_file_copy_ops()

def perform_pending_file_copy_ops():
  print(f"Copying a batch of {len(PENDING_FILE_COPY_OPS)} files...")
  new_ids = {}
  def _copy_callback(rid, resp, error):
    if error:
      print(f"WARNING! Failed to `copy` fileId={rid}")
      print(error)
    else:
      replace_text_across_repo(rid, resp['id'])
      new_ids[rid] = resp['id']
  batch_request = gdrive.BatchHttpRequest(
    callback=_copy_callback,
    batch_uri="https://www.googleapis.com/batch/drive/v3",
  )
  for rid, req in PENDING_FILE_COPY_OPS:
    batch_request.add(request_id=rid, request=req)
  with DelayedKeyboardInterrupt():
    batch_request.execute()
    PENDING_FILE_COPY_OPS.clear()
    NEW_FILE_IDS.update(new_ids)

def copy_folder(source_folder_id: str, dest_parent_id: str = None):
  source_folder = gdrive.session().files().get(
    fileId=source_folder_id,
    fields="id,name,parents,ownedByMe"
  ).execute()
  print(f"Copying \"{source_folder['name']}\"...")
  dest_folder = get_previously_copied_version(source_folder_id)
  if dest_folder:
    print("Resuming previous copy...")
  else:
    print("Creating new folder...")
    with DelayedKeyboardInterrupt():
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
      pass # nothing to do here
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
  if len(PENDING_FILE_COPY_OPS) > 0:
    perform_pending_file_copy_ops()
  if len(DEFERRED_SHORTCUTS) > 0:
    print("\nRetrying deferred shortcut files...")
    for shortcut in gdrive.tqdm(DEFERRED_SHORTCUTS):
      copy_shortcut(shortcut, NEW_FILE_IDS[shortcut['parents'][0]])
  print("All done!")
