#!/bin/python3

import gdrive
from enum import StrEnum
from collections.abc import Collection
from collections import OrderedDict, deque
import random
from mimetypes import guess_extension
from pathlib import Path
from typing import Callable, Optional
from tqdm import tqdm
import sys
import gdrive
import shutil
from strutils import (
  md5,
  format_size,
)
from executils import (
  graceful_threadmap,
  ThreadSafeSet,
)
from yaspin import yaspin
import googleapiclient.errors as gerrors
from bulk_import import BULK_PDF_FOLDER_NAMES, BulkPDFType
import website

# We'll stop downloading when we have only this much space left
MIN_FREE_SPACE = 2**34 # 16 GB

def query_cache(sql: str, variables: tuple=tuple()) -> list[dict]:
  """Performs a query, filtering out shortcuts and shuffling the results"""
  ret = gdrive.gcache.sql_query(
    "shortcut_target IS NULL AND " + sql,
    variables,
  )
  random.shuffle(ret)
  return ret

def query_my_cache(sql: str='', variables: tuple=tuple()) -> list[dict]:
  return query_cache(
    "owner = 1" + (f" AND {sql}" if sql else ''),
    variables,
  )

def query_parent_name(parent_name: str) -> list[dict]:
  ret = gdrive.gcache.parent_sql_query(
    "parent.name = ?",
    (parent_name,)
  )
  random.shuffle(ret)
  return ret

class BackupLevel:
  def __init__(self, level: int, name: str, description: str, finder: Optional[Callable[[], list[dict]]] = None):
    self.level = level
    self.name = name
    self.description = description
    self.finder = finder

  def find_files(self) -> list[dict]:
    """Finds and yields/returns the files to be backed up at this level."""
    if self.finder:
      return self.finder()
    return []

BACKUP_LEVELS: OrderedDict[int, BackupLevel] = OrderedDict()

def add_backup_level(level: int, name: str, description: str, finder: Optional[Callable[[], list[dict]]] = None):
  global BACKUP_LEVELS
  BACKUP_LEVELS[level] = BackupLevel(level, name, description, finder)
  BACKUP_LEVELS = OrderedDict(sorted(BACKUP_LEVELS.items()))

def backup_level(level: int, name: str, description: str):
  """Decorator to register a function as a backup level finder."""
  def decorator(func: Callable[[], list[dict]]):
    add_backup_level(level, name, description, func)
    return func
  return decorator

add_backup_level(0,  "Cache Only", "Don't proactively fill the cache at all")

class TagFolderTypes(StrEnum):
  PUBLIC = 'public'
  PRIVATE = 'private'
  NONTAG_PUBLIC_SUBS = 'public/*'
  UNREAD = 'private/unread'
  ARCHIVE = 'private/archive'

def get_folders_of_types_for_tag(
  tag_slug: str,
  include_folders: None | Collection[TagFolderTypes]=None,
) -> list[dict]:
  folder_json = gdrive.FOLDERS_DATA()
  if tag_slug not in folder_json:
    return []
  if not include_folders:
    include_folders = {
      TagFolderTypes.PUBLIC,
      TagFolderTypes.NONTAG_PUBLIC_SUBS,
      TagFolderTypes.PRIVATE,
    }
  private_link = folder_json[tag_slug]['private']
  public_link = folder_json[tag_slug]['public']
  public_id = gdrive.folderlink_to_id(public_link) if public_link else None
  private_id = gdrive.folderlink_to_id(private_link) if private_link else None
  ret = []
  if private_id:
    private_subfolders = gdrive.gcache.get_subfolders(
      parent_id=private_id,
      include_shortcuts=False,
    )
  else:
    private_subfolders = []
  for inc_type in set(include_folders):
    match inc_type:
      case TagFolderTypes.PUBLIC:
        if public_id:
          ret.append(gdrive.gcache.get_item(public_id))
          assert ret[-1] is not None, f"drive_folders.json['{tag_slug}']['public'] has a bad value"
      case TagFolderTypes.PRIVATE:
        if private_id:
          ret.append(gdrive.gcache.get_item(private_id))
          assert ret[-1] is not None, f"drive_folders.json['{tag_slug}']['private'] has a bad value"
      case TagFolderTypes.NONTAG_PUBLIC_SUBS:
        if public_id:
          folderids_to_tag = gdrive.load_folder_slugs()
          public_subfolders = [public_id] # recursive
          while public_subfolders:
            subid = public_subfolders.pop()
            for sf in gdrive.gcache.get_subfolders(parent_id=subid, include_shortcuts=False):
              if sf['id'] not in folderids_to_tag:
                ret.append(sf)
                public_subfolders.append(sf['id'])
      case TagFolderTypes.UNREAD:
        for sf in private_subfolders:
          if 'unread' in sf['name'].lower():
            ret.append(sf)
      case TagFolderTypes.ARCHIVE:
        for sf in private_subfolders:
          if sf['name'].lower().startswith('archive'):
            ret.append(sf)
  return ret

def find_files_for_tag(tag_slug: str, include_av: bool=False, include_folders: Collection[TagFolderTypes] | None=None) -> list[dict]:
  folders = get_folders_of_types_for_tag(tag_slug, include_folders)
  if not folders:
    return []
  nqs = ['?'] * len(folders)
  nqs = ', '.join(nqs)
  bad_mime_prefixes = ['application/vnd.google-apps']
  if not include_av:
    bad_mime_prefixes.extend([
      'audio/',
      'video/',
      'application/zip',
    ])
  bad_mime_prefixes = [
    f"mime_type LIKE '{prefix}%'"
    for prefix in bad_mime_prefixes
  ]
  all_files = gdrive.gcache.sql_query(
    f"parent_id IN ({nqs}) AND NOT ({' OR '.join(bad_mime_prefixes)})",
    tuple(sf['id'] for sf in folders),
  )
  return all_files

def find_unlinked_tag_content(
  include_folders: set[TagFolderTypes]=None,
  include_av=False,
) -> list[dict]:
  ret = []
  for tag in website.tags:
    all_files = find_files_for_tag(tag.slug, include_av=include_av, include_folders=include_folders)
    all_files = [
      file for file in all_files
      if file['id'] not in website.data.linked_ids
    ]
    random.shuffle(all_files)
    ret.extend(all_files)
  return ret

@backup_level(1, "lone published", "Non-av files in tags without a source")
def first_priorities() -> list[dict]:
  return find_unlinked_tag_content()

@backup_level(3, "public archive", "shared, untagged files")
def find_public_archive_files() -> list[dict]:
  ARCHIVE_FOLDER_ID = gdrive.folderlink_to_id(gdrive.FOLDERS_DATA()[""]["public"])
  return query_my_cache("parent_id = ?", (ARCHIVE_FOLDER_ID,))

@backup_level(4, "scanned books", "Books I personally scanned")
def find_book_scans() -> list[dict]:
  return gdrive.gcache.parent_sql_query(
    "parent.parent_id = '1WrMEkkL4be_hLvn43w0TFqOdzCycfyz2'",
    tuple(),
  )

@backup_level(6, "nonsite tags", "non-av files directly in tags below the site")
def find_nonwebsite_tag_files() -> list[dict]:
  FOLDERS_DATA = gdrive.FOLDERS_DATA()
  folder_slugs = set(FOLDERS_DATA.keys()) - set(gdrive.UNIMPORTANT_SLUGS) - set(tag.slug for tag in website.tags)
  ret = []
  for tag_slug in folder_slugs:
    all_files = find_files_for_tag(tag_slug)
    all_files = [
      file for file in all_files
      if file['id'] not in website.data.linked_ids
    ]
    ret.extend(all_files)
  random.shuffle(ret)
  return ret

@backup_level(8, "unread docs", "All non-av files in tag unread folders")
def find_unread_doc_files() -> list[dict]:
  return find_unlinked_tag_content(include_folders={TagFolderTypes.UNREAD})

add_backup_level(10, "High", "All valuable items in need of backing up")

@backup_level(18, "site tag avs", "all AV files in website tag folders")
def find_all_tag_content() -> list[dict]:
  ret = []
  for tag in website.tags:
    all_files = find_files_for_tag(tag.slug, include_av=True)
    random.shuffle(all_files)
    ret.extend(all_files)
  return ret

@backup_level(12, "nonsite unreads", "unread, non-av files in tags below site-level")
def find_nonwebsite_tag_files() -> list[dict]:
  FOLDERS_DATA = gdrive.FOLDERS_DATA()
  folder_slugs = set(FOLDERS_DATA.keys()) - set(gdrive.UNIMPORTANT_SLUGS) - set(tag.slug for tag in website.tags)
  ret = []
  include_folders = {
    TagFolderTypes.UNREAD,
  }
  for tag_slug in folder_slugs:
    all_files = find_files_for_tag(tag_slug, include_folders=include_folders)
    ret.extend(all_files)
  random.shuffle(ret)
  return ret

@backup_level(24, "site-unread av", "avs in unread site folders")
def find_all_private_subsitetag_content() -> list[dict]:
  include_folders={
    TagFolderTypes.UNREAD,    
  }
  ret = []
  for tag in website.tags:
    all_files = find_files_for_tag(tag.slug, include_av=True, include_folders=include_folders)
    random.shuffle(all_files)
    ret.extend(all_files)
  return ret

add_backup_level(30, "Medium", "All items in active need of backing up")

@backup_level(33, 'to go throughs', "openaccess content I've marked as next up to consider")
def find_to_go_through_files() -> list[dict]:
  ret = query_my_cache("parent_id = ?", ('1PXmhvbReaRdcuMdSTuiHuWqoxx-CqRa2',))
  ret.extend(query_parent_name(BULK_PDF_FOLDER_NAMES[BulkPDFType.TO_GO_THROUGH]))
  return ret

@backup_level(36, "all tag", "Catches all files in any tag-related folder")
def find_nonwebsite_tag_files() -> list[dict]:
  FOLDERS_DATA = gdrive.FOLDERS_DATA()
  folder_slugs = set(FOLDERS_DATA.keys()) - set(gdrive.UNIMPORTANT_SLUGS)
  ret = []
  include_folders = {t.value for t in TagFolderTypes} # get everything
  for tag_slug in folder_slugs:
    all_files = find_files_for_tag(tag_slug, include_av=True, include_folders=include_folders)
    ret.extend(all_files)
  random.shuffle(ret)
  return ret

@backup_level(57, "academia.edu", "unsorted PDFs from Academia.edu")
def find_academia_edu_pdfs() -> list[dict]:
  return query_parent_name(BULK_PDF_FOLDER_NAMES[BulkPDFType.ACADEMIA_EDU])

add_backup_level(60, "Low", "All valuable items, even backed up elsewhere")

@backup_level(66, 'core api', "The PDFs pulled from CORE yet unsorted")
def find_unsorted_core_pdfs() -> list[dict]:
  return query_parent_name(BULK_PDF_FOLDER_NAMES[BulkPDFType.CORE_API])

@backup_level(72, 'rejects', "actively rejected from the library")
def find_rejected_files() -> list[dict]:
  return query_my_cache("parent_id = ?", (gdrive.REJECTS_FOLDER_ID,))

@backup_level(78, "all obu files", "every descendant of the library roots")
def find_all_obu_files(filter_fn: Callable[[dict], bool]=None) -> list[dict]:
  ret = []
  folders_data = gdrive.FOLDERS_DATA()
  folders = deque([
    gdrive.folderlink_to_id(folders_data['root']['public']),
    gdrive.folderlink_to_id(folders_data['root']['private']),
  ])
  seen_folders = set()
  seen_files = set()
  while folders:
    folder_id = folders.popleft()
    if not folder_id or folder_id in seen_folders:
      continue
    seen_folders.add(folder_id)
    this_ret = []
    children = gdrive.gcache.get_children(folder_id)
    for child in children:
      if child['mimeType'] == 'application/vnd.google-apps.folder':
        if child['name'] not in BULK_PDF_FOLDER_NAMES.values():
          folders.append(child['id'])
        continue
      if child.get('shortcutDetails'):
        if child['shortcutDetails']['targetId'] in seen_files:
          continue
        child = gdrive.gcache.get_item(child['shortcutDetails']['targetId'])
        if not child:
          continue
      else:
        if child['id'] in seen_files:
          continue
      seen_files.add(child['id'])
      if not filter_fn or filter_fn(child):
        this_ret.append(child)
    random.shuffle(this_ret)
    ret.extend(this_ret)
  return ret

@backup_level(15, "obu pdfs", "All PDFs in the OBU hierarchy")
def find_all_obu_pdfs() -> list[dict]:
  return find_all_obu_files(lambda f: f['mimeType'] == 'application/pdf')

@backup_level(9, "one offs", "A few docs not elsewhere covered")
def list_one_off_docs() -> list[dict]:
  return [
    gdrive.gcache.get_item(fid) for fid in [
      '1TN6KzqD7-dEwcEJ9cs9qykuUHT_QRMpm7TVD8cT_biU',
      '1NNlHLr928Mb-NRiJKjZxdwTrsYY7cSZdR_3KulvjiYA',
      '1Yi6evYG0NsdYzVBO7o8XrCIHo3dApJ4DmlXraerzZFw',
    ]
  ]

@backup_level(45, "obu docs", "All epubs and other text document types")
def find_all_obu_text_docs() -> list[dict]:
  DOC_EXTS = {
    'epub',
    'docx',
    'doc',
    'txt',
    'odt',
    'mobi',
    'xlsx',
    'azw',
    'azw3',
    'kfx',
    'rtf',
    'fb2',
    'djvu',
    'cbz',
    'html',
    'csv',
    'tsv',
    'md',
  }
  return find_all_obu_files(lambda f: f['name'].split('.')[-1].lower() in DOC_EXTS)

@backup_level(51, "obu audio", "All audio files in the OBU library")
def find_all_obu_audio_files() -> list[dict]:
  return find_all_obu_files(lambda f: f['mimeType'].startswith('audio'))

@backup_level(59, "obu video", "All video files in the OBU library")
def find_all_obu_audio_files() -> list[dict]:
  return find_all_obu_files(lambda f: f['mimeType'].startswith('video'))

@backup_level(84, "google docs", "My manually created Docs and Sheets")
def find_manual_docs() -> list[dict]:
  with gdrive.gcache._lock:
    ret = gdrive.gcache.cursor.execute(
      """
      SELECT file.*
      FROM drive_items file
      LEFT JOIN item_properties prop
      ON prop.file_id = file.id
        AND prop.key = 'url'
      WHERE prop.file_id IS NULL
        AND file.shortcut_target IS NULL
        AND file.owner = 1
        AND file.mime_type IN (?, ?);
      """,
      ('application/vnd.google-apps.spreadsheet', 'application/vnd.google-apps.document')
    ).fetchall()
  ret = [gdrive.gcache.row_dict_to_api_dict(dict(row)) for row in ret]
  random.shuffle(ret)
  return ret

@backup_level(90, "youtube", "JSON Files pulled from the YouTube API")
def find_youtube_metadata() -> list[dict]:
  return query_my_cache("parent_id = ?", (gdrive.YOUTUBE_METADATA_FOLDER_ID,))

add_backup_level(100, "Comprehensive", "All reasonable items")

@backup_level(106, 'old versions', 'slated for eventual deletion anyway')
def find_old_versions() ->  list[dict]:
  return query_my_cache("parent_id = ?", (gdrive.OLD_VERSIONS_FOLDER_ID,))

@backup_level(112, "google docs", "All GDocs, including the autogenerated ones")
def find_all_gdocs() -> list[dict]:
  return query_my_cache("mime_type = ?", ('application/vnd.google-apps.document',))

@backup_level(118, "pkl files", "All files ending in .pkl (e.g. NORMALIZED_TEXT_FOLDER)")
def find_all_pkl_files() -> list[dict]:
  return query_my_cache("name LIKE '%.pkl'")

@backup_level(126, "All Owned", "Literally every file I own")
def find_all_my_files() -> list[dict]:
  return query_my_cache("")

@backup_level(127, "All Accessible", "Also backs up files shared with OBU")
def find_all_shared_files() -> list[dict]:
  return query_cache("owner > 1")

SEEN_IDS = ThreadSafeSet() # Make sure we only `download_file_to_cache` at most once per run
def download_file_to_cache(file: dict, verbose=False) -> str | None:
    """Will try its best, following shortcuts, exporting docs, etc."""
    if file['id'] in SEEN_IDS:
      return None
    _, _, freespace = shutil.disk_usage(gdrive.gcache.file_cache_dir)
    if freespace < file['size'] + MIN_FREE_SPACE:
      raise OSError(f"We've filled up the disk as much as I'm confortable with")
    SEEN_IDS.add(file['id'])
    return gdrive.gcache.download_file_to_cache(file)

def run_backup_level(level: BackupLevel, parallelism=14):
  print(f"Starting backup level {level.level} ({level.name})...")
  with yaspin(text="Identifying files..."):
    files = level.find_files()
  graceful_threadmap(download_file_to_cache, files, unit='f', max_workers=parallelism)
  print(f"Done backing up to level {level.level}!")

def sideload_file(file: Path, cache_dir: Path, parent_folder: str | None, move: bool, check: bool):
  """moves (or copies, if not `move`) `file` into `cache_dir`
  
  If the file doesn't exist in `gdrive.gcache` then it's uploaded to `parent_folder` (else skipped)"""
  assert cache_dir.is_dir()
  hashval = md5(file)
  target_path = gdrive.gcache.get_cache_path_for_md5(hashval)
  if not target_path:
    if not parent_folder:
      print(f"WARNING: Skipping untracked file {file}")
      return
    newid = gdrive.gcache.upload_file(file, folder_id=parent_folder)
    target_path = gdrive.gcache.get_cache_path_for_md5(hashval)
    assert target_path is not None
  assert target_path.suffix == file.suffix.lower(), f"How did we get a different extension {target_path.suffix} for {file}?"
  is_in_trash = target_path.parent.parent.parent.name == 'trash'
  if is_in_trash:
    if target_path.exists() and md5(target_path) != hashval:
      new_path = target_path.with_stem(file.stem)
      if new_path.exists() and md5(new_path) != hashval:
        raise FileExistsError(f"{new_path} also exists with a different file. Idk what to do now")
      target_path = new_path
    print(f"WARNING: File was trashed. Placing in {target_path}")
  if target_path.exists():
    if not check or md5(target_path) == hashval:
      if move:
        file.unlink()
      return
    print(f"Found corrupted: {target_path}")
    target_path.unlink()
  target_path.parent.mkdir(exist_ok=True, parents=is_in_trash)
  if move:
    shutil.move(src=file, dst=target_path)
  else:
    shutil.copy2(file, target_path)


def sideload_main(
  files: Collection[Path],
  parent_folder: str | None = None,
  move: bool = True,
  recurse: bool = False,
  check: bool = False,
):
  if parent_folder:
    if parent_folder.startswith(gdrive.FOLDER_LINK_PREFIX):
      parent_folder = gdrive.folderlink_to_id(parent_folder)
    folder = gdrive.gcache.get_item(parent_folder)
    if not folder:
      raise ValueError(f"Folder with ID {parent_folder} not found")
    if folder['mimeType'] != 'application/vnd.google-apps.folder':
      raise ValueError(f"{parent_folder} is not a Google Drive Folder, but a {folder['mimeType']}")
  to_remove = set()
  for file in files:
    if not file.exists():
      raise FileNotFoundError(file)
    if file.is_dir():
      if not recurse:
        raise ValueError(f"{file} is a directory! Please specify files or use -r")
      to_remove.add(file)
      for child in file.iterdir():
        files.append(child)
  files = [f for f in files if f not in to_remove]
  if len(files) > 1:
    file_iter = tqdm(files)
  else:
    file_iter = iter(files)
  for file in file_iter:
    sideload_file(file, gdrive.gcache.file_cache_dir, parent_folder, move, check)

def get_saved_backup_level() -> int | None:
  with gdrive.gcache._lock:
    row = gdrive.gcache.cursor.execute(
      "SELECT value FROM metadata WHERE key = 'backup_level';"
    ).fetchone()
    if row:
      return int(row['value'])
    return None

def save_backup_level(level: int):
  with gdrive.gcache._lock:
    gdrive.gcache.cursor.execute(
      "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
      ('backup_level', str(level), )
    )
    gdrive.gcache.conn.commit()

def backup_main(from_level: int=0, new_max_level: int | None=None, parallelism: int=0):
  import sys
  if new_max_level is not None:
    save_backup_level(new_max_level)
    max_level = new_max_level
  else:
    max_level = get_saved_backup_level()
    if max_level is None:
      print("ERROR: No backup level supplied and no previous level found in the database. Please provide a --level.", file=sys.stderr)
      sys.exit(1)
  if max_level == 0:
    print('The cache is set to "cach only" mode. Nothing further to do.')
    sys.exit(0)
  print(f"Will now back up GDrive to a level {max_level}")
  for level in BACKUP_LEVELS.values():
    if not level.finder:
      continue
    if level.level < from_level:
      print(f"Skipping level {level.level} {level.name}")
      continue
    if level.level > max_level:
      break
    if parallelism < 1:
      parallelism = 14
    run_backup_level(level, parallelism=parallelism)
  print(f"All files with priority <= {max_level} are now saved locally!")

def print_backup_levels_list(statistics: bool=False):
  """`statistics` replaces the generic description with current fill level stats"""
  print("\033[1mGoogle Drive Backup Levels\033[0m")
  print(
"""
Backing up to a level 'n' includes all levels < n, so each level includes the levels above it in the chart below.

The bold levels are semantic breakpoints which add no content themselves. You're encouraged to pick one of these levels but are welcome to pick any integer you like between 0 and 127. If new levels are added in the future, they'll be added in between the existing levels at the appropriate priority.

The current backup levels are as follows:
"""
  )
  seen_file_ids = set()
  cum_sum_size = 0
  cum_sum_dl_size = 0

  if statistics:
    print(f"\033[4m  Lvl: {'Level Name':<16}{'This Level':^27} {'Cummulative':^27}\033[0m")
  else:
    print(f"\033[4m  Lvl: {'Level Name':<16}{'Est. Size':>9} - {'Description'}\033[0m")
  for lvl, bl in BACKUP_LEVELS.items():
    if bl.finder is None:
      print(f"\033[1m  {lvl:3d}: {'^'+bl.name+'^':<16}{"\"" if (bl.level or statistics) else "0 B":^9} - {bl.description if not statistics else ''}\033[0m")
    else:
      files = bl.finder()
      this_level_inc_size = 0
      this_level_overlap_size = 0
      this_level_overlap_dl_size = 0
      this_level_inc_dl_size = 0
      while files:
        file = files.pop()
        target_path = gdrive.gcache.get_cache_path_for_file(file)
        if not target_path:
          continue
        if file['id'] in seen_file_ids:
          this_level_overlap_size += file['size']
          if statistics and target_path.exists():
            this_level_overlap_dl_size += file['size']
        else:
          this_level_inc_size += file['size']
          seen_file_ids.add(file['id'])
          if statistics and target_path.exists():
            this_level_inc_dl_size += file['size']
      cum_sum_size += this_level_inc_size
      cum_sum_dl_size += this_level_inc_dl_size
      if statistics:
        if this_level_inc_size+this_level_overlap_size > 0:
          this_level_dl_size = float(this_level_inc_dl_size+this_level_overlap_dl_size)
          this_level_total_size = this_level_inc_size+this_level_overlap_size
          this_level_percent = f"{this_level_dl_size/this_level_total_size:.1%}"
          this_level_col = f"{this_level_percent} ({format_size(this_level_dl_size)}✓"
          this_level_missing = this_level_total_size-this_level_dl_size
          if this_level_missing > 10000:
            this_level_col += f" {format_size(this_level_missing)}𐄂"
          this_level_col += ")"
          cum_percent = f"{cum_sum_dl_size/cum_sum_size:.1%}"
          cum_col = f"{cum_percent} @ +{format_size(this_level_inc_dl_size)} / {format_size(this_level_inc_size)}"
          description = f"{this_level_col:<27} {cum_col:<27}"
        else:
          description = f"     [N/A]"
      else:
        description = f"{format_size(cum_sum_size):>9} - {bl.description}"
      print(f"  {lvl:3d}: {bl.name:<16}{description}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
      description="Utilities for managing gdrive's local file cache",
    )
    subparsers = parser.add_subparsers(dest="command")

    def backup_level(value):
        ivalue = int(value)
        if ivalue < 0:
          raise argparse.ArgumentTypeError(f"{value} is a negative int")
        if ivalue > 127:
          raise argparse.ArgumentTypeError(f"{ivalue} is too large to be a valid backup level. Use --list-levels to see valid levels and their meaning.")
        return ivalue

    levels = subparsers.add_parser("levels", help="Print information about the backup levels")
    levels.add_argument(
      '--stats',
      action="store_true",
      default=False,
      help="Instead of the description, print stats about the cache at each level"
    )

    backup = subparsers.add_parser("backup", help="Download files from Drive to the cache")
    backup.add_argument(
      "--to-level", '-l',
      required=False,
      dest="level",
      type=backup_level,
      default=None,
      help="Sets the max priority level for the files this cache should backup. Backup levels <= this value will be run.",
    )
    backup.add_argument(
      "--from-level",
      required=False,
      dest="from_level",
      default=0,
      type=int,
      help="Skip levels less than this (this run only)",
    )
    backup.add_argument(
      "--threads", "-t",
      required=False,
      default=0,
      type=int,
      help="How many files to download at the same time",
    )

    sideload = subparsers.add_parser("sideload", help="Sideload files to the cache")
    sideload.add_argument("files", nargs="+", help="Files to sideload", type=Path)
    sideload.add_argument(
        "--upload-to", "-p",
        required=False,
        dest="parent_folder",
        type=str,
        default=None,
        help="Upload missing files to this Google Drive folder (link or ID). By default, missing files are ignored."
    )
    sideload.add_argument(
        "--copy",
        action="store_true",
        help="Copy files in (default: move)",
        default=False,
    )
    sideload.add_argument(
      "--recursive", "-r",
      action="store_true",
      help="Allow sideload to crawl directories",
      default=False,
    )
    sideload.add_argument(
      '--replace', '-f',
      action="store_true",
      default=False,
      help="Don't assume the existing cache files are good",
    )

    args = parser.parse_args()

    if not gdrive.gcache.file_cache_dir:
      gdrive.gcache.set_file_cache_dir()

    if args.command == "sideload":
      sideload_main(args.files, args.parent_folder, move=(not args.copy), recurse=args.recursive, check=args.replace)
      sys.exit(0)
    
    with yaspin(text="Loading website data..."):
      website.load()
      website.data.linked_ids = set()
      for item in website.content:
        if not item.get('external_url') and not item.get('file_links'):
          continue
        for drive_link in item.get('drive_links', []):
          website.data.linked_ids.add(
            gdrive.link_to_id(drive_link)
          )
    
    if args.command == "levels":
      print_backup_levels_list(statistics=args.stats)
    elif args.command == "backup":
      backup_main(from_level=args.from_level, new_max_level=args.level, parallelism=args.threads)
    else:
      parser.print_help()
