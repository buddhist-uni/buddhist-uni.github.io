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

from openaleximporter import make_library_entry_for_work, alt_url_for_work, OPENALEX_CREDS
import openalextopics as topics
import journals

NOT_IN_TRACKING_JOURNALS = ",".join(f"locations.source.id:!{loc}" for loc in journals.slugs.keys())

# https://docs.openalex.org/
#APIURL = "https://api.openalex.org/works?filter=is_oa:true,is_paratext:false,type:!book,type:!monograph,locations.source.id:S47477353,cited_by_count:%3E2&per_page=50&page=7&sort=cited_by_count:desc"
APIURL=f"https://api.openalex.org/works?{OPENALEX_CREDS}filter=is_oa:true,language:en,is_paratext:false,type:!book,type:!review,type:!dataset,"+NOT_IN_TRACKING_JOURNALS+f",keywords.id:buddhism,cited_by_count:%3E10&per_page=100&page=8&sort=cited_by_count:desc"
#APIURL="https://api.openalex.org/works?filter=title.search:Gatsby,is_oa:true,is_paratext:false&sort=cited_by_count:desc"
#APIURL = "https://api.openalex.org/works?filter=cites:W1599632106,is_oa:true"

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"}

FNAME_MAXLEN = 192 # 126 might be safer

import requests
import os
import json
from urllib.parse import urljoin
import re
from time import sleep
from strutils import *
try:
  from yaspin import yaspin
  from tqdm import tqdm
  from pathvalidate import sanitize_filename
  from bs4 import BeautifulSoup
except:
  print("Install the dependancies first by running:")
  print("  pip install pathvalidate yaspin tqdm beautifulsoup4")
  exit(1)

import gdrive

METADATA_DIR = os.path.expanduser(os.path.normpath("~/.local/share/openalexdownloader"))
PLACE_FILE = os.path.join(METADATA_DIR, "place.json")
SEEN_FILE = os.path.join(METADATA_DIR, "works_seen.txt")

titlefilter = re.compile(r'(<[^<]+?>)|(\[[^\[]+?\])|["""„«»›‹'']')

PDF_LINKS = {
  "https://doi.org/10.18874/jjrs.": ("/pdf/download", lambda s, o: s),
  "https://doi.org/10.1080/14639947.": ("/doi/epdf/", lambda i, o: "https://www.tandfonline.com"+i.replace("epdf","pdf").replace('needAccess=true&role=button','download=true')),  
  "https://www.ncbi.nlm.nih.gov/pmc/articles": ("pdf/nih", lambda s, o: f"{o}/{s}"),
  "https://www.zygonjournal.org/": ("/download/", lambda s, o: s),
  "https://heiup.uni-heidelberg.de/journals": ("/article/view/", lambda s, o: s.replace('view', 'download')),
  "https://doi.org/10.11195/": ("/_pdf", lambda s, o: s),
  "http://www.dspace.cam.ac.uk/handle/": ("/download", lambda s, o: f"https://www.repository.cam.ac.uk{s}"),
  "https://journals.openedition.org/": ("/pdf/", lambda s, o: urljoin(o, s)),
  "https://shs.hal.science/": ("/document", lambda s, o: s),
  "https://doi.org/10.5281/zenodo.": (".pdf?download", lambda s, o: f"https://zenodo.org{s}"),
  "https://zenodo.org/record": (".pdf?download", lambda s, o: urljoin(o, s)),
  "https://doi.org/10.14288/": ("download/pdf", lambda s, o: urljoin(o, s)),
  "https://doaj.org/article/": ("pdf", lambda s, o: s),
}

def assert_cd_is_writable():
  try:
    filename = f"{random_letters(10)}.txt"
    with open(filename, "w") as fd:
      fd.write("test")
    os.remove(filename)
  except:
    print(f"Failed to write and rm {filename}")
    print("Make sure that you have write permissions to this directory!")
    quit(1)

def download(url: str, filename: str, expected_type=None) -> bool:
  if not expected_type:
    expected_type = filename.split(".")[-1]
  if os.path.exists(filename):
    if not prompt(f"  \"{filename}\" exists! Overwrite?", "n"):
      return False
  
  link_pattern = None
  for k, v in PDF_LINKS.items():
    if url.startswith(k) and not url.endswith(".pdf"):
      link_pattern = v
      break
  if link_pattern:
      nurl = None
      with yaspin(text="Parsing html..."):
          r = requests.get(url, headers=REQUEST_HEADERS, timeout=20)
          parser = BeautifulSoup(r.text, "lxml")
          for a in parser.find_all('a'):
            l = a.get("href")
            if not l:
              continue
            if link_pattern[0] in l:
                nurl = link_pattern[1](l, url)
                break
      if nurl:
        print(f"  Trying again with custom redirect \"{nurl}\"...")
        return download(nurl, filename, expected_type)
      else:
        print(f"  Failed to parse webpage!")
        Path("page.html").write_text(r.text)
        print("  Look in page.html to debug")
  
  is_doi = url.split("/")[2] == "doi.org"
  try:
   with yaspin(text="Connecting...").dots2:
    r = requests.get(url, stream=True, headers=REQUEST_HEADERS, timeout=(5 if is_doi else 15))
  except requests.exceptions.SSLError:
    print("  ERROR: SSL Connection Failed!")
    print(f"  URL: {url}")
    print(f"  Filename: {filename}")
    return False
  except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
    if is_doi:
      print("  TIMED OUT. Not trying again.")
      print(f"  URL: {url}")
      print(f"  Filename: {filename}")
      return False
    print("  TIMEOUT ERROR! Trying again...")
    with yaspin(text="Waiting 15 seconds first...", timer=True).clock:
      sleep(15)
    try:
     with yaspin(text="Trying again...").dots9:
      r = requests.get(url, stream=True, headers=REQUEST_HEADERS, timeout=20)
    except:
      print("  ERROR: Couldn't connect :(")
      print(f"  URL: {url}")
      print(f"  Filename: {filename}")
      return False
  type = r.headers['Content-Type']
  disposition = ""
  try:
    disposition = r.headers['Content-Disposition']
  except:
    pass
  try:
    firstchunk = next(r.iter_content(chunk_size=128))
  except StopIteration:
    firstchunk = b""
  bad_pdf = (expected_type == "pdf" and not firstchunk.startswith(b"%PDF-"))
  if bad_pdf or (expected_type != "pdf" and expected_type not in (type+disposition)):
    print(f"  ERROR: expected {expected_type} but got {type}")
    print(f"  Full header: {r.headers}")
    try:
      print(f"  UTF-8 Response: {''.join(firstchunk.decode('utf-8').splitlines())}…")
    except UnicodeDecodeError:
      print(f"  Binary Response: {firstchunk}…")
    r.close()
    print(f"  Filename: {filename}")
    print(f"  URL: {url}")
    return False
  print(f"Downloading to {filename}...")
  try:
    size = int(r.headers['Content-Length'])
  except:
    size = 0
  progress = tqdm(unit="B", unit_scale=True, unit_divisor=1024, total=size, miniters=1)
  try:
   with open(filename, 'wb') as fd:
    fd.write(firstchunk)
    progress.update(len(firstchunk))
    # Bayesian prior of 128kiB/s
    hypothetical_speed = 131072.0
    try:
     while True:
      # estimate how many Bytes we can get in an update interval
      chunk_size = round(progress.mininterval*0.5*((progress.n+hypothetical_speed)/(1.0+progress._time()-progress.start_t)))
      # ask the request for that many bytes
      chunk = next(r.iter_content(chunk_size=chunk_size))
      fd.write(chunk)
      progress.update(len(chunk))
    except StopIteration:
      pass # this is the normal way for a generator to stop looping
    if progress.n == len(firstchunk): # if streaming didn't work, try downloading in one go instead
      progress.close()
      print("Got no new data, trying again...")
      fd.seek(0)
      with yaspin(text=f"Downloading...").bouncingBall as spinner:
        r.close()
        # some servers dislike streaming/sniffing and prefer you dl in one go
        r = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
        fd.write(r.content)
        spinner.text = "Got it!"
        spinner.ok("( ^.^  )")
      print(f"{len(r.content)} bytes this time")
      return True
  except Exception as e:
    os.remove(filename)
    raise e
  del progress
  return True


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
    suffix = f" - {authorstr(work, 2)}.pdf"
    title = trunc(title_case(work['title']), FNAME_MAXLEN - len(suffix))
    filename = sanitize_filename(whitespace.sub(' ', titlefilter.sub('', f"{title}{suffix}")), replacement_text="_")
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
    if work in works_seen or len(gdrive.gcache.search_by_name_containing(title[0:-2])) > 0:
      print(f"\n{index+1}/{total} - {trunc(filename, 20)} already seen before...")
      if work not in works_seen:
        works_seen.add(work)
      continue
    if os.path.exists(filename):
      print(f"\n{index+1}/{total} - {trunc(filename, 20)} already downloaded...")
      works_seen.add(work)
      continue
    print(f"\n{index+1}/{total} - {work['type']} - {work['id'].split('/')[-1]}")
    print_work(work, indent=2)
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
