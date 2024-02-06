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
    "modifiedTime < '2024-02-05T15:43:26'",
    "trashed=false",
    "'me' in writers",
    "properties has { key='createdBy' and value='LibraryUtils.LinkSaver' }",
  ])
  urls = []
  for file in gdrive.all_files_matching(QUERY, FIELDS):
    link = file['properties']['url']
    print(f"Saving '{file['name']}'...")
    regen_link_doc(file['id'], title=file['name'], link=link)
    if 'youtu' not in link and 'archive.org' not in link:
      archive_urls([link])
