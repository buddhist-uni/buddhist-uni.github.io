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
from typing import TypedDict
from strutils import sanitize_string, git_root_folder
try:
  from tqdm import tqdm, trange
except:
  print("  pip install tqdm")
  exit(1)
ARCHIVE_ORG_AUTH_FILE = '~/archive.org.auth'

CANONICAL_URLS_PATH = git_root_folder.joinpath("_data", "canonical_urls.json")

ARCHIVE_ORG_AUTH_PATH = Path(os.path.expanduser(ARCHIVE_ORG_AUTH_FILE))
if ARCHIVE_ORG_AUTH_PATH.exists():
  ARCHIVE_ORG_AUTH = ARCHIVE_ORG_AUTH_PATH.read_text().strip()
else:
  raise RuntimeError(f"Please make a new {ARCHIVE_ORG_AUTH_FILE} text file and put in it the information from https://archive.org/account/s3.php in the following format: \"LOW <accesskey>:<secretkey>\"")

ARCHIVEID_BLACKLIST = {
  "unehistoiredetou0000na",
  "delinegaliteparm0000prof",
  "isbn_9782228906555",
  "discoveringroyal0000drew",
  "regulusvelpueris0000sain",
  "einekurzegeschic0000yuva",
  "unabrevehistoria0000bill",
  "xiaowangzilittle0000fash_o5z8",
  "xiaowangzilittle0000sain_b1x8",
  "xiaowangzilittle0000sain",
  "xiaowangzilittle0000sain_t5z5",
  "lederniervoldupe0000vill",
  "earlyidentityexperiencecontitutionofbeingaccordingtoearlybuddhismsuehamiltonseeotherbooks_648_V",
  "elartedelasabidu0000dala"
}

retry_strategy = Retry(total=2, backoff_factor=0.5)
http_adapter = HTTPAdapter(max_retries=retry_strategy)
archive_org_session = requests.Session()
archive_org_session.mount("https://", http_adapter)
archive_org_session.timeout = 5
archive_org_session.headers['Authorization'] = ARCHIVE_ORG_AUTH
archive_org_session.headers['Accept'] = 'application/json'

def wait_secs(n):
    print(f"Waiting {n} seconds...")
    for i in trange(n):
      time.sleep(1)

def last_archived_datetime(url):
  resp = archive_org_session.head("https://web.archive.org/web/"+str(url))
  if not resp.ok:
    return None
  if not 'x-archive-redirect-reason' in resp.headers:
    return None
  timestamp = resp.headers['x-archive-redirect-reason'].split(' at ')[1]
  return datetime.strptime(timestamp, '%Y%m%d%H%M%S')

def extract_archiveorg_id(item):
  """
    Extracts the Archive.org ID from the given URL.

    Args:
      item (str): The URL to extract the Archive.org ID from.

    Returns:
      str or None: The extracted Archive.org ID if found, None otherwise.
  """
  match = re.search(r'https?:\/\/archive.org\/details\/([\.a-zA-Z0-9_-]+)\/?', item)
  if match:
    return match.groups()[0]
  return None

def search_archiveorg_lending_library(query):
  return archive_org_session.get("https://archive.org/advancedsearch.php", params={
      "q": f"(collection:JaiGyan OR collection:inlibrary) AND language:(san OR eng) AND {query}",
      "sort": "lending___available_to_borrow desc, loans__status__max_lendable_copies desc, lending___max_lendable_copies desc",
      "rows": 12,
      "output": "json"
    }).json()['response']

def is_doc_sane_for_work(doc, workinfo):
  if doc['identifier'] in ARCHIVEID_BLACKLIST:
    return False
  if 'imagecount' in doc and doc['imagecount'] < workinfo['pages']:
    return False
  if 'year' in doc and doc['year'] < workinfo['year']:
    return False
  return True

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
    author = ""
    try:
      author = " ".join(filter(lambda w: len(w)>2, self.info['authors'][0].split("-")[0].split(" ")))
    except KeyError:
      pass
    if author == 'tnh':
      author = "Thich Nhat Hanh"
    sst = f"title:({title})"
    if author:
      sst += f" AND {author}"
    print(f"Searching works matching \"{sst}\" instead...")
    return search_archiveorg_lending_library(sst)

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
    print(f"Going with \"{doc['title']}\" by \"{doc.get('creator', 'None')}\" ({doc.get('year') or doc.get('publicdate')[:4]})")
    return f"https://archive.org/details/{doc['identifier']}/mode/1up"
  print("Unable to find a suitable copy :(")
  return None

def is_archiveorg_item_lendable(itemid):
  if itemid in ARCHIVEID_BLACKLIST:
    return False
  # Old API.  Seems deprecated?  Keeping the code around just in case:
  # resp = archive_org_session.get("https://archive.org/services/availability", params={"identifier": itemid})
  # data = resp.json()
  # if not resp.ok or not data["success"]:
  #   raise RuntimeError("Failed to connect to the Archive.org availability API")
  # try:
  #   return data['responses'][itemid]['is_lendable'] or data['responses'][itemid]['status'] == 'open'
  # except KeyError:
  #   message = data['responses'][itemid]['error_message']
  #   if message == 'not found':
  #     return False
  #   raise KeyError(f"Archive.org Availability API returned: \"{message}\"")

  # New metadata API
  resp = archive_org_session.get(f"https://archive.org/metadata/{itemid}")
  if not resp.ok:
    raise RuntimeError("Failed to connect to the Archive.org metadata API")
  data = resp.json()
  # No data is returned for bad IDs
  if not data:
    return False
  metadata = data['metadata']
  assert metadata['identifier'] == itemid, f"Got {metadata['identifier']} for {itemid} ?"
  assert metadata['mediatype'] == 'texts', f"Why are you searching for non-text {itemid} ?"
  # Without access restriction this is a completely free / open access work
  if 'access-restricted-item' not in metadata or not metadata['access-restricted-item'] or metadata['access-restricted-item'] == 'false':
    return True
  assert metadata['access-restricted-item'] in ['true', True], f"Access restriction is {metadata['access-restricted-item']} for {itemid}"
  # If it's in the borrowable collection, it's available for lending
  if 'inlibrary' in metadata['collection']:
    return True
  return False


def openlibrary_edition_to_work_id(editionid, retrycount=3):
  try:
    resp = requests.get(f"https://openlibrary.org/books/{editionid}.json")
    data = resp.json()
  except json.decoder.JSONDecodeError:
    print(f"!! WARNING: Failed to get Work ID for {editionid} with message: \"{resp.text}\"!!!")
    if "Service Unavailable" in resp.text and retrycount > 0:
      wait_secs(60)
      return openlibrary_edition_to_work_id(editionid, retrycount-1)
    return None
  try:
    return data['works'][0]['key'].replace("/works/", "")
  except:
    print(f"!! WARNING: Edition {editionid} has no Work ID!")
    return None

def save_url_to_archiveorg(url):
  print(f"Saving {url} to the Wayback Machine now...")
  try:
    resp = archive_org_session.post("https://web.archive.org/save", data={"url": url})
  except:
    print("WARNING: A connection error occurred")
    return False
  if resp.ok and json.loads(resp.text):
    print("Save job submitted!")
    return json.loads(resp.text).get("job_id")
  else:
    print(f"WARNING: Save failed\n\t{resp.headers}\n\tCONTENT:\n\t{resp.text}")
    return False

def archivejob_status(job_id):
  """
  Returns the status of a Wayback Machine save job. (False on error)
  """
  try:
    resp = archive_org_session.get(f"https://web.archive.org/save/status/{job_id}")
  except:
    print("WARNING: A connection error occurred")
    return False
  if resp.ok:
    # ['status'] == 'success' -> ['original_url'] will have the resolved url
    # This url may be different than the url that was submitted even if
    # ['http_status'] == 200
    return json.loads(resp.text)
  else:
    print(f"WARNING: Check failed\n\t{resp.headers}\n\tCONTENT:\n\t{resp.text}")
    return False

class ArchivedURL(TypedDict):
  original_url: str
  archival_url: str
  job_id: str
  status: int

def archive_urls(urls, skip_urls_archived_in_last_days=365) -> list[ArchivedURL]:
  canonical_urls = json.loads(CANONICAL_URLS_PATH.read_text())
  pending_jobs = []
  def wait_secs(n):
    print(f"Waiting {n} seconds...")
    for i in trange(n):
      time.sleep(1)
  if skip_urls_archived_in_last_days:
    now = datetime.now()
    skipinterval = timedelta(days=skip_urls_archived_in_last_days)
    def should_arch(url):
      if url in canonical_urls:
        url = canonical_urls[url]
      archtime = last_archived_datetime(url)
      if not archtime:
        return True
      return now-archtime > skipinterval
  else:
    def should_arch(url):
      return True
  consecutive_failures = 0
  for url in tqdm(urls):
    if "archive.org/" in url or not should_arch(url):
      print(f"Skipping {url}...")
      continue
    job_id = None
    retries = 3
    while not job_id and retries > 0:
      job_id = save_url_to_archiveorg(url)
      if not job_id:
        wait_secs(60)
        retries -= 1
    if not job_id:
      print("ERROR: Too many consecutive failures. Skipping the rest...")
      break
    pending_jobs.append({
      "original_url": url,
      "job_id": job_id,
    })
    wait_secs(5)
  print(f"Submitted {len(pending_jobs)} URLs!")
  print("Confirming their status...")
  successes = []
  loopcount = 0
  while len(pending_jobs) > 0 and loopcount < 60:
    time.sleep(5)
    next_pending = []
    for job in pending_jobs:
      status = archivejob_status(job["job_id"])
      if status and status["status"] == "success":
        job["status"] = int(status["http_status"])
        job["archival_url"] = status["original_url"]
        if job['status'] == 200 and job['original_url'] != job['archival_url']:
          canonical_urls[job["original_url"]] = status["original_url"]
          print(f"  OK: {job['original_url']} -> {job['archival_url']}")
        elif job['status'] == 200:
          print(f"  OK: {job['original_url']}")
        else:
          print(f"  WARNING: Got a {job['status']} for {job['original_url']}")
        successes.append(job)
      elif (not status) or status["status"] == "pending":
        next_pending.append(job)
      else:
        print(f"\n  ERROR: {job['original_url']}")
        print(f"    {status}\n")
    pending_jobs = next_pending
    loopcount += 1
  if loopcount >= 60:
    print(f"WARNING: Never got back info about {len(pending_jobs)} submitted jobs:")
    print(pending_jobs)
  CANONICAL_URLS_PATH.write_text(json.dumps(canonical_urls, sort_keys=True, indent=1))
  return successes
