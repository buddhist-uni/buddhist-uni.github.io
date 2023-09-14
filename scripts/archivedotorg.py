#!/bin/python3

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from pathlib import Path
import json
import re
import time
from datetime import datetime, timedelta
import os
from strutils import sanitize_string
try:
  from tqdm import tqdm, trange
except:
  print("  pip install tqdm")
  quit(1)
ARCHIVE_ORG_AUTH_FILE = '~/archive.org.auth'

ARCHIVE_ORG_AUTH_PATH = Path(os.path.expanduser(ARCHIVE_ORG_AUTH_FILE))
if ARCHIVE_ORG_AUTH_PATH.exists():
  ARCHIVE_ORG_AUTH = ARCHIVE_ORG_AUTH_PATH.read_text().strip()
else:
  print(f"Please make a new {ARCHIVE_ORG_AUTH_FILE} text file and put in it the information from https://archive.org/account/s3.php in the following format: \"LOW <accesskey>:<secretkey>\"")
  quit(1)

ARCHIVEID_BLACKLIST = {
  "elartedelasabidu0000dala"
}

retry_strategy = Retry(total=2, backoff_factor=0.5)
http_adapter = HTTPAdapter(max_retries=retry_strategy)
archive_org_session = requests.Session()
archive_org_session.mount("https://", http_adapter)
archive_org_session.timeout = 5
archive_org_session.headers['Authorization'] = ARCHIVE_ORG_AUTH
archive_org_session.headers['Accept'] = 'application/json'

def last_archived_datetime(url):
  resp = archive_org_session.head("https://web.archive.org/web/"+str(url))
  if not resp.ok:
    return None
  if not 'x-archive-redirect-reason' in resp.headers:
    return None
  timestamp = resp.headers['x-archive-redirect-reason'].split(' at ')[1]
  return datetime.strptime(timestamp, '%Y%m%d%H%M%S')

def extract_archiveorg_id(item):
  match = re.search(r'https?:\/\/archive.org\/details\/([a-z0-9_-]+)\/?', item)
  if match:
    return match.groups()[0]
  return None

def search_archiveorg_lending_library(query):
  return archive_org_session.get("https://archive.org/advancedsearch.php", params={
      "q": f"collection:inlibrary AND language:eng AND {query}",
      "sort": "lending___available_to_borrow desc, loans__status__max_lendable_copies desc, lending___max_lendable_copies desc",
      "rows": 12,
      "output": "json"
    }).json()['response']

def is_doc_sane_for_work(doc, workinfo):
  return doc['imagecount'] >= workinfo['pages'] and doc['year'] >= workinfo['year'] and doc['identifier'] not in ARCHIVEID_BLACKLIST

class _AO_SearchStrat(object):
  def __init__(self, workinfo):
    self.info = workinfo
  def is_applicable(self):
    return True
  def get_response(self):
    raise NotImplementedError(f"Override the get_response function for {self.__class__}")

class _AO_OLIDSearchStrat(_AO_SearchStrat):
  def is_applicable(self):
    self.olid = None
    if 'olid' in self.info and self.info['olid']:
      print(f"Finding work OLID for {self.info['olid']}...")
      self.olid = openlibrary_edition_to_work_id(self.info['olid'])
      print(f"Got {self.olid}")
    return not not self.olid
     
  def get_response(self):
    print(f"Searching by OLID:{self.olid}...")
    return search_archiveorg_lending_library(f"openlibrary_work:({self.olid})")

class _AO_OCLCSearchStrat(_AO_SearchStrat):
  def is_applicable(self):
    return 'oclc' in self.info and self.info['oclc']
  def get_response(self):
    print(f"Searching by oclc={self.info['oclc']}...")
    return search_archiveorg_lending_library(self.info['oclc'])

class _AO_DefaultSearchStrat(_AO_SearchStrat):
  def get_response(self):
    title = self.info['title'].split(':')[0]
    if title.count(' ') == 0:
      title = self.info['title']
    title = sanitize_string(" ".join(filter(lambda w: "'" not in w and len(w)>2, title.split(" "))))
    author = " ".join(filter(lambda w: len(w)>2, self.info['authors'][0].split("-")[0].split(" ")))
    if author == 'tnh':
      author = "Thich Nhat Hanh"
    print(f"Searching works by title=\"{title}\" and author=\"{author}\" instead...")
    return search_archiveorg_lending_library(f"title:({title}) AND creator:({author})")

def find_lendable_archiveorg_url_for_metadata(workinfo):
  print(f"Searching Archive.org for lendable copies of \"{workinfo['title']}\"...")
  docs = []
  strats = [_AO_DefaultSearchStrat, _AO_OCLCSearchStrat, _AO_OLIDSearchStrat]
  while len(docs) == 0 and len(strats) > 0:
    strat = strats.pop()(workinfo)
    if not strat.is_applicable():
      continue
    ser = strat.get_response()
    print(f"Found {ser['numFound']} lendable work(s): {list(map(lambda a: a['identifier'], ser['docs']))}")
    docs = list(filter(lambda doc: is_doc_sane_for_work(doc, workinfo), ser['docs']))
    if ser['numFound'] > 0 and len(docs) == 0:
      print("But none of those seem suitable...")
  if len(docs) >= 1:
    doc = docs[0]
    print(f"Going with \"{doc['title']}\" by \"{doc.get('creator', 'None')}\" ({doc['year']})")
    return f"https://archive.org/details/{doc['identifier']}/mode/1up"
  print("Unable to find a suitable copy :(")
  return None

def is_archiveorg_item_lendable(itemid):
  resp = archive_org_session.get("https://archive.org/services/availability", params={"identifier": itemid})
  data = resp.json()
  if not resp.ok or not data["success"]:
    raise RuntimeError("Failed to connect to the Archive.org availability API")
  try:
    return data['responses'][itemid]['is_lendable'] or data['responses'][itemid]['status'] == 'open'
  except KeyError:
    message = data['responses'][itemid]['error_message']
    if message == 'not found':
      return False
    raise KeyError(f"Archive.org Availability API returned: \"{message}\"")

def openlibrary_edition_to_work_id(editionid):
  try:
    resp = requests.get(f"https://openlibrary.org/books/{editionid}.json")
    data = resp.json()
  except json.decoder.JSONDecodeError:
    print(f"!! WARNING: Failed to get Work ID for {editionid} with message: \"{resp.text}\"!!!")
    return None
  return data['works'][0]['key'].replace("/works/", "")

def save_url_to_archiveorg(url):
  print(f"Saving {url} to the Wayback Machine now...")
  try:
    resp = archive_org_session.post("https://web.archive.org/save", data={"url": url})
  except:
    print("WARNING: A connection error occurred")
    return False
  if resp.ok and json.loads(resp.text):
    print("Saved!")
    return True
  else:
    print(f"WARNING: Save failed\n\t{resp.headers}\n\tCONTENT:\n\t{resp.text}")
    return False

def archive_urls(urls, skip_urls_archived_in_last_days=365):
  successes = []
  def wait_secs(n):
    print(f"Waiting {n} seconds...")
    for i in trange(n):
      time.sleep(1)
  if skip_urls_archived_in_last_days:
    now = datetime.now()
    skipinterval = timedelta(days=skip_urls_archived_in_last_days)
    def should_arch(url):
      archtime = last_archived_datetime(url)
      if not archtime:
        return True
      return now-archtime > skipinterval
  else:
    def should_arch(url):
      return True
  consecutive_failures = 0
  for url in tqdm(urls):
    if not should_arch(url):
      print(f"Skipping {url}...")
      continue
    if not save_url_to_archiveorg(url):
      consecutive_failures += 1
      wait_secs(60)
      if save_url_to_archiveorg(url):
        successes.append(url)
        consecutive_failures = 0
      else:
        consecutive_failures += 1
    else:
      successes.append(url)
      consecutive_failures = 0
    if consecutive_failures > 5:
      print("ERROR: This doesn't seem to be working...")
      quit(1)
    wait_secs(5)
  print(f"Saved {len(successes)} URLs:")
  for url in successes:
    print(f"  {url}")
  return successes
