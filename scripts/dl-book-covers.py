#!/bin/python
# Downloads all book covers from openlibrary.org to assets/imgs/covers
# This script is run by .github/workflows/build.yaml

import requests
from strutils import git_root_folder
import website

BOOKCOVER_DIR = git_root_folder.joinpath('assets/imgs/covers')
if not BOOKCOVER_DIR.is_dir():
  BOOKCOVER_DIR.mkdir()

def download_cover(olid):
  response = requests.get(f"https://covers.openlibrary.org/b/olid/{olid}-L.jpg?default=false")
  assert response.status_code == 200
  with open(BOOKCOVER_DIR.joinpath(f"{olid}.jpg"), "wb") as f:
    f.write(response.content)

website.load()
for page in website.content:
  if page.olid:
    if BOOKCOVER_DIR.joinpath(f"{page.olid}.jpg").exists():
      continue
    print(f"Downloading cover for {page.olid}...")
    download_cover(page.olid)
