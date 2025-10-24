#!/bin/python3

import tag_predictor
import gdrive
import json
from tqdm import tqdm

for metafile in tqdm(list(tag_predictor.YOUTUBE_DATA_FOLDER.glob('*.json'))):
  with metafile.open() as fp:
    data = json.load(fp)
  transcript = data.get('transcript', None)
  if transcript:
    continue
  transcript = gdrive.fetch_youtube_transcript(data['id'])
  if transcript:
    data['transcript'] = transcript
    with metafile.open('w') as fp:
      json.dump(data, fp)

