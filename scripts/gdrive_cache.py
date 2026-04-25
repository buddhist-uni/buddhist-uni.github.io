#!/bin/python3

from collections.abc import Collection, Iterable
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Optional, Any
from tqdm import tqdm
import gdrive
import shutil
from strutils import (
  md5,
)

class BackupLevel:
  def __init__(self, level: int, name: str, description: str, finder: Optional[Callable[[], Iterable[Any]]] = None):
    self.level = level
    self.name = name
    self.description = description
    self.finder = finder

  def find_files(self) -> Iterable[Any]:
    """Finds and yields/returns the files to be backed up at this level."""
    if self.finder:
      return self.finder()
    return []

BACKUP_LEVELS: OrderedDict[int, BackupLevel] = OrderedDict()

def add_backup_level(level: int, name: str, description: str, finder: Optional[Callable[[], Iterable[Any]]] = None):
  global BACKUP_LEVELS
  BACKUP_LEVELS[level] = BackupLevel(level, name, description, finder)
  BACKUP_LEVELS = OrderedDict(sorted(BACKUP_LEVELS.items()))

def backup_level(level: int, name: str, description: str):
  """Decorator to register a function as a backup level finder."""
  def decorator(func: Callable[[], Iterable[Any]]):
    add_backup_level(level, name, description, func)
    return func
  return decorator

# Dummy levels
add_backup_level(10, "High", "High priority backup items")
add_backup_level(30, "Medium", "Medium priority backup items")
add_backup_level(60, "Low", "Low priority backup items")
add_backup_level(100, "Comprehensive", "All reasonable items to backup")
add_backup_level(126, "Exhaustive", "Literally everything")

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

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
      description="Utilities for managing gdrive's local file cache",
    )
    subparsers = parser.add_subparsers(dest="command")

    def non_negative_int(value):
        ivalue = int(value)
        if ivalue < 0:
            raise argparse.ArgumentTypeError(f"{value} is an invalid non-negative int value")
        return ivalue

    backup = subparsers.add_parser("backup", help="Download files from Drive to the cache")
    backup.add_argument(
      "--level", '-l',
      required=False,
      dest="level",
      type=non_negative_int,
      default=None,
      help="Sets the max priority level for the files this cache should backup",
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
        # TODO: Implement backup logic here based on args.level
        pass
    else:
      parser.print_help()
