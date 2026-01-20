#!/bin/python3

import argparse
import textwrap
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
  yaspin,
)
from gdrive import (
  FOLDERS_DATA_FILE,
  gcache,
  OLD_VERSIONS_FOLDER_ID,
  process_duplicate_files,
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
  '--extensions', action=argparse.BooleanOptionalAction,
  help="Whether to fix files whose mimetype != their extension",
  default=True,
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
argument_parser.add_argument(
  "--pickles", action=argparse.BooleanOptionalAction,
  help="Whether to clean up dangling pickle files",
  default=True,
)

with yaspin(text="Loading website data..."):
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
  process_duplicate_files(files, folder_slugs, verbose, dry_run)

def remove_duplicate_url_docs(url: str, verbose=True, dry_run=True):
  files = gcache.sql_query("url_property = ? AND owner = 1", (url,))
  assert len(files) > 1, f"multiple files expected with url={url}"
  # Immediately ignore Old Versions slated for deleting anyway
  files = [f for f in files if OLD_VERSIONS_FOLDER_ID not in f['parents']]
  if len(files) <= 1:
    return
  if any(f['mimeType'] != 'application/vnd.google-apps.document' for f in files):
    raise ValueError(f"Non-doc found pointing to url={url}")
  process_duplicate_files(files, folder_slugs, verbose, dry_run)

def fix_file_extensions(verbose=True, dry_run=True):
  # Maps to the canonical extension
  # If maps to tuple of two values, the 1st is canonical and the 2nd acceptable
  MIME_TYPE_EXTENSIONS = {
    'application/pdf': 'pdf',
    'application/epub+zip': 'epub',
    'video/mp4': 'mp4',
    'application/zip': 'zip',
    'audio/x-m4a': 'm4a',
    'audio/mp4': 'm4a',
    'application/x-mobipocket-ebook': 'mobi',
    'application/vnd.amazon.mobi8-ebook': 'azw3',
    'image/png': 'png',
    'audio/mpeg': ('mp3', 'm4a'),
    'audio/mp3': 'mp3',
    'text/html': ('html', 'htm'),
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    'application/msword': ('doc', 'dot'),
    'image/jpeg': ('jpg', 'jpeg'),
  }
  print("Fixing file extensions...")
  renames = 0
  for mime_type, ext in tqdm(MIME_TYPE_EXTENSIONS.items(), total=len(MIME_TYPE_EXTENSIONS), unit="type", disable=verbose):
    if verbose:
      print(f"  {ext}...")
    okay_ext = None
    if isinstance(ext, tuple):
      okay_ext = ext[1]
      ext = ext[0]
    badboys = gcache.sql_query(
      "mime_type = ? AND owner = 1 AND name NOT LIKE ?",
      (mime_type, f"%.{ext}"),
    )
    for bb in badboys:
      if okay_ext:
        if str(bb['name']).lower().endswith(f'.{okay_ext}'):
          continue
      if verbose:
        print(f"    {bb['name']}")
      renames += 1
      if not dry_run:
        gcache.rename_file(bb['id'], bb['name']+'.'+ext)
  print(f"  Found {renames} files that needed an extension")
    

def remove_dangling_pickles(verbose=True, dry_run=False):
  from tag_predictor import NORMALIZED_DRIVE_FOLDER
  with yaspin(text="Loading all pickles..."):
    all_pickles = gcache.get_children(NORMALIZED_DRIVE_FOLDER)
  def _get_target(pickle_file):
    return gcache.get_item(pickle_file['name'][0:-4])
  print("Checking pickle files...")
  deletes = 0
  pbar = tqdm(range(len(all_pickles)), unit="file")
  for idx in pbar:
    pickle = all_pickles[idx]
    target = _get_target(pickle)
    if not target:
      deletes += 1
      if verbose:
        pbar.write(f"  Deleting dangling {pickle['name']}")
      if not dry_run:
        gcache.trash_file(pickle['id'])
    elif target['name'][-4:].lower() not in ['.pdf', 'epub']:
      deletes += 1
      if verbose:
        pbar.write(f"  Deleting pickle for unreadable {target['name']}")
      if not dry_run:
        gcache.trash_file(pickle['id'])
  pbar.close()
  print(f"Deleted {deletes} of {len(all_pickles)} pickle files!")

if __name__ == "__main__":
  arguments = argument_parser.parse_args()
  print("Will perform the following tasks:")
  print(f"  Extensions: {arguments.extensions}")
  print(f"  Shortcuts: {arguments.shortcuts}")
  print(f"  Sharing: {arguments.sharing}")
  print(f"  Duplicates: {arguments.duplicates}")
  # print(f"  Old Cleanup: {arguments.oldies}")
  print(f"  Pickles: {arguments.pickles}")
  print("")
  if not prompt("Continue?", default='y'):
    exit()
  if arguments.extensions:
    fix_file_extensions(verbose=arguments.verbose, dry_run=False)
  if arguments.shortcuts:
    create_all_missing_shortcuts(verbose=arguments.verbose)
  if arguments.sharing:
    ensure_all_public_files_are_shared(verbose=arguments.verbose)
  if arguments.duplicates:
    remove_duplicate_files(verbose=arguments.verbose)
  if arguments.pickles:
    remove_dangling_pickles(verbose=arguments.verbose)
  print("All tasks complete")
