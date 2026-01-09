#!/bin/python3

from urllib import parse as url
from collections import deque
import os
import json
import shutil
from strutils import (
   whitespace,
   trunc,
   floor,
   ceil,
   prompt,
   title_case,
   input_with_prefill,
   get_author_slug,
   HOSTNAME_BLACKLIST,
   italics,
   MONTHS,
   radio_dial,
   invert_inverted_index,
   system_open,
   print_work,
)
import gdrive_base
import gdrive
from itertools import chain
import journals
import publishers
try:
  import requests
  from yaspin import yaspin
  from slugify import slugify
except:
  print("pip install requests yaspin python-slugify")
  quit(1)

def serp_result(work: dict, margin=10) -> str:
  width = os.get_terminal_size().columns
  space = width - margin - 4
  return whitespace.sub(' ', f"{trunc(work['display_name'], floor(0.7*space))} by {trunc(work['hint'], ceil(0.3*space))}")

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

def make_library_entry_for_work(work, draft=False, course=None, glink='', pagecount=None) -> str:
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
    case 'proceedings-article' | 'journal-article' | 'article' | 'review' | 'preprint' | 'editorial':
        category = 'articles'
    case 'posted-content' | 'other':
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
  filename = input_with_prefill("Filename: ", filename)
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
  title = title.replace('"', '\\\"')
  with open(file_path, 'w') as fd:
    fd.write(f"""---
title: "{title}"
authors:
""")
    for i in range(min(4, len(work['authorships']))):
        author = work['authorships'][i]['author']['display_name'].replace('‐', '-')
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
        fd.write(f"  - \"{work['authorships'][4]['author']['display_name'].replace('‐', '-')}")
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
    if alternate_url and not oa_url:
        oa_url = alternate_url
        alternate_url = None
    if oa_url and oa_url.startswith("http:"):
          if "download" in oa_url or "pdf" in oa_url or "viewcontent.cgi" in oa_url:
            oa_url = "https:" + oa_url[5:]
    if not oa_url:
      oa_url = doi
    status = 404
    try:
      test = requests.head(oa_url or "https://www.google.com/404")
      status = test.status_code
    except requests.exceptions.ConnectionError:
      status = 404
    except requests.exceptions.SSLError:
      oa_url = oa_url.replace("/download/", "/view/").replace("https:", "http:")
    if doi == oa_url or status in [404]:
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
    fd.write(f"\"\ndrive_links:\n  - \"{glink}\"\n")
    if course != '':
      fd.write("course: ")
      if course:
        fd.write(slugify(course))
      fd.write("\nstatus: featured\n")
    fd.write(f"tags:\n  - \nyear: {work['publication_year']}\n")
    fd.write(f"month: {MONTHS[int(work['publication_date'][5:7])-1]}\n")
    try:
      venue = title_case(work['primary_location']['source']['display_name'].replace('"', "\\\""))
    except (TypeError, KeyError, AttributeError):
      venue = ""
    journal = ""
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
    publisherid = None
    if work['primary_location']['source'] and work['primary_location']['source']['host_organization_name'] and (journal == '' or '"' in journal):
      publisherid = work['primary_location']['source']['host_organization'].split("openalex.org/")[1]
      if publisherid in publishers.slugs:
        fd.write(f"publisher: {publishers.slugs[publisherid]}\n")
      else:
        fd.write(f"publisher: \"{title_case(work['primary_location']['source']['host_organization_name'])}\"\n")
    elif category in ('monographs', 'excerpts', 'papers'):
        fd.write("publisher: \"\"\n")
    if publisherid == publishers.SPRINGER_NATURE: # Nature and SBM have different addresses, but for simplicity we combine both imprints into a single publisher
       fd.write("address: \"Netherlands\"\n")
    elif category in ('monographs', 'excerpts'):
        fd.write("address: \"\"\n")
    if work['biblio']['volume']:
        fd.write(f"volume: {work['biblio']['volume']}\n")
    if work['biblio']['issue']:
        if publisherid == publishers.MDPI:
          assert int(work['biblio']['first_page']) == int(work['biblio']['last_page']), f"I expected MDPI article {work['id']} to have first and last page == article number"
          fd.write(f"number: {int(work['biblio']['first_page'])}\n")
        else:
          fd.write(f"number: {work['biblio']['issue']}\n")
    try:
        if publisherid == publishers.MDPI:
           raise ValueError("MDPI publishes each article individually")
        fd.write(f"pages: \"{int(work['biblio']['first_page'])}--{int(work['biblio']['last_page'])}\"\n")
    except (TypeError, KeyError, ValueError):
      if pagecount:
        fd.write(f"pages: {pagecount}\n")
      else:
        if category in ('monographs', 'booklets', 'essays', 'reference') or publisherid == publishers.MDPI:
            fd.write("pages: \n")
        elif category in ('articles', 'papers', 'excerpts'):
            fd.write("pages: \"--\"\n")
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
  query = input_with_prefill("Search> ", query)
  if not query:
    return (None, query)
  existing_drafts = None
  with yaspin(text="Scanning drafts..."):
    existing_drafts = draft_files_matching(query)
  if existing_drafts:
    use_draft = None
    if len(existing_drafts) > 1:
      print(f"Found {len(existing_drafts)} existing _draft files. Should we use one of those?")
      i = radio_dial([os.path.basename(fd) for fd in existing_drafts]+["None of the above"])
      if i < len(existing_drafts):
        use_draft = existing_drafts[i]
    else:
      print(f"Found matching _draft file: {existing_drafts[0]}")
      if prompt("Use this file?"):
        use_draft = existing_drafts[0]
    if use_draft:
        new_path = os.path.join(os.path.join(os.path.dirname(existing_drafts[0]), "../../_content/articles/"), os.path.basename(use_draft))
        shutil.move(use_draft, new_path)
        system_open(new_path)
        return (None, query)
  r = {}
  with yaspin(text="Searching OpenAlex..."):
    r = search_openalex_for_works(query)
  if 'results' not in r or len(r['results']) == 0:
    print("No results found :(")
    if prompt("Try again?"):
      return prompt_for_work(query)
    else:
      return (None, query)
  while True:
    print("Results:")
    i = radio_dial([serp_result(res) for res in r['results']] + ['Try a new search?', 'Give up?'])
    if i==len(r['results']):
      return prompt_for_work(query)
    if i-1==len(r['results']):
      return (None, query)
    workid = r['results'][i]['id'].split("/")[-1]
    with yaspin(text="Fetching work info..."):
      work = fetch_work_data(workid)
    print_work(work)
    if prompt("Is this the correct work?"):
      return (work, query)

def _main():
  query = ""
  print("Type part of the name of the work, hit Enter to search, arrows to scroll through the results, and hit Enter when you've selected the right one.\n")
  work, query = prompt_for_work(query)
  if not work:
    quit(0)
  title = whitespace.sub(' ', work['title']).split(':')[0].replace('\'', '\\\'')
  gfiles = gdrive.gcache.search_by_name_containing(
      title,
      additional_filters="mime_type = ? AND owner_id = 1",
      additional_params=('application/pdf',)
  )
  gfile = None
  if len(gfiles) == 0:
    gfiles = gdrive.gcache.search_by_name_containing(
       query,
       additional_filters="mime_type = ? AND owner_id = 1",
       additional_params=('application/pdf',)
    )
    if len(gfiles) == 0:
      print("No suitable files found.")
  for gfile in gfiles:
    parentid = gfile['parents'][0]
    gfile['course'] = gdrive.get_course_for_folder(parentid)
  if len(gfiles) == 1:
    gfile = gfiles[0]
    print(f"Got \"{gfile['name']}\"")
  if len(gfiles) > 1:
    print(f"Got {len(gfiles)} candidates.\nPlease select one:")
    i = radio_dial([f"{f['name']} in {f['course']}" for f in gfiles]+["Other (I'll supply a URL manually)"])
    if i < len(gfiles):
      gfile = gfiles[i]
  if gfile:
    glink = gdrive_base.DRIVE_LINK.format(gfile['id'])
  else:
    glink = input("Google Drive Link: ")
    gfile = gdrive.gcache.get_item(gdrive_base.link_to_id(glink))
    parentid = gfile['parents'][0]
    gfile['course'] = gdrive.get_course_for_folder(parentid)
  course = gdrive.input_course_string_with_tab_complete(prefill=gfile['course'])
  folders = gdrive.get_gfolders_for_course(course)
  gdrive.move_gfile(glink, folders)
  filepath = make_library_entry_for_work(work, course=course, glink=glink)
  print(f"\nOpening {filepath}\n")
  system_open(filepath)

if __name__ == "__main__":
  _main()

