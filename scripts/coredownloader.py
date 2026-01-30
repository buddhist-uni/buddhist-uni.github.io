#!/bin/python3

import requests
from pathlib import Path
from journals import issns

TOKEN_PATH = Path('~/core-api.key').expanduser()
TOKEN = 'Bearer ' + TOKEN_PATH.read_text().strip()

TRACKING_ISSNS = [issn for val in issns.values() for issn in val] # 268
# but there's a lot of mess here: other languages, review articles... how to filter?

import website
website.load()
DOIS = [c.get('source_url', c.get('external_url', '')) for c in website.content]
DOIS = [doi.split('doi.org/')[1] for doi in DOIS if 'doi.org/' in doi]
# ~113 from these, but they're at least guarenteed

# "Buddhist" articles that aren't for download
MDPI_PROVIDER_ID = 22080 # 351
ANTI_TRACKING_KEYWORDS = [
  "1556-5068", # SSRN ISSN. 236
  "NFTs", # 166
  "blockchain", # 869
  "documentType:review", # 1040
]

def call_api(subpath: str, params: dict):
  url = "https://api.core.ac.uk/v3/" + subpath
  response = requests.get(
    url,
    headers={
      'Authorization': TOKEN,
    },
    params=params,
  )
  match response.status_code:
    case 200:
      return response.json()
    case 429:
      raise NotImplementedError(f"Teach me how to handle rate limits. Got back HEADERS={response.headers}")
    case 504:
      raise ValueError(f"Malformed request {params} to {subpath}")
    case _:
      raise NotImplementedError(f"Unknown status code {response.status_code}:\n\n{response.text}")




