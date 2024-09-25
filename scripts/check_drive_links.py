#!/bin/env python3

import gdrive
import website

FIELDS = "id,name,trashed"

website.load()

def fetch_all_content_drive_ids():
  for content in website.content:
    for link in content.get('drive_links',[]):
      gid = gdrive.link_to_id(link)
      if not gid:
        print(f"Warning: Unable to extract id from \"{link}\"")
      else:
        yield gid

if __name__ == "__main__":
  drive_ids = set(gid for gid in fetch_all_content_drive_ids())
  seen_ids = set()
  print("\nChecking drive links:")
  for gfile in gdrive.batch_get_files_by_id(list(drive_ids), FIELDS):
    seen_ids.add(gfile['id'])
    if gfile['trashed']:
      print(f"ERROR! {gdrive.DRIVE_LINK.format(gfile['id'])} is trashed!")
  unseen_ids = drive_ids - seen_ids

