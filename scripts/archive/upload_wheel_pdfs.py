#!/bin/python3

import gdrive
from pathlib import Path
import json

private_folders = {
  gdrive.folderlink_to_id(v["public"]): gdrive.folderlink_to_id(v["private"])
  for v in json.loads(gdrive.FOLDERS_DATA_FILE.read_text()).values()
}

root = Path("../../../Download/")
for fd in root.iterdir():
  if fd.suffix != ".pdf":
    continue
  print(f"\nLooking for {fd.stem}.epub...")
  epubs = gdrive.files_exactly_named(fd.stem + ".epub")
  if len(epubs) == 0:
    print("  Didn't find it\n  Uploading to Go Through...")
    gdrive.upload_to_google_drive(fd, folder_id="1PXmhvbReaRdcuMdSTuiHuWqoxx-CqRa2")
    continue
  folder = epubs[0]['parents'][0]
  pfolder = private_folders.get(folder)
  print(f"  Found it!\nUploading to {folder}...")
  upload = gdrive.upload_to_google_drive(fd, folder_id=folder)
  if not upload:
    raise RuntimeError("Upload failed")
  if pfolder:
    print("  Creating private shortcut...")
    gdrive.create_drive_shortcut(upload, fd.name, pfolder)
  print("  Deleting uploaded file...")
  fd.unlink()
