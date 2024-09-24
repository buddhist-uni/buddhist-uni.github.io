#!/usr/bin/env python3

import json
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
# technically can do 100/batch but in practice it will timeout messily sometimes
PENDING_FILE_COPY_OPS = []
BATCH_SIZE = 30
WRITELOCKFILE = gdrive.git_root_folder / "scripts/.gcache/pending_copies.json"

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

def trash_all_uncopied_files(root_folder: str):
  if "http" in root_folder:
    root_folder = gdrive.folderlink_to_id(root_folder)
  for child in gdrive.all_files_matching(f"'{root_folder}' in parents and trashed=false", SOURCE_FILE_FIELDS):
    if child['mimeType'] == 'application/vnd.google-apps.folder':
      trash_all_uncopied_files(child['id'])
      continue
    if not child.get('properties') or not child['properties'].get('copiedFrom'):
      source = NEW_FILE_IDS.keyfor(child['id'])
      if source:
        raise RuntimeError(f"\"{child['name']}\" is from {source} but doesn't know it!")
      if gdrive.prompt(f"Tash uncopied \"{child['name']}\" in {gdrive.FOLDER_LINK_PREFIX}{root_folder} ?"):
        gdrive.trash_drive_file(child['id'])
        print("  Trashed")
    else:
      knownfrom = child['properties']['copiedFrom']
      if knownfrom not in NEW_FILE_IDS:
        NEW_FILE_IDS[knownfrom] = child['id']
      if NEW_FILE_IDS[knownfrom] != child['id']:
        cacheknowncopy = gdrive.session().files().get(
          fileId=NEW_FILE_IDS[knownfrom],
          fields="id,name,properties,shortcutDetails,mimeType,parents,owners,trashed,size,createdTime",
        ).execute()
        print("Found this file the cache didn't know\n=============")
        print(json.dumps(child, indent=2, sort_keys=True))
        print("\nThe file known to the cache is\n===============")
        print(json.dumps(cacheknowncopy, indent=2, sort_keys=True))
        print("\nWill trash one of them!")
        if gdrive.prompt("Shall it be the first one?"):
          gdrive.trash_drive_file(child['id'])
          print("  Trashed")
        else:
          gdrive.trash_drive_file(cacheknowncopy['id'])
          NEW_FILE_IDS[knownfrom] = child['id']
          print("  Trashed")

def get_previously_copied_version(fileid: str):
  if fileid in NEW_FILE_IDS:
    return NEW_FILE_IDS[fileid]
  ret = gdrive.session().files().list(
    q=' and '.join([
      f"properties has {{ key='copiedFrom' and value='{fileid}' }}",
      "trashed=false",
    ]),
    pageSize=1,
    fields='files(id),nextPageToken',
  ).execute()
  if 'nextPageToken' in ret:
    print(f"WARNING! Multiple copies of {fileid} found! Trashing the first copy...")
    gdrive.trash_drive_file(ret['files'][0]['id'])
    return get_previously_copied_version(fileid)
  ret = ret['files']
  if len(ret) == 0:
    return None
  NEW_FILE_IDS[fileid] = ret[0]['id']
  return ret[0]['id']

def copy_shortcut(
    source_shortcut: dict,
    dest_parent_id: str = None,
    defer_uncopied_targets: list[dict] = None,
) -> str:
  shortcut_metadata = {
    'name': source_shortcut['name'],
    'mimeType': 'application/vnd.google-apps.shortcut',
    'properties': {"copiedFrom": source_shortcut['id'], "createdBy": APP_NAME},
    'parents': [dest_parent_id]
  }
  target_id = source_shortcut['shortcutDetails']['targetId']
  target_copy = get_previously_copied_version(target_id)
  if target_copy:
    shortcut_metadata['shortcutDetails'] = {
      'targetId': target_copy
    }
    register_file_copy_op(
      source_shortcut['id'],
      gdrive.session().files().create(body=shortcut_metadata, fields="id"),
    )
    return True
  try:
    target = gdrive.session().files().get(
      fileId=target_id,
      fields='name,owners'
    ).execute()
  except HttpError:
    print(f"WARNING! Bad target for shortcut \"{source_shortcut['name']}\" in {gdrive.FOLDER_LINK_PREFIX}{source_shortcut['parents'][0]}")
    print(f"  Failed to get nominal target of https://drive.google.com/open?id={target_id}")
    print(f"  Destination folder is {gdrive.FOLDER_LINK_PREFIX}{dest_parent_id}")
    input( "  Please handle manually, then press enter to continue...")
    return False
  if is_file_mine(target):
    if defer_uncopied_targets is None:
      print(f"WARNING! Not making a copy of \"{source_shortcut['name']}\" into {gdrive.FOLDER_LINK_PREFIX}{dest_parent_id} because \"{target['name']}\" ( https://drive.google.com/open?id={target_id} ) is mine and unmigrated!")
      input("  Please handle manually, then press enter to continue...")
      return False
    defer_uncopied_targets.append(source_shortcut)
    if NEW_FILE_IDS[source_shortcut['parents'][0]] != dest_parent_id:
      raise RuntimeError(f"Shortcut \"{source_shortcut['name']}\" in {source_shortcut['parents']} didn't match the expected destination {dest_parent_id}. Got {NEW_FILE_IDS[source_shortcut['parents'][0]]} instead.")
    return False
  shortcut_metadata['shortcutDetails'] = {
    'targetId': target_id
  }
  register_file_copy_op(
    source_shortcut['id'],
    gdrive.session().files().create(body=shortcut_metadata, fields="id")
  )
  return True

def copy_file(source_file: dict, dest_parent_id: str = None) -> str:
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
  link = source_file.get('properties', {}).get('url')
  # Google Docs (especially the link files) have to be done individually
  # For some reason they 500 Error in Batches
  if link or source_file['mimeType'] == 'application/vnd.google-apps.document':
    print(f"Copying Google Doc \"{source_file['name']}\"...")
    with DelayedKeyboardInterrupt():
      try:
        ret = copy_request.execute()
      except HttpError as e:
        print(e)
        if gdrive.prompt("Retry?", default="y"):
          return copy_file(source_file, dest_parent_id)
      NEW_FILE_IDS[source_file['id']] = ret['id']
  else:
    register_file_copy_op(source_file['id'], copy_request)

def register_file_copy_op(source_id, copy_request):
  PENDING_FILE_COPY_OPS.append((source_id, copy_request))
  if len(PENDING_FILE_COPY_OPS) >= BATCH_SIZE:
    perform_pending_file_copy_ops()

def handle_write_errors(source_file_ids):
  for source_id in source_file_ids:
    new_id = get_previously_copied_version(source_id)
    if new_id:
      print(f"  Found id for {source_id}")
      NEW_FILE_IDS[source_id] = new_id
    else:
      print(f"  Failed to find id for {source_id}. Run `trash_all_uncopied_files` later.")

def perform_pending_file_copy_ops():
  if WRITELOCKFILE.exists():
    print("Writes from last batch didn't finish cleanly. Investigating...")
    with DelayedKeyboardInterrupt():
      handle_write_errors(json.load(WRITELOCKFILE.open()))
      WRITELOCKFILE.unlink()
  ERRORS = []
  print(f"Copying a batch of {len(PENDING_FILE_COPY_OPS)} files...")
  new_ids = {}
  def _copy_callback(rid, resp, error):
    if error:
      print(f"WARNING! Failed to `copy` fileId={rid}")
      print(error)
      ERRORS.append(rid)
    else:
      replace_text_across_repo(rid, resp['id'])
      new_ids[rid] = resp['id']
  batch_request = gdrive.BatchHttpRequest(
    callback=_copy_callback,
    batch_uri="https://www.googleapis.com/batch/drive/v3",
  )
  for rid, req in PENDING_FILE_COPY_OPS:
    batch_request.add(request_id=rid, request=req)
  these_ids = [p[0] for p in PENDING_FILE_COPY_OPS]
  with DelayedKeyboardInterrupt():
    json.dump(these_ids, WRITELOCKFILE.open("w"))
    batch_request.execute()
    PENDING_FILE_COPY_OPS.clear()
    NEW_FILE_IDS.update(new_ids)
    if len(ERRORS) == 0:
      WRITELOCKFILE.unlink()
    else:
      json.dump(ERRORS, WRITELOCKFILE.open("w"))

def copy_folder(source_folder_id: str, dest_parent_id: str = None):
  dest_folder = get_previously_copied_version(source_folder_id)
  if not dest_folder:
    source_folder = gdrive.session().files().get(
      fileId=source_folder_id,
      fields="id,name,parents,ownedByMe"
    ).execute()
    print(f"Creating new folder \"{source_folder['name']}\"...")
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
      copy_shortcut(child, dest_folder, DEFERRED_SHORTCUTS)
    else:
      copy_file(child, dest_folder)
  replace_text_across_repo(source_folder_id, dest_folder)

def replace_links_in_doc(docid: str):
  doc = gdrive.docs().get(documentId=docid).execute()
  print(f"Replacing links in {doc['title']}...")
  content = doc['body']['content']
  requests = []
  for block in content:
    for element in block.get('paragraph', {}).get('elements', []):
      linkurl = element.get('textRun', {
        }).get('textStyle',{
        }).get('link',{
        }).get('url')
      if linkurl:
        for oldid, newid in NEW_FILE_IDS.items.items():
          if oldid in linkurl:
            print(f"  Found old link \"{element['textRun']['content']}\"...")
            requests.append({
              'updateTextStyle': {
                'fields': 'link',
                'textStyle': {
                  'link': {
                    'url': linkurl.replace(oldid, newid)
                  }
                },
                'range': {
                  'startIndex': element['startIndex'],
                  'endIndex': element['endIndex']
                }
              }
            })
            break
  if len(requests) == 0:
    print("  Nothing to do")
    return
  print("  Making changes...")
  gdrive.docs().batchUpdate(documentId=docid, body={'requests':requests}).execute()
  
def replace_links_across_all_docs():
  for document in gdrive.all_files_matching("mimeType='application/vnd.google-apps.document' and 'me' in owners", "id,name"):
    try:
      replace_links_in_doc(document['id'])
    except:
      print(f"WARNING! Failed to replace links in {document['name']}")

def find_unmigrated_folders():
  known_folders = json.load(gdrive.FOLDERS_DATA_FILE.open("r"))
  folderids = set()
  for tag, folders in known_folders.items():
    if folders["public"]:
      folderids.add(gdrive.folderlink_to_id(folders['public']))
    if folders['private']:
      folderids.add(gdrive.folderlink_to_id(folders['private']))
  for folder in gdrive.batch_get_files_by_id(list(folderids), "id,ownedByMe,name,properties,trashed,mimeType"):
    if folder['mimeType'] != 'application/vnd.google-apps.folder':
      print(f"ERROR! {folder['id']} is not a folder!!")
      continue
    if not folder['ownedByMe']:
      print(f"ERROR! {gdrive.FOLDER_LINK_PREFIX}{folder['id']} is not owned by me!!")
      continue
    if not folder.get('properties', {}).get('copiedFrom'):
      print(f"ERROR! Folder {folder['id']} owned by me doesn't know where it came from!")
      continue
    if folder['trashed']:
      print(f"ERROR! Folder {folder['id']} is trashed!")

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
  print("Verifying copy...")
  trash_all_uncopied_files(source_folder)
  copy_folder(source_folder)
  if len(PENDING_FILE_COPY_OPS) > 0:
    perform_pending_file_copy_ops()
  if len(DEFERRED_SHORTCUTS) > 0:
    print("\nRetrying deferred shortcut files...")
    for shortcut in gdrive.tqdm(DEFERRED_SHORTCUTS):
      copy_shortcut(shortcut, NEW_FILE_IDS[shortcut['parents'][0]])
  print("All done!")
