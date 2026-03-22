#!/bin/python3

from pathlib import Path
from argparse import ArgumentParser
from hashlib import md5
import json
import time
import csv
import sys
import requests
from urllib.parse import quote as urlquote

from strutils import (
  input_with_prefill,
  system_open,
  prompt,
  radio_dial,
)
from pdfutils import get_page_count
import gdrive_base
import gdrive

def parse_filename(name) -> tuple[str, str]:
  (title, author) = split_filename(name)
  if ' ' not in title:
    title = title.replace("_", " ")
    title = title.replace("-", " ")
  return (title, author)

def split_filename(name) -> tuple[str, str]:
  name = name.split('.')[0]
  parts = name.split(' - ')
  if len(parts) == 1:
    return (parts[0], '')
  return (parts[0].replace("_ ", ": "), parts[-1])

def get_opensyllabus_score(title: str, author: str, year):
  resp = requests.get(f"https://os-analytics-api-prod.opensyllabus.org/api/titles/?format=json&size=50&work_query={urlquote(title)}").json()
  if len(resp['works']) == 0 and ":" in title:
    resp = requests.get(f"https://os-analytics-api-prod.opensyllabus.org/api/titles/?format=json&size=50&work_query={urlquote(title.split(':')[0])}").json()
  if len(resp['works']) == 0:
    return 0
  if len(resp['works']) == 1:
    return resp['works'][0]['score']*100.0
  for work in resp['works']:
    for wauthor in work['authors']:
      if author in wauthor['display_name']:
        return work['score']*100.0
  for work in resp['works']:
    if work['year'] and abs(int(work['year']) - int(year)) <= 1:
      return work['score']*100.0
  print("Please select a work from OpenSyllabus:")
  index = radio_dial([f"{work['title']} ({work['year']}) by {work['authors'][0]['display_name']}" for work in resp['works']]+["None of the above"])
  if index == len(resp['works']):
    return 0
  return resp['works'][index]['score']*100.0

parser = ArgumentParser()
parser.add_argument('folder', type=Path)
parser.add_argument('output', type=Path, default=None, nargs='?')
parser.add_argument("--free", action="store_true", default=False)
args = parser.parse_args()

outrows = []
if args.output and args.output.exists():
  with args.output.open('r') as infp:
    reader = csv.reader(infp)
    for row in reader:
      outrows.append(row)
gfolders = json.loads(gdrive.FOLDERS_DATA_FILE.read_text())
tags = {gdrive_base.folderlink_to_id(folder): tag for tag, folders in gfolders.items() for folder in folders.values()}

for filep in args.folder.iterdir():
  if not filep.is_file():
    continue
  print(f"\n{filep.name}")
  already = False
  for i in range(len(outrows)):
    row = outrows[i]
    if row[-1] == filep.name:
      already = True
  if already:
    print(f"Skipping {filep.name}...")
    continue
  title, author = parse_filename(filep.name)
  system_open(filep)
  gfiles = gdrive.gcache.files_exactly_named(filep.name)
  free = ""
  if args.free:
    free = "1"
  elif "(oa)" in filep.name:
    free = "1"
  title = input_with_prefill("title: ", title)
  if not title:
    break
  author = input_with_prefill("author: ", author)
  if len(gfiles) != 1 or gfiles[0]['md5Checksum'] != md5(filep.read_bytes()).hexdigest():
    glink = input("Google File URL: ")
    gfile = gdrive.gcache.get_item(gdrive_base.link_to_id(glink))
  else:
    gfile = gfiles[0]
  pages = ''
  if filep.suffix.lower() == '.pdf':
    pages = get_page_count(filep)
  system_open(f"https://www.goodreads.com/search?q={urlquote(title)}")
  print("Opening Goodreads...")
  time.sleep(3)
  year = input("year: ")
  pages = input_with_prefill("pages: ", str(pages))
  rating = input("GR Avg Rating: ")
  ratings = input("GR Ratings Count: ")
  academic_score = get_opensyllabus_score(title, author, year)
  print(f"OpenSyllabus Score: {academic_score}")
  free = input_with_prefill("free: ", free)
  fun = input("fun: ")
  recs = input("recs: ")
  folderid = gfile['parents'][0]
  tag = 'unknown'
  try:
    while folderid not in tags:
      folderid = gdrive.gcache.get_item(folderid)['parents'][0]
    tag = tags[folderid]
  except:
    pass
  print(f"tag: {tag}")
  outrows.append([
    title,
    author,
    gdrive_base.DRIVE_LINK.format(gfile['id']),
    year,
    pages,
    recs,
    tag,
    free,
    fun,
    rating,
    ratings,
    academic_score,
    filep.name,
  ])
  if args.output:
    with args.output.open('w') as outfp:
      csv.writer(outfp, delimiter="\t").writerows(outrows)
  else:
    print('\t'.join([str(v) for v in outrows[-1]]), file=sys.stderr)

