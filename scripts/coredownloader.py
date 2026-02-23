#!/bin/python3

import json
import journals
from yaspin import yaspin
from typing import Any
from tqdm import tqdm
from local_core import (
  CoreAPIWorksCache,
)
import gdrive
import nearestpdf
import titlematch
import website
with yaspin(text="Loading website..."):
  website.load()

nearestpdf.load()

TRACKING_ISSNS = [issn for val in journals.issns.values() for issn in val] # 268
# but there's a lot of mess here: other languages, review articles... how to filter?

# "Buddhist" articles that aren't for download
ANTI_TRACKING_KEYWORDS = [
  "\"1556-5068\"", # SSRN ISSN. 2 # registered as query 3
  "NFTs", # 166
  "blockchain", # 869 # registered as 4
  "documentType:review", # 1040
  "title:review",
]
TRACKING_QUERY_STR = "(title:Buddhist OR abstract:Buddhist) AND fullText:Buddhist"
TRACKING_QUERY_STR += "".join(f" AND -{anti}" for anti in ANTI_TRACKING_KEYWORDS)

core = CoreAPIWorksCache('/home/khbh/Desktop/core_api.db')
TRACKING_QUERY = core.register_query(TRACKING_QUERY_STR)

LOCAL_DOIS: dict[str, str]
LOCAL_DOIS = dict() # mapping doi to drive file id

for website_item in website.content:
  if website_item.formats[0] != 'pdf':
    continue
  if not website_item.get("drive_links"):
    continue
  drive_id = gdrive.link_to_id(website_item['drive_links'][0])
  if drive_id not in nearestpdf.gid_to_idx:
    continue
  dois = [
    doi.split('doi.org/')[1]
    for doi in [
      website_item.get('source_url', ''),
      website_item.get('external_url', ''),
      website_item.get('doi',''),
      website_item.get('alternate_doi', ''),
      website_item.get('alternative_doi', ''),
    ]
    if 'doi.org/' in doi
  ]
  core_work = None
  for doi in dois:
    LOCAL_DOIS[doi] = drive_id

print(f"Attempting to fetch {len(LOCAL_DOIS)} works by DOI...")
bulk_works = core.bulk_get_by_doi(list(LOCAL_DOIS.keys()), max_per_batch=100)

print(f"Associating {len(bulk_works)} Drive files from the website with their CORE Works...")
# This ensures that we won't try to download anything the website knows about
del bulk_works
for doi, drive_id in LOCAL_DOIS.items():
  core_work = core.get_locally_from_doi(doi)
  if not core_work:
    continue
  core.register_gfile_for_work(core_work['id'], drive_id, similarity=0.99)

while core.load_another_page_from_query(TRACKING_QUERY) > 0:
  print("Loading another page...")

