#!/bin/python3

from pathlib import Path
import gdrive_base

if __name__ == '__main__':
  import argparse
  parser = argparse.ArgumentParser(
    description="Replace a Google Drive file's contents with a local file's.",
  )
  parser.add_argument(
    'gfile',
  )
  parser.add_argument(
    'lfile',
    type=Path,
  )
  args = parser.parse_args()
  assert args.lfile.is_file()
  gid = gdrive_base.link_to_id(args.gfile)
  assert gid is not None
  gdrive_base.upload_to_google_drive(
    args.lfile,
    update_file=gid,
    verbose=True,
  )
