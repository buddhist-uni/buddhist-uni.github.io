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

# Journals
# See e.g. https://api.openalex.org/venues/V120086578 for more info
BSR   = "V139284966"
JIABS = "V2764843907"
JGB   = "V2739015590"
IJDS  = "V2739402052"
HIJBS = "V4210175251"
JBE   = "V2764747367"
JJRS  = "V120086578"
JCB   = "V107624032"

import openalexconcepts as concepts

# https://docs.openalex.org/
APIURL=f"https://api.openalex.org/works?filter=is_oa:true,is_paratext:false,host_venue.id:!{BSR},host_venue.id:!{JIABS},host_venue.id:!{JGB},host_venue.id:!{JJRS},host_venue.id:!{IJDS},host_venue.id:!{JBE},host_venue.id:!{HIJBS},host_venue.id:!{JCB},concepts.id:{concepts.BUDDHISM}|{concepts.BUDDHA},cited_by_count:%3E0,publication_year:%3E1970,publication_year:%3C2021&sort=cited_by_count:desc&per_page=200&page=3"

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-A725F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Mobile Safari/537.36"}

METADATA_FILENAME = ".openalexdownloader.json"

FNAME_MAXLEN = 192 # 126 is safer

import requests
import random
import os
import json
import re
import string
from time import sleep
try:
  from yaspin import yaspin
  from tqdm import tqdm
  from pathvalidate import sanitize_filename
except:
  print("Install the dependancies first by running:")
  print("  pip install pathvalidate yaspin tqdm")
  exit(1)

titlefilter = re.compile('(<[^<]+?>)|(\[[^\[]+?\])|["”“„«»›‹‘’]')
whitespace = re.compile('\s+')

def trunc(longstr, maxlen=12) -> str:
  return longstr if len(longstr) <= maxlen else (longstr[:maxlen-1]+'…')

def random_letters(length):
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

def prompt(question: str, default = None) -> bool:
    reply = None
    hint = "(y/n)"
    if default == "y":
      hint = "[y]/n"
    if default == "n":
      hint = "y/[n]"
    while reply not in ("y", "n"):
        reply = input(f"{question} {hint}: ").casefold()
        if not reply:
          reply = default
    return (reply == "y")

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
  try:
   with yaspin(text="Connecting...").dots2:
    r = requests.get(url, stream=True, headers=REQUEST_HEADERS, timeout=15)
  except requests.exceptions.SSLError:
    print("  ERROR: SSL Connection Failed!")
    print(f"  URL: {url}")
    print(f"  Filename: {filename}")
    return False
  except requests.exceptions.ConnectionError:
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
  firstchunk = next(r.iter_content(chunk_size=128))
  if (expected_type == "pdf" and not firstchunk.startswith(b"%PDF-")) or (expected_type != "pdf" and expected_type not in (type+disposition)):
    print(f"  ERROR: expected {expected_type} but got {type}")
    print(f"  Full header: {r.headers}")
    print(f"  Response: {''.join(firstchunk.decode('utf-8').splitlines())}…")
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
      with yaspin(text=f"Downloading...").bouncingBall:
        r.close()
        # some servers dislike streaming/sniffing and prefer you dl in one go
        r = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
        fd.write(r.content)
      print(f"Got {len(r.content)} bytes this time")
      return True
  except Exception as e:
    os.remove(filename)
    raise e
  del progress
  return True

# Makes the authors string for the work
# https://docs.openalex.org/api-entities/works/work-object#authorships
def authorstr(work: dict, maxn: int) -> str:
    authors = list(map(lambda a: a['author']['display_name'].replace(',', ''), work['authorships']))
    if len(authors) > maxn:
      authors = authors[:(maxn-1)]
      authors.append('et al')
    return ", ".join(authors)

# Reconstructs an abstract from OA's
# inverted index:
# https://docs.openalex.org/api-entities/works/work-object#abstract_inverted_index
def abstract(index: dict) -> str:
  max_i = max(map(lambda ps: max(ps), index.values()))
  ret = [""]*(max_i+1)
  for k in index:
    word = whitespace.sub(' ', k.strip())
    for i in index[k]:
      ret[i] = word
  return " ".join(ret)

def print_work(work: dict, indent=0):
    s = "".join([" "]*indent)
    print(f"{s}Title: {work['title']}")
    print(f"{s}Author(s): {authorstr(work, 6)}")
    print(f"{s}Venue: {work['host_venue']['display_name']}")
    print(f"{s}Year: {work['publication_year']}")
    try:
      print(f"{s}Pages: {1+int(work['biblio']['last_page'])-int(work['biblio']['first_page'])}")
    except:
      print(f"{s}Pages: ??")
    print(f"{s}Cited By: {work['cited_by_count']}")
    if work['abstract_inverted_index']:
      print(f"{s}Abstract: {abstract(work['abstract_inverted_index'])}")
    print(f"{s}URL: {url}")

# The Main Script

if __name__ == "__main__":
  if not prompt(f"Will dump all files to \"{os.getcwd()}\" Is this okay?", "y"):
    quit(1)
  assert_cd_is_writable()
  if download(APIURL, "works.json") and os.path.exists(METADATA_FILENAME):
    os.remove(METADATA_FILENAME)
  with open("works.json") as fd:
    data = json.load(fd)
  try:
    total = len(data["results"])
  except KeyError:
    print("Error accessing the API:")
    print(json.dumps(data))
    os.remove("works.json")
    quit(1)
  metadata = {"i": 0}
  if os.path.exists(METADATA_FILENAME):
    if prompt("Pick up where you left off?", "y"):
     with open(METADATA_FILENAME) as fd:
      metadata = json.load(fd)
  for index in range(metadata["i"], total):
    metadata["i"] = index
    with open(METADATA_FILENAME, "w") as fd:
      json.dump(metadata, fd)
    work = data["results"][index]
    suffix = f" - {authorstr(work, 2)}.pdf"
    filename = sanitize_filename(whitespace.sub(' ', titlefilter.sub('', f"{trunc(work['title'].title(), FNAME_MAXLEN - len(suffix))}{suffix}")), replacement_text="_")
    url = work['open_access']['oa_url']
    if os.path.exists(filename):
      print(f"\n{index+1}/{total} - {trunc(filename, 20)} already downloaded...")
      continue
    print(f"\n{index+1}/{total} - {work['type']}")
    print_work(work, indent=2)
    if prompt(f"Download {index+1}?", "n"):
      if download(url, filename):
        print("Downloaded successfully!")
        sleep(0.5)
      else:
        input("Download failed. Press enter to continue...")
  print("Finished!")
  os.remove(METADATA_FILENAME)
  os.remove("works.json")
