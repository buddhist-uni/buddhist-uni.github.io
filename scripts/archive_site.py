"""Saves every page across the site to Archive.org's Wayback Machine"""

import requests
from pathlib import Path
import json
import time
import os
import xml.etree.ElementTree as XML
try:
  import tqdm
except:
  print("  pip install tqdm")
  quit(1)

# Must be in the format "LOW {accesskey}:{secretkey}"
# Get your keys here: https://archive.org/account/s3.php
ARCHIVE_ORG_AUTH_FILE = Path(os.path.expanduser('~/archive.org.auth'))
ARCHIVE_ORG_AUTH = ARCHIVE_ORG_AUTH_FILE.read_text()

SITEMAP_NAMESPACE = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

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
    print(f"Found {togo} urls. Will take at least {(togo/600.0):.2f} hours")
    # Extract and yield the URLs
    for url_element in url_elements:
        loc_element = url_element.find("ns:loc", SITEMAP_NAMESPACE)
        if loc_element is not None:
            yield loc_element.text

def save_url_to_archiveorg(url):
  print(f"Saving {url} to the Wayback Machine now...")
  try:
    resp = requests.post("https://web.archive.org/save", data={"url": url}, headers={'Accept': 'application/json', 'Authorization': ARCHIVE_ORG_AUTH})
  except:
    print("WARNING: A connection error occurred")
    return False
  if resp.ok and json.loads(resp.text):
    print("Saved!")
    return True
  else:
    print(f"WARNING: Save failed\n\t{resp.headers}\n\tCONTENT:\n\t{resp.text}")
    return False

if __name__ == "__main__":
  from tqdm import tqdm, trange
  skip_past = "https://buddhistuniversity.net/authors/gross-rita"
  urls = list(all_urls_in_website("https://buddhistuniversity.net"))
  def wait_secs(n):
    print(f"Waiting {n} seconds...")
    for i in trange(n):
      time.sleep(1)
  try:
    skip_past = urls.index(skip_past)
    urls = urls[skip_past+1:]
  except:
    pass
  consecutive_failures = 0
  for url in tqdm(urls):
    if not save_url_to_archiveorg(url):
      consecutive_failures += 1
      wait_secs(60)
      if save_url_to_archiveorg(url):
        consecutive_failures = 0
      else:
        consecutive_failures += 1
    else:
      consecutive_failures = 0
    if consecutive_failures > 5:
      print("ERROR: This doesn't seem to be working...")
      quit(1)
    wait_secs(5)
