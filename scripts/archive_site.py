"""Saves every page across the site to Archive.org's Wayback Machine"""

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from pathlib import Path
import json
import time
from datetime import datetime, timedelta
import os
import xml.etree.ElementTree as XML
try:
  from tqdm import tqdm, trange
except:
  print("  pip install tqdm")
  quit(1)
ARCHIVE_ORG_AUTH_FILE = '~/archive.org.auth'

ARCHIVE_ORG_AUTH_PATH = Path(os.path.expanduser(ARCHIVE_ORG_AUTH_FILE))
if ARCHIVE_ORG_AUTH_PATH.exists():
  ARCHIVE_ORG_AUTH = ARCHIVE_ORG_AUTH_PATH.read_text()
else:
  print(f"Please make a new {ARCHIVE_ORG_AUTH_FILE} text file and put in it the information from https://archive.org/account/s3.php in the following format: \"LOW <accesskey>:<secretkey>\"")
  quit(1)

SITEMAP_NAMESPACE = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

retry_strategy = Retry(total=2, backoff_factor=0.5)
http_adapter = HTTPAdapter(max_retries=retry_strategy)
archive_org_session = requests.Session()
archive_org_session.mount("https://", http_adapter)
archive_org_session.timeout = 5
archive_org_session.headers['Authorization'] = ARCHIVE_ORG_AUTH
archive_org_session.headers['Accept'] = 'application/json'

def all_urls_in_website(domain):
    # Fetch the XML sitemap using requests
    response = requests.get(domain+"/sitemap.xml")
    if not response.ok:
      print(f"Couldn't load the sitemap for {domain}")
      return
    print(f"Got the sitemap for {domain} ({len(response.text)}bytes)")
    root = XML.fromstring(response.text)
    # Find all URL elements using XPath
    url_elements = root.findall(".//ns:url", SITEMAP_NAMESPACE)
    togo = len(url_elements)
    # Extract and yield the URLs
    for url_element in url_elements:
        loc_element = url_element.find("ns:loc", SITEMAP_NAMESPACE)
        if loc_element is not None:
            yield loc_element.text

def last_archived_datetime(url):
  resp = archive_org_session.head("https://web.archive.org/web/"+str(url))
  if not resp.ok:
    return None
  if not 'x-archive-redirect-reason' in resp.headers:
    return None
  timestamp = resp.headers['x-archive-redirect-reason'].split(' at ')[1]
  return datetime.strptime(timestamp, '%Y%m%d%H%M%S')

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

if __name__ == "__main__":
  skip_past = "Last successful URL"
  urls = list(all_urls_in_website("https://buddhistuniversity.net"))
  try:
    skip_past = urls.index(skip_past)
    urls = urls[skip_past+1:]
  except:
    pass
  archive_urls(urls)
