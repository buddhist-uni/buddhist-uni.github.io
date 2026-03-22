#!/bin/python3
#
## OpenAlex Downloader
#
# Uses the openalex.org API to download
# OpenAccess PDFs matching a query but
# prompts the user (y/n) before each
# with all the metadata you'd need to
# decide if that's a file you want.
# Pauses to let you download it manually
# if the url points to a landing page.
#
# To use, update APIURL below
# Update User-Agent for fewer 403s

from downloadutils import (
  assert_cd_is_writable,
  download,
  HOSTNAME_BLACKLIST,
  pdf_name_for_work,
)
from openaleximporter import (
  make_library_entry_for_work,
  alt_url_for_work,
  OPENALEX_CREDS,
  print_openalex_work,
)
import openalextopics as topics
import journals

NOT_IN_TRACKING_JOURNALS = ",".join(f"locations.source.id:!{loc}" for loc in journals.slugs.keys())

# https://docs.openalex.org/
#APIURL = "https://api.openalex.org/works?filter=is_oa:true,is_paratext:false,type:!book,type:!monograph,locations.source.id:S47477353,cited_by_count:%3E2&per_page=50&page=7&sort=cited_by_count:desc"
APIURL=f"https://api.openalex.org/works?{OPENALEX_CREDS}filter=is_oa:true,language:en,is_paratext:false,type:!book,type:!review,type:!dataset,"+NOT_IN_TRACKING_JOURNALS+f",keywords.id:buddhism,cited_by_count:%3E10&per_page=100&page=8&sort=cited_by_count:desc"
#APIURL="https://api.openalex.org/works?filter=title.search:Gatsby,is_oa:true,is_paratext:false&sort=cited_by_count:desc"
#APIURL = "https://api.openalex.org/works?filter=cites:W1599632106,is_oa:true"

import os
import json
from strutils import (
  prompt,
  FileSyncedSet,
  trunc,
)
from pathvalidate import sanitize_filename

import gdrive

METADATA_DIR = os.path.expanduser(os.path.normpath("~/.local/share/openalexdownloader"))
PLACE_FILE = os.path.join(METADATA_DIR, "place.json")
SEEN_FILE = os.path.join(METADATA_DIR, "works_seen.txt")


# The Main Script

if __name__ == "__main__":
  os.makedirs(METADATA_DIR, exist_ok=True)
  metadata = {"i": 0, "url": None}
  if os.path.exists(PLACE_FILE):
     with open(PLACE_FILE) as fd:
       metadata = json.load(fd)
  else:
    if not prompt(f"Will dump all files to \"{os.getcwd()}\" Is this okay?", "y"):
      quit(1)
  assert_cd_is_writable()
  if not os.path.exists("works.json") or metadata["url"] != APIURL:
    if download(APIURL, "works.json"):
      metadata["i"] = 0
      metadata["url"] = APIURL
  with open("works.json") as fd:
    data = json.load(fd)
  try:
    total = len(data["results"])
  except KeyError:
    print("Error accessing the API:")
    print(json.dumps(data))
    os.remove("works.json")
    quit(1)
  works_seen = FileSyncedSet(SEEN_FILE, lambda w: w['id'].split('/')[-1])
  for index in range(metadata["i"], total):
    metadata["i"] = index
    with open(PLACE_FILE, "w") as fd:
      json.dump(metadata, fd)
    work = data["results"][index]
    filename = pdf_name_for_work(work)
    url = work['open_access']['oa_url']
    alturl = alt_url_for_work(work, url)
    if (not url) or (url.split("/")[2] in HOSTNAME_BLACKLIST):
      url = work["doi"]
    if not (work["doi"] == url or alturl):
      alturl = work["doi"]
    if not url:
      url = alturl
      alturl = None
    if not url:
      print(f"\n{index+1}/{total} - {trunc(filename, 20)} cannot be downloaded...")
      works_seen.add(work)
      continue
    if work in works_seen:
      # TODO: maybe include a titlematch.py check here against Google Drive?
      print(f"\n{index+1}/{total} - {trunc(filename, 20)} already seen before...")
      if work not in works_seen:
        works_seen.add(work)
      continue
    if os.path.exists(filename):
      print(f"\n{index+1}/{total} - {trunc(filename, 20)} already downloaded...")
      works_seen.add(work)
      continue
    print(f"\n{index+1}/{total} - {work['type']} - {work['id'].split('/')[-1]}")
    print_openalex_work(work, indent=2)
    # you can fully automate by replacing prompt below with your inclusion criteria
    # for example all but titles in a blacklist, do:
    # if not any(map(lambda w: w in work['title'].lower(), ["introduction", "review", "editor", etc]):
    if prompt(f"Download {index+1}?", "n"):
      succ = download(url, filename)
      if not succ and alturl:
        print("Trying another url...")
        succ = download(alturl, filename)
      if succ:
        print("Downloaded successfully!")
        entrypath = make_library_entry_for_work(work, draft=True)
      else:
        print("Download failed.")
        if prompt("Would you like to make an entry for it anyway?", 'n'):
          url = input("Use a different url (leave blank for no)?")
          if url:
            work['open_access']['oa_url'] = url
          entrypath = make_library_entry_for_work(work, draft=True)
        else:
          entrypath = None
          if ((work.get('primary_location') or {}).get('source') or {}).get('id'):
            print(f"In case you want to blacklist it, the source.id was: {work['primary_location']['source']['id'].split('/')[-1]}")
      if entrypath:
        print(f"Wrote a draft entry to {entrypath}")
    works_seen.add(work)
  print("Finished url:")
  print(metadata["url"])
  input("Press enter to exit :)")
  os.remove("works.json")
