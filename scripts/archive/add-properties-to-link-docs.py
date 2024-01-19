#!/bin/python3

from urllib.parse import urlparse, parse_qs

import gdrive

gfiles = gdrive.session().files()

query = "mimeType='application/vnd.google-apps.document' and trashed=false and 'me' in owners"
fields = "id,properties,name,size"

for file in gdrive.all_files_matching(query, fields):
  print(f"Analyzing '{file['name']}'...")
  if int(file.get('size') or 1) > 3000:
    print("  File too large to be a link file. Skipping")
    continue
  if file.get('properties',{}).get('url'):
    print("  Has the metadata already. Skipping")
    continue
  doc = gfiles.export(
      fileId=file['id'],
      mimeType='text/html',
    ).execute().decode('utf-8')
  soup = gdrive.BeautifulSoup(doc, features='html.parser')
  links, ps, h2s, h3s = [soup.find_all(foo) or [] for foo in ['a', 'p', 'h2', 'h3']]
  if len(links) != 1:
    # I don't want to handle multi-link docs
    # and no-link docs are other things
    print("  Doesn't appear to be a single-link doc")
    continue
  link = links[0].get('href')
  link = parse_qs(urlparse(link).query).get('q', [''])[0]
  if len(link) > 121:
    link = gdrive.requests.get('http://tinyurl.com/api-create.php?url='+link).text
  data = {'properties': {
    'createdBy': 'LibraryUtils.LinkSaver',
    'url': link,
  }}
  # if new-style doc, just add properties metadata
  if len(ps) == len(h2s) and len(h2s) == 1 and len(h3s) == 0:
    print(f"  Saving '{link}' to document properties...")
    gfiles.update(fileId=file['id'], body=data).execute()
    continue
  # if old-style doc, reformat to the new style and add metadata
  ps_with_text = [p for p in ps if p.get_text() != ""]
  if len(ps_with_text) == 2 and len(h2s) == len(h3s) and len(h3s) == 0:
    title = ps_with_text[0].get_text()
  elif len(ps_with_text) == 1 and ps_with_text[0].get_text() == link:
    title = file['name']
  else:
    print("  Doesn't match any known link doc format. Skipping")
    continue
  data['mimeType'] = 'text/html'
  html = f"""<h2>{title}</h2><a href="{link}">{link}</a>"""
  print("  Updating style and adding metadata...")
  gfiles.update(
    fileId=file['id'],
    body=data,
    media_body=gdrive.string_to_media(html, 'text/html'),
  ).execute()
