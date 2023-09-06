#!/bin/python3

from urllib import parse as url
from collections import deque
import sys
import os
import tty
import termios
import json
import re
import shutil
from strutils import *
from itertools import chain
import journals
try:
  import requests
  from yaspin import yaspin
  from slugify import slugify
except:
  print("pip install requests yaspin python-slugify")
  quit(1)

OPENALEX_SEARCH_RESULT_COUNT = 10
def search_openalex_for_works(query):
  r = requests.get(f"https://api.openalex.org/autocomplete/works?q={url.quote(query, safe='')}")
  return json.loads(r.text)

def fetch_work_data(workid):
  r = requests.get(f"https://api.openalex.org/works/{workid}")
  return json.loads(r.text)

def alt_url_for_work(work, oa_url):
  ret = None
  if 'locations' in work:
    try:
      ret = next(filter(
          lambda url: url != work['doi'] and url != oa_url and url and (url.split("/")[2] not in HOSTNAME_BLACKLIST),
          chain(map(lambda v: v['pdf_url'], work['locations']), map(lambda v: v['landing_page_url'], work['locations']))
      ))
    except StopIteration:
      pass
  return ret

def make_library_entry_for_work(work, draft=False) -> str:
  category = 'articles'
  subcat = ''
  match work['type']:
    case 'book-section' | 'book-part':
        category = 'excerpts'
    case 'monograph' | 'book' | 'book-set' | 'book-series' | 'edited-book':
        category = 'monographs'
    case 'report' | 'book-chapter':
        category = 'papers'
    case 'reference-entry' | 'database' | 'dataset' | 'reference-book' | 'standard':
        category = 'reference'
    case 'proceedings-article' | 'journal-article' | 'article':
        category = 'articles'
    case 'posted-content':
        category = 'essays'
    case 'dissertation':
        category = 'booklets'
        subcat = 'thesis'
    case _:
        raise ValueError(f"Unexpected work type \"{work['type']}\" found")

  if draft:
    content_path = "_drafts/_content"
  else:
    content_path = f"_content/{category}"
  file_path = os.path.normpath(os.path.join(os.path.dirname(__file__), f"../{content_path}"))
  if not os.path.exists(file_path):
    if draft and prompt(f"{file_path} doesn't exist. Create it?"):
      os.makedirs(file_path)
    else:
      raise FileNotFoundError(f"{file_path} requested but doesn't exist")
  title = title_case(work['title'])
  title = whitespace.sub(' ', title)
  title = italics.sub('*', title)
  filename = slugify(
    title,
    max_length=40,
    word_boundary=True,
    save_order=True,
    stopwords=('a', 'an', 'the', 'is', 'are', 'by'),
    replacements=[('between','btw')],
  )
  try:
    author = work['authorships'][0]['author']['display_name']
    assert(work['authorships'][0]['author_position'] == 'first')
    aslug = get_author_slug(author)
    if aslug:
      author = aslug
    else:
      try:
        pivot = author.rindex(' ')
        author = f"{author[1+pivot:]} {author[:pivot]}"
      except ValueError:
        pass
    if len(work['authorships']) > 1:
        author += " et al"
    filename += f"_{slugify(author)}"
  except (KeyError, IndexError):
    pass
  filename += '.md'
  file_path = os.path.join(file_path, filename)
  with open(file_path, 'w') as fd:
    fd.write('---\n')
    fd.write(f"title: >-\n    {title}\n")
    fd.write("authors:\n")
    for i in range(min(4, len(work['authorships']))):
        author = work['authorships'][i]['author']['display_name']
        aslug = get_author_slug(author)
        if aslug:
            author = aslug
        else:
            author = f"\"{author}\""
        fd.write(f"  - {author}\n")
    aslug = get_author_slug(work['authorships'][-1]['author']['display_name'])
    if len(work['authorships']) == 5 and aslug:
        fd.write(f"  - {aslug}")
    elif len(work['authorships']) >= 5:
        fd.write(f"  - \"{work['authorships'][4]['author']['display_name']}")
        if len(work['authorships']) > 5:
          fd.write(" and others")
        fd.write("\"\n")
    if subcat != '':
        fd.write(f"subcat: {subcat}\n")
    if category in ('papers', 'excerpts', 'monographs'):
        fd.write("editor: \n")
    fd.write("external_url: \"")
    oa_url = work['open_access']['oa_url']
    if oa_url and oa_url.split("/")[2] in HOSTNAME_BLACKLIST:
      oa_url = None
    doi = work["doi"]
    alternate_url = alt_url_for_work(work, oa_url)
    if doi == oa_url:
      if alternate_url:
        oa_url = alternate_url
        alternate_url = None
      else:
        doi = None
    if oa_url:
        fd.write(oa_url)
        if doi or alternate_url:
            fd.write("\"\nsource_url: \"")
    if doi:
        fd.write(doi)
        if not oa_url and alternate_url:
            fd.write("\"\nsource_url: \"")
    if alternate_url and not (doi and oa_url):
        fd.write(alternate_url)
    fd.write("\"\ndrive_links:\n  - \"\"\nstatus: featured\ncourse: \ntags:\n  - \n")
    fd.write(f"year: {work['publication_year']}\n")
    fd.write(f"month: {MONTHS[int(work['publication_date'][5:7])-1]}\n")
    try:
      venue = title_case(work['primary_location']['source']['display_name'].replace('"', "\\\""))
    except (TypeError, KeyError, AttributeError):
      venue = ""
    if category == 'monographs':
        fd.write("olid: \n")
    elif category in ('excerpts', 'papers'):
        fd.write(f"booktitle: \"{venue}\"\n")
    elif category == 'articles':
        try:
          journal = work['primary_location']['source']['id']
        except (TypeError, KeyError, AttributeError):
          journal = ""
        if journal:
          journal = journal.split('/')[-1]
        if journal and journal in journals.slugs:
          journal = journals.slugs[journal]
        else:
          journal = f"\"{venue}\""
        fd.write(f"journal: {journal}\n")
        if not work['biblio']['volume'] and not work['biblio']['issue']:
            fd.write("volume: \nnumber: \n")
    if work['biblio']['volume']:
        fd.write(f"volume: {work['biblio']['volume']}\n")
    if work['biblio']['issue']:
        fd.write(f"number: {work['biblio']['issue']}\n")
    try:
        fd.write(f"pages: \"{int(work['biblio']['first_page'])}--{int(work['biblio']['last_page'])}\"\n")
    except (TypeError, KeyError, ValueError):
        if category in ('monographs', 'booklets', 'essays', 'reference'):
            fd.write("pages: \n")
        if category in ('articles', 'papers', 'excerpts'):
            fd.write("pages: \"--\"\n")
    if work['primary_location']['source'] and work['primary_location']['source']['host_organization_name']:
        fd.write(f"publisher: \"{title_case(work['primary_location']['source']['host_organization_name'])}\"\n")
    elif category in ('monographs', 'excerpts', 'papers'):
        fd.write("publisher: \"\"\n")
    if category in ('monographs', 'excerpts'):
        fd.write("address: \"\"\n")
    fd.write(f"openalexid: {work['id'].split('/')[-1]}\n---\n\n>")
    abstract = deque(invert_inverted_index(work['abstract_inverted_index']))
    line_len = 1
    while len(abstract) > 0:
        word = f" {abstract.popleft()}"
        fd.write(word)
        line_len += len(word)
        if word[-1] == '.' and line_len > 50 and len(abstract) >= 3:
            line_len = 1 + len(word)
            fd.write('\n>')
    fd.write('\n\n')
  return file_path

def draft_files_matching(query):
  matching_files = []
  query_slug = slugify(query)
  draft_folder_path = os.path.normpath(os.path.join(os.path.dirname(__file__), f"../_drafts/_content"))
  
  for root, dirs, files in os.walk(draft_folder_path):
    for file in files:
      file_path = os.path.join(root, file)
      
      # Check if the file name contains the query string in slugified form
      if query_slug in slugify(file):
        matching_files.append(file_path)
        continue
      
      # Check if the third ("title") line of the file contains the query string (ignoring capitalization)
      with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        if len(lines) >= 3 and query.lower() in lines[2].lower():
          matching_files.append(file_path)
  
  return matching_files

def prompt_for_work(query) -> str:
  print("Type part of the name of the work, hit Tab or Enter to search, arrows to scroll through the results, and hit Enter when you've selected the right one.\n")
  SEARCH_ROOM = 5
  stdout_make_room(SEARCH_ROOM)
  cout(f"Search> \033[s{query}")
  stdin = sys.stdin.fileno()
  old_settings = termios.tcgetattr(stdin)
  tty.setraw(stdin)
  r = {}
  i = 0
  try:
   while '\r' not in query:
    ch = sys.stdin.read(1)
    if ch in ['\t', '\r', '\x04'] and 'results' not in r:
       cout("\033[u\033[3E")
       with yaspin(text="Scanning drafts..."):
         existing_drafts = draft_files_matching(query)
       if existing_drafts:
        if len(existing_drafts) > 1:
            cout(f"Found {len(existing_drafts)} existing _draft files: ")
            cout(" AND ".join(existing_drafts))
            raise NotImplementedError("Multiple matching draft files found")
        else:
            cout(f"Found matching _draft file: {existing_drafts[0]}\033[u\033[3E")
            if prompt("Use this file?"):
                new_path = os.path.join(os.path.join(os.path.dirname(existing_drafts[0]), "../../_content/articles/"), os.path.basename(existing_drafts[0]))
                shutil.move(existing_drafts[0], new_path)
                system_open(new_path)
                quit(0)
       with yaspin(text="Searching OpenAlex..."):
         i = 0
         r = search_openalex_for_works(query)
    elif ch == '\x03':
      raise KeyboardInterrupt()
    elif ch in ['\r', '\x04']:
      break
    elif ch == '\t':
      continue
    elif ch == '\x1b': # ESC
      ch = sys.stdin.read(1)
      if ch == '[': # we're getting a control char (e.g. arrow keys)
        ch = sys.stdin.read(1)
        # A=up, B=down, C=right, D=left, H=home, F=end
        if ch == 'A' and i > 0:
          i -= 1
        if (ch == 'B') and ('results' in r) and (len(r['results']) > i + 1):
          i += 1
        # TODO: Handle left/right editing
    else:
      i = 0
      r = {}
      if ch == '\x7f': # BACKSPACE
        query = query[:-1]
      else:
        query += ch
    cout(f"\033[u\033[0J{query}\033[E")
    if 'results' in r and len(r['results']) > 0:
      cout(f"Results:\033[E")
      if i > 0:
        cout(f"\033[2m   {i}/{len(r['results'])}: {serp_result(r['results'][i-1])}\033[0m")
      cout(f"\033[E")
      cout(f" > {i+1}/{len(r['results'])}: {serp_result(r['results'][i])}")
      if len(r['results']) > i + 1:
        cout(f"\033[E")
        cout(f"\033[2m   {i+2}/{len(r['results'])}: {serp_result(r['results'][i+1])}\033[0m")
    else:
      cout(f"\033[2ENo results (hit tab/enter to search)")
    cout(f"\033[u\033[{len(query)}C")
  finally:
    cout(f"\033[u\033[{SEARCH_ROOM}E\n")
    termios.tcsetattr(stdin, termios.TCSADRAIN, old_settings)
  return (r['results'][i]['id'].split("/")[-1], query)

def _main():
  query = ""
  while True:
    workid, query = prompt_for_work(query)
    with yaspin():
      work = fetch_work_data(workid)
    print_work(work)
    if prompt("Is this the correct work?"):
      break
  filepath = make_library_entry_for_work(work)
  print(f"\nOpening {filepath}\n")
  system_open(filepath)

if __name__ == "__main__":
  _main()

