#!/bin/python3

from archivedotorg import archive_urls
import gdrive

FIELDS = "id,properties,name,size"

def regen_link_doc(docid, title=None, link=None):
  if not (link and title):
    fdata = gdrive.session().files().get(fileId=docid,fields=FIELDS).execute()
    if not link:
      link = fdata['properties']['url']
    if not title:
      title = fdata['name']
  html = gdrive.make_link_doc_html(title, link)
  gdrive.session().files().update(
    fileId=docid,
    body={'mimeType':'text/html'},
    media_body=gdrive.string_to_media(html, 'text/html'),
  ).execute()

if __name__ == '__main__':
  QUERY = " and ".join([
    "mimeType='application/vnd.google-apps.document'",
    "trashed=false",
    "'me' in writers",
    "properties has { key='createdBy' and value='LibraryUtils.LinkSaver' }",
  ])
  urls = []
  for file in gdrive.all_files_matching(QUERY, FIELDS, page_size=2):
    print(f"Regenerating '{file['name']}'...")
    link = file['properties']['url']
    regen_link_doc(file['id'], title=file['name'], link=link)
    if 'youtu' not in link:
      urls.append(link)
  print(f"Ensuring all {len(urls)} (non-YT) URLs are saved to Archive.org...")
  archive_urls(urls)

