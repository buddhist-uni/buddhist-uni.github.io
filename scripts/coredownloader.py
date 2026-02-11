#!/bin/python3

import journals
from local_core import (
  CoreAPIWorksCache,
)

TRACKING_ISSNS = [issn for val in journals.issns.values() for issn in val] # 268
# but there's a lot of mess here: other languages, review articles... how to filter?

import website
website.load()

DOIS = [(
  c.get('source_url', ''),
  c.get('external_url', ''),
  c.get('doi',''),
  c.get('alternate_doi', ''),
) for c in website.content]
DOIS = [
  doi.split('doi.org/')[1]
  for doilist in DOIS
  for doi in doilist
  if 'doi.org/' in doi
]
# 95 of the above have fullText

# "Buddhist" articles that aren't for download
MDPI_PROVIDER_ID = 22080 # 351
ANTI_TRACKING_KEYWORDS = [
  "1556-5068", # SSRN ISSN. 236
  "NFTs", # 166
  "blockchain", # 869
  "documentType:review", # 1040
]




