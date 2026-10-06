#!/bin/python3

import tag_predictor
import gdrive_base
import gdrive
import json
from tqdm import tqdm
from random import shuffle

def sync_youtube_metadata():
  remote_files = {
    f['name']: f
    for f in gdrive.gcache.get_children(gdrive.YOUTUBE_METADATA_FOLDER_ID)
    if f['name'].endswith('.json')
  }
  local_files = {
    p.name: p
    for p in tag_predictor.YOUTUBE_DATA_FOLDER.glob('*.json')
  }

  remote_only = [f for name, f in remote_files.items() if name not in local_files]
  local_only = [p for name, p in local_files.items() if name not in remote_files]
  common_names = set(remote_files.keys()) & set(local_files.keys())

  to_download = [
    (r_file['id'], tag_predictor.YOUTUBE_DATA_FOLDER.joinpath(r_file['name']))
    for r_file in remote_only
  ]
  to_update_remote = []

  for name in common_names:
    r_file = remote_files[name]
    l_file = local_files[name]
    r_size = int(r_file.get('size') or 0)
    l_size = l_file.stat().st_size
    if l_size > r_size:
      to_update_remote.append((l_file, r_file['id']))
    elif r_size > l_size:
      to_download.append((r_file['id'], l_file))

  if to_download:
    print("Downloading YouTube metadata from Drive:")
    for remote_id, dest_path in tqdm(to_download, unit="f"):
      if dest_path.exists():
        dest_path.unlink()
      part_path = dest_path.with_suffix(dest_path.suffix + '.part')
      if part_path.exists():
        part_path.unlink()
      gdrive_base.download_file(remote_id, dest_path, verbose=False)
    print(f"✅ {len(to_download)} downloaded!")
  else:
    print("✅ Nothing to download from Drive")

  if local_only:
    print("Uploading new YouTube metadata to Drive:")
    for l_path in tqdm(local_only, unit="f"):
      gdrive_base.upload_to_google_drive(
        l_path,
        folder_id=gdrive.YOUTUBE_METADATA_FOLDER_ID,
        verbose=False,
      )
    print(f"✅ {len(local_only)} new files uploaded!")
  else:
    print("✅ No new files to upload")

  if to_update_remote:
    print("Updating YouTube metadata on Drive:")
    for l_path, remote_id in tqdm(to_update_remote, unit="f"):
      gdrive_base.upload_to_google_drive(
        l_path,
        update_file=remote_id,
        verbose=False,
      )
    print(f"✅ {len(to_update_remote)} files updated on the server!")
  else:
    print("✅ Nothing to update on Drive")

  if local_only or to_update_remote:
    gdrive.gcache.update()

sync_youtube_metadata()

cached_files = list(tag_predictor.YOUTUBE_DATA_FOLDER.glob('*.json'))
shuffle(cached_files)

for metafile in tqdm(cached_files):
  with metafile.open() as fp:
    data = json.load(fp)
  transcript = data.get('transcript', None)
  if transcript:
    continue
  vid = data.get('id', metafile.stem)
  data['id'] = vid

  doc = gdrive.get_video_doc(vid)
  from_doc = False
  if doc:
    total_duration = gdrive.parse_iso8601_duration((data.get('contentDetails') or {}).get('duration'))
    transcript = gdrive.extract_transcript_from_doc(doc['id'], total_duration=total_duration)
    if transcript:
      from_doc = True

  if not transcript:
    transcript = gdrive.fetch_youtube_transcript(vid)

  if transcript:
    data['transcript'] = transcript
    if 'publishedAt' not in data:
      try:
        snippet = gdrive.get_ytvideo_snippets([vid])[0]
        data.update(snippet)
      except IndexError:
        pass
    with metafile.open('w') as fp:
      json.dump(data, fp)
    print(f"Updating on Drive...")
    remotes = gdrive.gcache.files_exactly_named(metafile.name)
    remotes = [r for r in remotes if r['parent_id'] == gdrive.YOUTUBE_METADATA_FOLDER_ID]
    assert len(remotes) == 1, f"Expected exactly one remote file, got {remotes}"
    gdrive_base.upload_to_google_drive(
      metafile,
      update_file=remotes[0]['id'],
      verbose=False,
    )
    if isinstance(transcript, str):
      print(f"{vid} marked as \"{transcript}\"")
    else:
      print(f"{vid} has a transcript now!")
      if from_doc:
        # pyrefly: ignore [unsupported-operation]
        print(f"  (pulled from Google Doc https://docs.google.com/document/d/{doc['id']}/edit)")
      elif doc:
        link = f'https://youtu.be/{vid}'
        new_html = f"""<h1>{doc['name']}</h1><h2><a href="{link}">{link}</a></h2>"""
        new_html += gdrive._make_ytvideo_summary_html(vid, data, transcript)
        gdrive_base.session().files().update(
          fileId=doc['id'],
          body={'mimeType':'text/html'},
          media_body=gdrive_base.string_to_media(new_html, 'text/html'),
        ).execute()
        print(f"  and replaced https://docs.google.com/document/d/{doc['id']}/edit")

