#!/bin/python3

import json
import journals
from yaspin import yaspin
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
MDPI_PROVIDER_ID = 22080 # 351
ANTI_TRACKING_KEYWORDS = [
  "1556-5068", # SSRN ISSN. 2 # registered as query 3
  "NFTs", # 166
  "blockchain", # 869 # registered as 4
  "documentType:review", # 1040
]

core = CoreAPIWorksCache('/home/khbh/Desktop/core_api.db')

self_similarities = []
self_plus_similarities = []
differences = []
title_similarities = []

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
    core_work = core.get_locally_from_doi(doi)
    if core_work:
      break
  if not core_work:
    continue
  if not core_work['full_text']:
    continue
  text_plus = f"{core_work['full_text']} {core_work['title']} {core_work['abstract'] or ''}"
  authors = ''
  try:
    authors = [auth['name'] for auth in json.loads(core_work['authors'])]
  except:
    pass
  matches = nearestpdf.find_matching_files(
    core_work['title'],
    authors,
    text_plus,
  )
  drive_file = nearestpdf.google_files[nearestpdf.gid_to_idx[drive_id]]
  if len(matches) == 1 and matches[0][0]['id'] == drive_id:
    print("Got it with confidence", matches[0][1])
  else:
    import ipdb; ipdb.set_trace()





