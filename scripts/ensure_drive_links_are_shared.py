#!/bin/python3

import gdrive
import website

website.load()

all_public_gids = []

for page in website.content:
  if page.drive_links:
    for glink in page.drive_links:
      gid = gdrive.link_to_id(glink)
      if gid:
        all_public_gids.append(gid)

print(f"Fetching permissions info about {len(all_public_gids)} Google Drive files...")
all_files = gdrive.batch_get_files_by_id(all_public_gids, "id,name,permissions,ownedByMe")
print("Looking for those missing public permissions...")
for file in all_files:
  if not file['ownedByMe']:
    continue
  is_publicly_shared = False
  for permission in file['permissions']:
    if permission['type'] == 'anyone':
      is_publicly_shared = True
      break
  if not is_publicly_shared:
    print(f"Sharing \"{file['name']}\" with everyone...")
    gdrive.share_drive_file_with_everyone(file['id'])

print("Done!")