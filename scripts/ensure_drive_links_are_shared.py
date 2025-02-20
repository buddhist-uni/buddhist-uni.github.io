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
gdrive.ensure_these_are_shared_with_everyone(all_public_gids)

print("Done!")