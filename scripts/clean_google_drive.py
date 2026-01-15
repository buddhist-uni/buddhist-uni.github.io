#!/bin/python3

import argparse
import textwrap
from itertools import permutations
from tqdm import tqdm
import json

from strutils import (
  prompt,
)
from gdrive_base import (
  folderlink_to_id,
  ensure_these_are_shared_with_everyone,
  link_to_id,
  batch_get_files_by_id,
  FOLDER_LINK_PREFIX,
  DRIVE_LINK,
)
from gdrive import (
  FOLDERS_DATA_FILE,
  gcache,
  OLD_VERSIONS_FOLDER_ID,
)
import website

argument_parser = argparse.ArgumentParser(
  formatter_class=argparse.RawDescriptionHelpFormatter,
  prog='python3 clean-google-drive.py',
  description=textwrap.dedent('''\
    A script to clean up the Google Drive Library.
    
    It performs several automatable, routine cleanup tasks, to
    enforce the invariants I've tried (all-too-humanly) to keep.
    
    By default, the script performs shortcuts and duplicates checks.
    Use --sharing to turn on the sharing check as well.
  '''),
)
argument_parser.add_argument(
  '-v', '--verbose', action='store_true',
)
argument_parser.add_argument(
  '--shortcuts', action=argparse.BooleanOptionalAction,
  help="Whether to create shortcuts in private folders for public files",
  default=True,
)
argument_parser.add_argument(
  "--sharing", action=argparse.BooleanOptionalAction,
  help="Whether to share public files with the public",
  default=False,
)
# TODO: Add a step for cleaning up old "Old Versions" files
# Note that this will require expanding the app scope to
# include the Google Drive Activity API:
#   https://www.googleapis.com/auth/drive.activity.readonly
# as that's the only way to know when a file was moved in.
# The Trello card has more details: https://trello.com/c/Avwkm76n
# argument_parser.add_argument(
#   "--old-cleanup", action=argparse.BooleanOptionalAction, dest="oldies",
#   help="Whether to delete outdated 'Old Version' files",
#   default=False,
# )
argument_parser.add_argument(
  "--duplicates", action=argparse.BooleanOptionalAction,
  help="Whether to remove duplicate files",
  default=True,
)
# TODO: Add a step for removing dangling .pkl files

website.load()

drive_folders = json.loads(FOLDERS_DATA_FILE.read_text())
private_folder_slugs = {
  folderlink_to_id(drive_folders[k]['private']): k
  for k in drive_folders
}
public_folder_slugs = {
  folderlink_to_id(drive_folders[k]['public']): k
  for k in drive_folders
}
folder_slugs = {**private_folder_slugs, **public_folder_slugs}

def create_all_missing_shortcuts(verbose=False):
  wrapper = lambda a: a
  if not verbose:
    wrapper = lambda a: tqdm(list(a.values()))
  print("Creating missing shortcuts...")
  counts = {
    'created': 0,
    'moved': 0,
    'trashed': 0,
  }
  for pair in wrapper(drive_folders):
    if verbose:
      print(f"[shortcuts] Now analyzing the \"{pair}\" folders...")
      pair = drive_folders[pair]
    if not (pair['public'] and pair['private']):
      continue
    this_count = create_missing_shortcuts(pair, verbose=verbose)
    counts['created'] += this_count['created']
    counts['moved'] += this_count['moved']
    counts['trashed'] += this_count['trashed']
  print(f"Summary:\n  {counts}")

def create_missing_shortcuts(pair, verbose=True) -> dict[str,int]:
  """Takes a {'public': folderlink, 'private': folderlink} pair and ensures 'public' files have shortcuts in 'private'"""
  if not (pair['public'] and pair['private']):
    raise ValueError("I need a genuine pair of folders")
  counts = {
    'created': 0,
    'moved': 0,
    'trashed': 0,
  }
  private_fid = folderlink_to_id(pair['private'])
  public_fid = folderlink_to_id(pair['public'])
  files_with_shortcuts_here = set()
  for shortcut in gcache.get_shortcuts_in_folder(private_fid):
    files_with_shortcuts_here.add(shortcut['shortcutDetails']['targetId'])
  for public_file in gcache.get_regular_children(public_fid):
    if public_file['id'] in files_with_shortcuts_here:
      continue
    existing_shortcuts = gcache.get_shortcuts_to_file(public_file['id'])
    if len(existing_shortcuts) == 0:
      if verbose:
        print(f"  Creating a new shortcut to {public_file['name']}...")
      gcache.create_shortcut(public_file['id'], public_file['name'], private_fid, target_mime_type=public_file.get('mimeType'))
      counts['created'] += 1
      continue
    match = website.entry_with_drive_id(public_file['id'])
    if len(existing_shortcuts) > 1:
      if match:
        correct_private_folder = folderlink_to_id(drive_folders.get(match.course, {}).get('private'))
        if not correct_private_folder:
          raise RuntimeError(f"Need to know private folder for {match.course}")
        correct_public_folder = folderlink_to_id(drive_folders.get(match.course, {}).get('public'))
        if correct_public_folder and public_file['parents'][0] != correct_public_folder:
          if verbose:
            print(f"  Moving public file {public_file['name']} to {match.course} where it belongs...")
          gcache.move_file(public_file['id'], correct_public_folder)
          counts['moved'] += 1
        make_short = True
        for shortcut in existing_shortcuts:
          if shortcut['parents'][0] == correct_private_folder:
            make_short = False
          else:
            if verbose:
              print(f"  Trashing superfluous shortcut to {public_file['name']} in {shortcut['parents'][0]}...")
            gcache.trash_file(shortcut['id'])
            counts['trashed'] += 1
        if make_short:
          if verbose:
            print(f"  Creating a new shortcut to {public_file['name']}...")
          gcache.create_shortcut(public_file['id'], public_file['name'], correct_private_folder, target_mime_type=public_file.get('mimeType'))
          counts['created'] += 1
        continue
      if len(existing_shortcuts) == 2:
        if existing_shortcuts[0]['parents'][0] == existing_shortcuts[1]['parents'][0]:
          if verbose:
            print(f"  Removing duplicate shortcut to {public_file['name']}...")
          gcache.trash_file(existing_shortcuts[0]['id'])
          counts['trashed'] += 1
          continue
        slug = folder_slugs.get(existing_shortcuts[0]['parents'][0])
        if slug and folder_slugs.get(existing_shortcuts[1]['parents'][0]) == slug:
          # If the two shortcuts are not in the same folder (tested above)
          # and yet they are in the same "slug", that means the shortcuts are in
          # the private and public versions of the same folder, which means
          # the public file is temporarily made visible and will be moved down
          # in due course, so we can safely ignore these "duplicate" shortcuts
          continue
      raise FileExistsError(
        f"\"{public_file['name']}\" already has multiple shortcuts in {[s['parents'] for s in existing_shortcuts]}"
      )
    existing_shortcut_parent = existing_shortcuts[0]['parents'][0]
    private_slug = private_folder_slugs.get(existing_shortcut_parent)
    canon_ref = private_slug
    if not private_slug:
      folder = gcache.get_item(existing_shortcut_parent)
      canon_ref = f"\"{folder['name']}\""
    elif drive_folders[private_slug]['public']:
      public_slug = public_folder_slugs.get(public_file['parents'][0])
      conflict_expl = textwrap.dedent(f'''\
          Shortcut to \"{public_file["name"]}\"
          expected in {private_fid} ({private_slug})
          but found in {existing_shortcut_parent} ({public_slug}) instead.
          '''
      ).replace("\n", " ")
      if verbose:
        print(conflict_expl)
      if not match:
        # default to trusting the public folder in such difficult cases
        # this is, after all, mostly a function for fixing _shortcuts_
        if verbose:
          print(f"  Moving the existing shortcut to {public_file['name']}...")
        gcache.move_file(
          existing_shortcuts[0]['id'],
          private_fid,
          existing_shortcuts[0]['parents'],
          verbose=False,
        )
        counts['moved'] += 1
        continue
      if match.course == private_slug:
        if verbose:
          print("  The public file was in the wrong folder. Moving it...")
        gcache.move_file(
          public_file['id'],
          folderlink_to_id(drive_folders[private_slug]['public']),
          public_file['parents'],
          verbose=False,
        )
        counts['moved'] += 1
        continue
      if match.course == public_slug:
        if verbose:
          print("  The public file was correct. Moving the shortcut....")
        gcache.move_file(
          existing_shortcuts[0]['id'],
          folderlink_to_id(drive_folders[public_slug]['private']),
          existing_shortcuts[0]['parents'],
          verbose=False
        )
        counts['moved'] += 1
        continue
      print(conflict_expl)
      raise RuntimeError("I really don't know what to do here!  The Website, private drive and public drive all disagree!!")
    gcache.create_shortcut(public_file['id'], f"[should live in {canon_ref}] {public_file['name']}", private_fid, target_mime_type=public_file.get('mimeType'))
    counts['created'] += 1
  return counts

def ensure_all_public_files_are_shared(verbose=True):
  all_public_gids = []
  for page in website.content:
    if page.drive_links:
      for glink in page.drive_links:
        gid = link_to_id(glink)
        if gid:
          all_public_gids.append(gid)
  print(f"Fetching info about {len(all_public_gids)} Google Drive files...")
  print("  If any of these fail to fetch, please investigate that id manually!")
  count = ensure_these_are_shared_with_everyone(all_public_gids, verbose=verbose)
  print(f"Done! {count} files have been shared.")

def remove_duplicate_files(verbose=True):
  duplicate_md5s = gcache.find_duplicate_md5s()
  print(f"[duplicates] Found {len(duplicate_md5s)} duplicated files by hash.")
  if not verbose:
    duplicate_md5s = tqdm(duplicate_md5s, unit='file', desc='Handling duplicates')
  for md5 in duplicate_md5s:
    remove_duplicate_file(md5, verbose=verbose, dry_run=False)
  duplicate_urls = gcache.find_duplicate_urls()
  print(f"[duplicates] Found {len(duplicate_urls)} duplicated urls.")
  if not verbose:
    duplicate_urls = tqdm(duplicate_urls, unit='url', desc='Handling duplicates')
  for url in duplicate_urls:
    remove_duplicate_url_docs(url, verbose=verbose, dry_run=False)
    

SAFE_EXTENSIONS = set([
  'mp3',
  'mp4',
  'pdf',
  'zip',
  'epub',
  'ogg',
  'm4a',
  'doc',
  'docx',
  'xlsx',
  'html',
  'odt',
  'wma',
  'mobi',
  'rtf',
  'mdx',
  'jpg',
])
UNSAFE_EXTENSIONS = set([
  'pkl',
  'txt',
])

def remove_duplicate_file(md5, verbose=True, dry_run=True):
  files = gcache.get_items_with_md5(md5)
  assert len(files) > 1, f"multiple files expected with md5={md5}"
  if files[0]['size'] < 4096:
    # Let small files live. They aren't hurting anyone!
    return
  # Immediately ignore "UNSAFE" (to delete) file types
  files = [f for f in files if '.' in f['name'] and f['name'].split('.')[-1].lower() not in UNSAFE_EXTENSIONS]
  # Immediately ignore Old Versions slated for deleting anyway
  files = [f for f in files if OLD_VERSIONS_FOLDER_ID not in f['parents']]
  # Immediately ignore any file not owned by me
  files = [f for f in files if f['owners'][0]['me']]
  if len(files) <= 1:
    return
  if any(f['name'].split('.')[-1].lower() not in SAFE_EXTENSIONS for f in files):
    raise ValueError(f"Unknown extension found for md5 = {md5}")
  assert len(files) < 5, f"Found many ({len(files)}) duplicates of {md5}"
  _process_duplicate_files(files, verbose, dry_run)

def remove_duplicate_url_docs(url: str, verbose=True, dry_run=True):
  files = gcache.sql_query("url_property = ? AND owner = 1", (url,))
  assert len(files) > 1, f"multiple files expected with url={url}"
  # Immediately ignore Old Versions slated for deleting anyway
  files = [f for f in files if OLD_VERSIONS_FOLDER_ID not in f['parents']]
  if len(files) <= 1:
    return
  if any(f['mimeType'] != 'application/vnd.google-apps.document' for f in files):
    raise ValueError(f"Non-doc found pointing to url={url}")
  _process_duplicate_files(files, verbose, dry_run)

def _process_duplicate_files(files: list[dict[str, any]], verbose: bool, dry_run: bool):
  for file in files:
    file['parent'] = gcache.get_item(file['parents'][0])
  ids_to_keep = _select_ids_to_keep(files)
  files_to_keep = [f for f in files if f['id'] in ids_to_keep]
  files_to_trash = [f for f in files if f['id'] not in ids_to_keep]
  if verbose or len(files_to_keep) > 1:
    if len(files_to_keep) > 1:
      print("!!vvPLEASE Review the below duplicates manually vv!!")
    for file in files_to_keep:
      print(f"  Keeping \"{file['name']}\" in \"{file['parent']['name']}\"")
      if len(files_to_keep) > 1:
        print(f"    {DRIVE_LINK.format(file['id'])}")
        print(f"    {FOLDER_LINK_PREFIX}{file['parent_id']}")
    if len(files_to_keep) > 1:
      print("!!^^PLEASE Review the above duplicates manually^^!!")
  for f in files_to_trash:
    if verbose:
      print(f"    Trashing \"{f['name']}\" in \"{f['parent']['name']}\"...")
    if not dry_run:
      gcache.trash_file(f['id'])

UNIMPORTANT_SLUGS = [
  'to-go-through',
  'to-split',
  None,
]
UNIMPORTANT_PREFIXES = [
  "🏛️ academia.edu",
  "🌱 dharma seed",
  "📼 youtube videos",
  "DhammaTalks",
  "unread",
  'archive', # normally we wouldn't delete these losing data,
             # however, by this point in the code,
             # we have already eliminated unreads
             # so this leaves items that are archived in one place
             # and accepted somewhere deeper. In those cases we
             # should give such files a second chance at life.
]
TAG_ORDER = {
  str(tf).removesuffix('.md'): idx+1
  for idx, tf in enumerate(website.config['collections']['tags']['order'])
}
LO_PRI = len(TAG_ORDER)+1000

def _select_ids_to_keep(files: list[dict[str, any]]) -> list[str]:
  """Maticulously applies hand-crafted heuristics to select the keepers"""
  #####
  # If only one is in a slugged folder, keep that one
  ####
  slugs = [folder_slugs.get(f['parents'][0]) for f in files]
  filter_list = []
  for unimportant in UNIMPORTANT_SLUGS:
    filter_list.append(unimportant)
    important_slugs = [slug for slug in slugs if slug not in filter_list]
    num_slugs = len(important_slugs)
    if num_slugs == 1:
      # if there's only one file in a slugged folder, keep that one
      # no need to even check for permissions
      return [files[slugs.index(important_slugs[0])]['id']]

  #####
  # Don't trash any publicly-launched files
  #####
  file_permissions = batch_get_files_by_id([f['id'] for f in files], "id,name,permissions")
  are_publics = [any(p['type'] == 'anyone' for p in f['permissions']) for f in file_permissions]
  num_public = sum(are_publics)
  if num_public > 0:
    # Never suggest a public-facing file for deletion
    return [files[i]['id'] for i in range(len(files)) if are_publics[i]]
  
  #####
  # Discard files in "unimportant" subfolders first
  #####
  for prefix in UNIMPORTANT_PREFIXES:
    if prefix == "DhammaTalks":
      unreads = ['1NTIsr31uhBXymkFUu2coGU72vdCjwfNp' in [f['parent']['parents'][0], f['parents'][0]] for f in files]
    else:
      unreads = [f['parent']['name'].lower().startswith(prefix) for f in files]
    unread_count = sum(unreads)
    if unread_count > 0 and unread_count < len(files):
      files = [file for i, file in enumerate(files) if not unreads[i]]
      if len(files) == 1:
        return [files[0]['id']]
      slugs = [slug for i, slug in enumerate(slugs) if not unreads[i]]
  
  #####
  # Next, try to use the site's TAG_ORDER to prioritize placement
  #   Keep files placed in more important subfolders and trash those deeper
  #####
  if not any(slugs):
    slugs = [folder_slugs.get(f['parent']['parents'][0]) for f in files]
  if any(slug in TAG_ORDER for slug in slugs):
    priorities = [TAG_ORDER.get(slug, LO_PRI) for slug in slugs]
    highest = min(priorities)
    assert len(files) == len(priorities)
    files = [files[i] for i in range(len(files)) if priorities[i] == highest]
    if len(files) == 1:
      return [files[0]['id']]
    
  #####
  # If some couldn't be disambiguated by folder because they are in
  #   the same subfolder, then just pick one
  #####
  if len(set(file['parent_id'] for file in files)) == 1:
    # All files are in the same folder and have the same md5
    # first try to pick the longest name
    name_lens = [len(file['name']) for file in files]
    longest = max(name_lens)
    files = [file for file in files if len(file['name'])==longest]
    if len(files) == 1:
      return [file['id'] for file in files]
    # That failing, pick the eldest
    modifies = [file['modifiedTime'] for file in files]
    eldest = min(modifies)
    idx = modifies.index(eldest)
    return [files[idx]['id']]
  
  #####
  # Disambiguate remaining folders by depth
  #  This time we prefer deeper folders as likely more accurate placement
  ####
  max_depth = 0
  deepest = None
  for file in files:
    depth = 0
    parent = file['parent']
    while parent and parent['parent_id']:
      depth += 1
      new_parent = gcache.get_item(parent['parent_id'])
      if new_parent:
        parent = new_parent
      else:
        break
    file['depth'] = depth
    if depth > max_depth:
      max_depth = depth
      deepest = file
    file['root'] = parent
  roots = set(file['root']['id'] for file in files)
  assert len(roots) == 1, f"Multiple roots found for {files}"
  return [deepest['id']]

if __name__ == "__main__":
  arguments = argument_parser.parse_args()
  print("Will perform the following tasks:")
  print(f"  Shortcuts: {arguments.shortcuts}")
  print(f"  Sharing: {arguments.sharing}")
  print(f"  Duplicates: {arguments.duplicates}")
  # print(f"  Old Cleanup: {arguments.oldies}")
  print("")
  if not prompt("Continue?", default='y'):
    exit()
  if arguments.shortcuts:
    create_all_missing_shortcuts(verbose=arguments.verbose)
  if arguments.sharing:
    ensure_all_public_files_are_shared(verbose=arguments.verbose)
  if arguments.duplicates:
    remove_duplicate_files(verbose=arguments.verbose)
  print("All tasks complete")
