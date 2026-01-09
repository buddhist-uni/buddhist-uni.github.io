#!/bin/python3

import tag_predictor
import gdrive_base
import gdrive
import json
from tqdm import tqdm
from random import shuffle

cached_files = list(tag_predictor.YOUTUBE_DATA_FOLDER.glob('*.json'))
shuffle(cached_files)

for metafile in tqdm(cached_files):
  with metafile.open() as fp:
    data = json.load(fp)
  transcript = data.get('transcript', None)
  if transcript:
    continue
  transcript = gdrive.fetch_youtube_transcript(data['id'])
  if transcript:
    data['transcript'] = transcript
    if 'publishedAt' not in data:
      try:
        snippet = gdrive.get_ytvideo_snippets([data['id']])[0]
        data.update(snippet)
      except IndexError:
        pass
    with metafile.open('w') as fp:
      json.dump(data, fp)
    if isinstance(transcript, str):
      print(f"{data['id']} marked as \"{transcript}\"")
    else:
      print(f"{data['id']} has a transcript now!")
      link = f'https://youtu.be/{data["id"]}'
      doc = gdrive.gcache.get_url_doc(link)
      if doc:
        new_html = f"""<h1>{doc['name']}</h1><h2><a href="{link}">{link}</a></h2>"""
        new_html += gdrive._make_ytvideo_summary_html(data['id'], data, transcript)
        gdrive_base.session().files().update(
          fileId=doc['id'],
          body={'mimeType':'text/html'},
          media_body=gdrive_base.string_to_media(new_html, 'text/html'),
        ).execute()
        print(f"  and replaced https://docs.google.com/document/d/{doc['id']}/edit")

