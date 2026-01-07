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
)
from gdrive import (
  FOLDERS_DATA_FILE,
  gcache,
)
import website

argument_parser = argparse.ArgumentParser(
  formatter_class=argparse.RawDescriptionHelpFormatter,
  prog='python3 clean-google-drive.py',
  description=textwrap.dedent('''\
    A script to clean up the Google Drive Library.
    
    It performs several automatable, routine cleanup tasks, to
    enforce the invariants I've tried (all-too-humanly) to keep.
    
    By default, the script performs all actions. Use a flag to
    turn _off_ a particular check.
  '''),
)
argument_parser.add_argument(
  '-v', '--verbose', action='store_true',
)
argument_parser.add_argument(
  '--no-shortcuts', action='store_false', dest='shortcuts',
  help="Turn off creating shortcuts in private folders for public files"
)

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

if __name__ == "__main__":
  arguments = argument_parser.parse_args()
  print("Will perform the following tasks:")
  print(f"  Shortcuts: {arguments.shortcuts}")
  print("")
  if not prompt("Continue?", default='y'):
    exit()
  if arguments.shortcuts:
    create_all_missing_shortcuts(verbose=arguments.verbose)
  print("All tasks complete")
