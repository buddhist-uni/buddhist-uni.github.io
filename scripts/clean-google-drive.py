#!/bin/python3

import argparse
import textwrap
from tqdm import tqdm

from gdrive import * # this is a rough and tumble script!
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
argument_parser.add_argument(
  '--no-ensure-shared', action='store_false', dest='ensure_shared',
  help="Turn off ensuring all Google Drive links in website content are publicly shared."
)
argument_parser.add_argument(
  '--no-check-links', action='store_false', dest='check_links',
  help="Turn off checking the status of Google Drive links in website content."
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
  for pair in wrapper(drive_folders):
    if verbose:
      print(f"[shortcuts] Now analyzing the \"{pair}\" folders...")
      pair = drive_folders[pair]
    if not (pair['public'] and pair['private']):
      continue
    create_missing_shortcuts(pair, verbose=verbose)

def create_missing_shortcuts(pair, verbose=True):
  """Takes a {'public': gid, 'private': gid} and ensures 'public' files are in 'private'"""
  if not (pair['public'] and pair['private']):
    raise ValueError("I need a genuine pair of folders")
  private_fid = folderlink_to_id(pair['private'])
  public_fid = folderlink_to_id(pair['public'])
  files_with_shortcuts_here = set()
  query = " and ".join([
    "trashed=false",
    f"'{private_fid}' in parents",
    "mimeType='application/vnd.google-apps.shortcut'"
  ])
  for shortcut in all_files_matching(query, "shortcutDetails"):
    files_with_shortcuts_here.add(shortcut.get('shortcutDetails',{}).get('targetId'))
  query = " and ".join([
    "trashed=false",
    f"'{public_fid}' in parents",
    "mimeType!='application/vnd.google-apps.shortcut'",
    "mimeType!='application/vnd.google-apps.folder'"
  ])
  for public_file in all_files_matching(query, 'id,name,parents'):
    if public_file['id'] in files_with_shortcuts_here:
      continue
    existing_shortcuts = get_shortcuts_to_gfile(public_file['id'])
    if len(existing_shortcuts) == 0:
      if verbose:
        print(f"  Creating a new shortcut to {public_file['name']}...")
      create_drive_shortcut(public_file['id'], public_file['name'], private_fid)
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
          move_drive_file(public_file['id'], correct_public_folder, public_file['parents'])
        make_short = True
        for shortcut in existing_shortcuts:
          if shortcut['parents'][0] == correct_private_folder:
            make_short = False
          else:
            if verbose:
              print(f"  Trashing superfluous shortcut to {public_file['name']} in {shortcut['parents'][0]}...")
            trash_drive_file(shortcut['id'])
        if make_short:
          if verbose:
            print(f"  Creating a new shortcut to {public_file['name']}...")
          create_drive_shortcut(public_file['id'], public_file['name'], correct_private_folder)
        continue
      if len(existing_shortcuts) == 2:
        if existing_shortcuts[0]['parents'][0] == existing_shortcuts[1]['parents'][0]:
          if verbose:
            print(f"  Removing duplicate shortcut to {public_file['name']}...")
          trash_drive_file(existing_shortcuts[0]['id'])
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
      folder = session().files().get(fileId=existing_shortcut_parent,fields='name').execute()
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
        move_drive_file(
          existing_shortcuts[0]['id'],
          private_fid,
          existing_shortcuts[0]['parents'],
          verbose=False,
        )
        continue
      if match.course == private_slug:
        if verbose:
          print("  The public file was in the wrong folder. Moving it...")
        move_drive_file(
          public_file['id'],
          folderlink_to_id(drive_folders[private_slug]['public']),
          public_file['parents'],
          verbose=False,
        )
        continue
      if match.course == public_slug:
        if verbose:
          print("  The public file was correct. Moving the shortcut....")
        move_drive_file(
          existing_shortcuts[0]['id'],
          folderlink_to_id(drive_folders[public_slug]['private']),
          existing_shortcuts[0]['parents'],
          verbose=False
        )
        continue
      print(conflict_expl)
      raise RuntimeError("I really don't know what to do here!  The Website, private drive and public drive all disagree!!")
    create_drive_shortcut(public_file['id'], f"[should live in {canon_ref}] {public_file['name']}", private_fid)


def ensure_all_drive_links_are_shared():
  """
  Ensures all Google Drive links found in the website content are shared with everyone.
  """
  all_public_gids = []
  for page in website.content:
    if page.drive_links:
      for glink in page.drive_links:
        gid = gdrive.link_to_id(glink)
        if gid:
          all_public_gids.append(gid)

  print(f"Fetching permissions info about {len(all_public_gids)} Google Drive files...")
  gdrive.ensure_these_are_shared_with_everyone(all_public_gids)
  print("Done! (ensuring all drive links are shared)")


def check_all_drive_links_status():
  """
  Checks the status of all Google Drive links found in the website content.
  Verifies that the files are not trashed and warns about any missing or problematic links.
  """
  def _fetch_all_content_drive_ids():
    for content_page in website.content:
      for link in content_page.get('drive_links', []):
        gid = gdrive.link_to_id(link)
        if not gid:
          print(f"Warning: Unable to extract id from \"{link}\"")
        else:
          yield gid

  drive_ids = set(_fetch_all_content_drive_ids())
  seen_ids = set()

  print("\nChecking drive links status:")
  for gfile in gdrive.batch_get_files_by_id(list(drive_ids), "id,name,trashed"):
    seen_ids.add(gfile['id'])
    if gfile['trashed']:
      print(f"ERROR! {gdrive.DRIVE_LINK.format(gfile['id'])} ('{gfile.get('name', 'N/A')}') is trashed!")

  unseen_ids = drive_ids - seen_ids
  if unseen_ids:
    print(f"Warning: The following Drive IDs were found in content but not retrieved from Drive (may be invalid or no longer exist): {unseen_ids}")
  print("Done! (checking all drive links status)")


if __name__ == "__main__":
  arguments = argument_parser.parse_args()
  print("Will perform the following tasks:")
  print(f"  Shortcuts: {arguments.shortcuts}")
  print(f"  Ensure Shared: {arguments.ensure_shared}")
  print(f"  Check Links: {arguments.check_links}")
  print("")
  if not prompt("Continue?", default='y'):
    exit()
  if arguments.shortcuts:
    create_all_missing_shortcuts(verbose=arguments.verbose)
  if arguments.ensure_shared:
    ensure_all_drive_links_are_shared()
  if arguments.check_links:
    check_all_drive_links_status()
  print("All tasks complete")
