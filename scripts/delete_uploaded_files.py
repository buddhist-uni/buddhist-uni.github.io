#!/bin/python3

import argparse
from pathlib import Path

from gdrive import has_file_already

def test_and_maybe_delete(file: Path, doit=True, recurse=True):
  if file.is_dir():
    if not recurse:
      raise RuntimeError(f"{str(file)} is a directory and recusion not set.")
    for child in file.iterdir():
      test_and_maybe_delete(child, doit=doit)
    return
  if not file.is_file():
    print(f"Bad file {str(file)}!")
    print("  Skipping...")
    return
  print(f"\nExamining {str(file)}...")
  has = has_file_already(file)
  if has:
    print("  Found it!")
    if doit:
      print("  ! Deleting!")
      file.unlink()
    else:
      print("  Would delete if not for dry_run!")

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Deletes files iff they have been uploaded to GDrive already.')
  parser.add_argument('files', metavar='file', type=Path, nargs='+',
    help='The path or file to consider')
  parser.add_argument('-r', '--recursive', dest='recurse', action='store_true',
    help='All files in directory and subdirectories')
  parser.add_argument('--dry-run', dest='doit', action="store_false", default=True, help="Don't actually delete anything")
  args = parser.parse_args()
  for file in args.files:
    test_and_maybe_delete(file, doit=args.doit, recurse=args.recurse)
