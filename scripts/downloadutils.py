#!/bin/python3

import requests
import re
from pathlib import Path
import os
from time import sleep
from urllib.parse import urljoin

from strutils import (
  prompt,
  random_letters,
  authorstr,
  trunc,
  title_case,
  whitespace,
  DummyYaspin,
)
try:
  from yaspin import yaspin
  from tqdm import tqdm
  from pathvalidate import sanitize_filename
  from bs4 import BeautifulSoup
except:
  print("Install the dependancies first by running:")
  print("  pip install pathvalidate yaspin tqdm beautifulsoup4")
  exit(1)

HOSTNAME_BLACKLIST = {
  "www.questia.com",
  "scholarbank.nus.edu.sg",
}
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"}
FNAME_MAXLEN = 192 # 126 might be safer
titlefilter = re.compile(r'(<[^<]+?>)|(\[[^\[]+?\])|["""„«»›‹'']')

# When you get a page starting with `key`, look for a link containing `value[0]` and process it with `value[1]`
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
  """Quits the program if the $CWD isn't writable"""
  try:
    filename = f"{random_letters(10)}.txt"
    with open(filename, "w") as fd:
      fd.write("test")
    os.remove(filename)
  except:
    print(f"Failed to write and rm {filename}")
    print("Make sure that you have write permissions to this directory!")
    quit(1)

def pdf_name_for_work(work: dict):
  suffix = f" - {authorstr(work)}.pdf"
  title = trunc(title_case(work['title']), FNAME_MAXLEN - len(suffix))
  return sanitize_filename(
    whitespace.sub(' ', # make sure only spaces
      # rm funny quotes and stuff
      titlefilter.sub('', f"{title}{suffix}")),
    # replace other special chars with _s
    replacement_text="_"
  )


def download(url: str, filename: str, expected_type=None, verbose=True) -> bool:
  if not expected_type:
    expected_type = filename.split(".")[-1]
  if os.path.exists(filename):
    if not verbose:
      return True
    if not prompt(f"  \"{filename}\" exists! Overwrite?", "n"):
      return False
  
  ys = yaspin if verbose else DummyYaspin

  link_pattern = None
  for k, v in PDF_LINKS.items():
    if url.startswith(k) and not url.endswith(".pdf"):
      link_pattern = v
      break
  if link_pattern:
      nurl = None
      with ys(text="Parsing html..."):
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
        if verbose:
          print(f"  Trying again with custom redirect \"{nurl}\"...")
        return download(nurl, filename, expected_type)
      elif verbose:
        print(f"  Failed to parse webpage!")
        Path("page.html").write_text(r.text)
        print("  Look in page.html to debug")
  
  is_doi = url.split("/")[2] == "doi.org"
  try:
   with ys(text="Connecting...").dots2:
    r = requests.get(url, stream=True, headers=REQUEST_HEADERS, timeout=(5 if is_doi else 15))
  except requests.exceptions.SSLError:
    print(f"SSL Connection to {url} failed (trying to get {filename})")
    return False
  except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
    if is_doi:
      print(f"Timed out trying to connect to {url} (for {filename})")
      return False
    if verbose:
      print("  TIMEOUT! Trying again...")
    with ys(text="Waiting 15 seconds first...", timer=True).clock:
      sleep(15)
    try:
     with ys(text="Trying again...").dots9:
      r = requests.get(url, stream=True, headers=REQUEST_HEADERS, timeout=20)
    except:
      print(f"Failed to connect to {url} (for {filename})")
      return False
  try:
    declared_type = r.headers['Content-Type']
  except KeyError:
    declared_type = ''
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
  if bad_pdf or (expected_type != "pdf" and expected_type not in (declared_type+disposition)):
    if verbose:
      print(f"  ERROR: expected {expected_type} but got {declared_type}")
      print(f"  Full header: {r.headers}")
      try:
        print(f"  UTF-8 Response: {''.join(firstchunk.decode('utf-8').splitlines())}…")
      except UnicodeDecodeError:
        print(f"  Binary Response: {firstchunk}…")
      r.close()
      print(f"  Filename: {filename}")
      print(f"  URL: {url}")
    else:
      print(f"Got the wrong type {declared_type} from {url} (was expecting {expected_type} for {filename})")
    return False
  if verbose:
    print(f"Downloading to {filename}...")
  try:
    size = int(r.headers['Content-Length'])
  except:
    size = 0
  # TODO: should this also be gated on `verbose`?
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
      if verbose:
        print("Got no new data, trying again...")
      fd.seek(0)
      with ys(text=f"Downloading...").bouncingBall as spinner:
        r.close()
        # some servers dislike streaming/sniffing and prefer you dl in one go
        r = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
        if r.content.startswith(firstchunk):
          spinner.text = "Got it!"
          spinner.ok("( ^.^  )")
        else:
          spinner.text = "Got a different file the second time around"
          spinner.fail("( T.T )")
          if expected_type == 'pdf' and r.content.startswith(b"%PDF-"):
            spinner.text = "Got a different file, but it might still be ok..."
          else:
            if not verbose:
              print(f"Frustratingly, {url} gave us a different file the second time around! You'll have to download {filename} yourself.")
            return False
        fd.write(r.content)
      if verbose:
        print(f"{len(r.content)} bytes this time")
      return True
  except Exception as e:
    os.remove(filename)
    raise e
  # have to explicitly delete progress bar
  del progress
  return True
