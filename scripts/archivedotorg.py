"""Saves every page across the site to Archive.org's Wayback Machine"""

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from pathlib import Path
import json
import re
import time
from datetime import datetime, timedelta
import os
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

def arch_url_to_id(item):
  match = re.search(r'https?:\/\/archive.org\/details\/([a-z0-9_-]+)\/?', item)
  if match:
    return match.groups()[0]
  return item

def find_lendable_archiveorg_url_for_metadata(workinfo):
  print(f"Searching Archive.org for lendable copies of \"{workinfo['title']}\"...")
  print(f"Finding work OLID for {workinfo['olid']}...")
  olid = openlibrary_edition_to_work_id(workinfo['olid'])
  print(f"Got {olid}")
  print(f"Searching by OLID:{olid}...")
  ser = requests.get("https://archive.org/advancedsearch.php", params={
      "q": f"collection:inlibrary AND language:eng AND openlibrary_work:({olid})",
      "sort": "lending___available_to_borrow desc, loans__status__max_lendable_copies desc, lending___max_lendable_copies desc",
      "rows": 12,
      "output": "json"
    }).json()
  # print(ser['responseHeader'])
  ser = ser['response']
  print(f"Found {ser['numFound']} lendable work(s)")
  for doc in ser['docs']:
    if doc['imagecount'] >= workinfo['pages']:
      print(f"Going with \"{doc['title']}\" by \"{doc['creator']}\" ({doc['year']})")
      return f"https://archive.org/details/{doc['identifier']}/mode/1up"
  print("Unable to find a suitable copy :(")
  return None

def is_archiveorg_item_lendable(itemid):
  itemid = arch_url_to_id(itemid)
  resp = archive_org_session.get("https://archive.org/services/availability", params={"identifier": itemid})
  data = resp.json()
  if not resp.ok or not data["success"]:
    raise RuntimeError("Failed to connect to the Archive.org availability API")
  try:
    return data['responses'][itemid]['is_lendable']
  except KeyError:
    raise KeyError(f"Archive.org Availability API returned: \"{data['responses'][itemid]['error_message']}\"")

def openlibrary_edition_to_work_id(editionid):
  data = requests.get(f"https://openlibrary.org/books/{editionid}.json").json()
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


