#!/bin/python3

from collections.abc import Collection
from collections import OrderedDict, deque
import random
from mimetypes import guess_extension
from pathlib import Path
from typing import Callable, Optional
from tqdm import tqdm
import gdrive_base
import gdrive
import shutil
from strutils import (
  md5,
)
from executils import graceful_threadmap
from yaspin import yaspin
import googleapiclient.errors as gerrors
from bulk_import import BULK_PDF_FOLDER_NAMES, BulkPDFType
import website

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
add_backup_level(10, "High", "All valuable items in need of backing up")
add_backup_level(30, "Medium", "All items in active need of backing up")

@backup_level(54, 'eks', "The Ezra Klein Show Archive")
def find_eks_files() -> list[str]:
  return gdrive.gcache.parent_sql_query(
    "parent.parent_id = '1_HQsNoi2teB7SzbFX7vMniL01ZGttHuF'"
  )

@backup_level(57, "academia.edu", "unsorted PDFs from Academia.edu")
def find_academia_edu_pdfs() -> list[dict]:
  return query_parent_name(BULK_PDF_FOLDER_NAMES[BulkPDFType.ACADEMIA_EDU])

add_backup_level(60, "Low", "All valuable items, including those backed up elsewhere")

@backup_level(66, 'core api pdfs', "The PDFs pulled from CORE yet unsorted")
def find_unsorted_core_pdfs() -> list[dict]:
  return query_parent_name(BULK_PDF_FOLDER_NAMES[BulkPDFType.CORE_API])

@backup_level(72, 'rejects', "Saves files actively rejected from the library")
def find_rejected_files() -> list[dict]:
  return query_my_cache("parent_id = ?", (gdrive.REJECTS_FOLDER_ID,))

@backup_level(78, "all OBU files", "Attempts to save every descendant of the library roots")
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

@backup_level(39, "obu pdfs", "All PDFs in the OBU hierarchy")
def find_all_obu_pdfs() -> list[dict]:
  return find_all_obu_files(lambda f: f['mimeType'] == 'application/pdf')

@backup_level(40, "one offs", "A few docs not elsewhere covered")
def list_one_off_docs() -> list[dict]:
  return [
    gdrive.gcache.get_item(fid) for fid in [
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

@backup_level(84, "google docs and sheets", "My manually created docs")
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

@backup_level(90, "youtube metadata", "JSON Files pulled from the YouTube API")
def find_youtube_metadata() -> list[dict]:
  return query_my_cache("parent_id = ?", (gdrive.YOUTUBE_METADATA_FOLDER_ID,))

add_backup_level(100, "Comprehensive", "All reasonable items")

@backup_level(106, 'old versions', 'download the old versions slated for deletion anyway')
def find_old_versions() ->  list[dict]:
  return query_my_cache("parent_id = ?", (gdrive.OLD_VERSIONS_FOLDER_ID,))

@backup_level(112, "google docs", "All Google Docs, including the autogenerated ones")
def find_all_gdocs() -> list[dict]:
  return query_my_cache("mime_type = ?", ('application/vnd.google-apps.document',))

@backup_level(118, "pkl files", "All files ending in .pkl (usually these are cached in NORMALIZED_TEXT_FOLDER)")
def find_all_pkl_files() -> list[dict]:
  return query_my_cache("name LIKE '%.pkl'")

@backup_level(126, "All Owned", "Literally every file I own")
def find_all_my_files() -> list[dict]:
  return query_my_cache("")

@backup_level(127, "All Accessible", "Also backs up files shared with OBU")
def find_all_shared_files() -> list[dict]:
  return query_cache("owner > 1")

def download_file_to_cache(file: dict, verbose=True) -> str | None:
    """Will try its best, following shortcuts, exporting docs, etc."""
    if file['mimeType'] == 'application/vnd.google-apps.shortcut':
      file = gdrive.gcache.get_item(file['shortcutDetails']['targetId'])

    is_gdoc = file['mimeType'] == 'application/vnd.google-apps.document'
    is_gsheet = file['mimeType'] == 'application/vnd.google-apps.spreadsheet'
    if is_gdoc or is_gsheet:
      hashval = md5(file['id'] + str(file['version']))
    else:
      hashval = file.get('md5Checksum')
      if not isinstance(hashval, str):
        return None
    assert len(hashval) == 32
    
    if is_gdoc:
      extension = '.docx'
    elif is_gsheet:
      extension = '.xlsx'
    elif '.' in file.get('name', ''):
      extension = '.' + str(file['name']).split('.')[-1].lower()
    else:
      extension = guess_extension(file['mimeType']) or ''
      
    cache_dir = gdrive.gcache.file_cache_dir
    assert isinstance(cache_dir, Path)
    target_path = cache_dir / hashval[:2] / f"{hashval[2:]}{extension}"
    if target_path.exists():
      print(f"  Skipping already downloaded {file['name']}")
      return str(target_path)
    target_path.parent.mkdir(exist_ok=True)
    if verbose:
      print(f"  Downloading {file['name']}")
    if not (is_gdoc or is_gsheet):
      try:
        gdrive_base.download_file(file['id'], target_path, verbose=False)
      except FileNotFoundError as e:
        if target_path.exists():
          # Another thread got this file before us 😅
          pass
        else:
          raise e
    else:
      try:
        if is_gdoc:
          gdrive_base.download_gdoc_as_docx(file['id'], target_path)
        elif is_gsheet:
          gdrive_base.download_gsheet_as_xlsx(file['id'], target_path)
      except gerrors.HttpError as e:
        if "exportSizeLimitExceeded" in str(e):
          if verbose:
            print(f"  Skipping {file['name']}: it's too large to be exported :(")
          return None
        if "cannot be exported" in str(e):
          return None
        raise e
    if verbose:
      print(f"  Saved to {target_path.parent.name}/{target_path.name}")
    return str(target_path)

def run_backup_level(level: BackupLevel, parallelism=6):
  print(f"Starting backup level {level.level} ({level.name})...")
  with yaspin(text="Identifying files..."):
    files = level.find_files()
  graceful_threadmap(download_file_to_cache, files, unit='f', max_workers=parallelism)
  print(f"Done backing up to level {level.level}!")

def sideload_file(file: Path, cache_dir: Path, parent_folder: str | None, move: bool):
  """moves (or copies, if not `move`) `file` into `cache_dir`
  
  If the file doesn't exist in `gdrive.gcache` then it's uploaded to `parent_folder` (else skipped)"""
  assert cache_dir.is_dir()
  hashval = md5(file)
  remote_files = gdrive.gcache.get_items_with_md5(hashval)
  if not remote_files:
    if not parent_folder:
      print(f"WARNING: Skipping untracked file {file}")
      return
    newid = gdrive.gcache.upload_file(file, folder_id=parent_folder)
    remote_files = [gdrive.gcache.get_item(newid)]
  target_path = cache_dir / hashval[:2] / f"{hashval[2:]}{file.suffix.lower()}"
  if target_path.exists():
    if md5(target_path) == hashval:
      if move:
        file.unlink()
      return
    print(f"WARNING: Overwriting old, corrupted {target_path}")
    target_path.unlink()
  target_path.parent.mkdir(exist_ok=True)
  if move:
    file.rename(target_path)
  else:
    shutil.copy2(file, target_path)


def sideload_main(files: Collection[Path], parent_folder: str | None = None, move: bool = True):
  if parent_folder:
    if parent_folder.startswith(gdrive.FOLDER_LINK_PREFIX):
      parent_folder = gdrive.folderlink_to_id(parent_folder)
    folder = gdrive.gcache.get_item(parent_folder)
    if not folder:
      raise ValueError(f"Folder with ID {parent_folder} not found")
    if folder['mimeType'] != 'application/vnd.google-apps.folder':
      raise ValueError(f"{parent_folder} is not a Google Drive Folder, but a {folder['mimeType']}")
  if len(files) > 100:
    file_iter = tqdm(files)
  else:
    file_iter = iter(files)
  for file in file_iter:
    if not file.exists():
      print(f"WARNING: {file} does not exist!")
      continue
    if file.is_dir():
      raise ValueError(f"{file} is a directory! Please only specify specific files")
    sideload_file(file, gdrive.gcache.file_cache_dir, parent_folder, move)

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

    backup = subparsers.add_parser("backup", help="Download files from Drive to the cache")
    backup.add_argument(
      "--level", '-l',
      required=False,
      dest="level",
      type=backup_level,
      default=None,
      help="Sets the max priority level for the files this cache should backup. Backup levels <= this value will be run.",
    )
    backup.add_argument(
      "--list-levels",
      action="store_true",
      help="List all available backup levels and exit",
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

    args = parser.parse_args()

    if not gdrive.gcache.file_cache_dir:
      gdrive.gcache.set_file_cache_dir()

    if args.command == "sideload":
      sideload_main(args.files, args.parent_folder, move=(not args.copy))
    elif args.command == "backup":
      if args.list_levels:
        print("Available Backup Levels:")
        for lvl, bl in BACKUP_LEVELS.items():
            if bl.finder is None:
                print(f"\033[1m  {lvl:3d}: {bl.name:<15} - {bl.description}\033[0m")
            else:
                print(f"  {lvl:3d}: {bl.name:<15} - {bl.description}")
      else:
        import sys
        if args.level is not None:
          save_backup_level(args.level)
        else:
          args.level = get_saved_backup_level()
          if args.level is None:
            print("ERROR: No backup level supplied and no previous level found in the database. Please provide a --level.", file=sys.stderr)
            sys.exit(1)
        if args.level == 0:
          print('The cache is set to "cach only" mode. Nothing further to do.')
          sys.exit(0)
        print(f"Will now back up GDrive to a level {args.level}")
        for level in BACKUP_LEVELS.values():
          if not level.finder:
            continue
          if level.level > args.level:
            break
          run_backup_level(level)
        print(f"All files with priority <= {args.level} are now saved locally!")
    else:
      parser.print_help()
