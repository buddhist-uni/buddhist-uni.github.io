#!/bin/python3

from yaspin import yaspin
with yaspin(text="Initializing..."):
  from pathlib import Path
  import random
  import json
  from datetime import datetime, timedelta
  import gdrive_base
  import gdrive
  from strutils import (
    radio_dial,
    system_open,
    input_with_tab_complete,
  )
  
  DB_PATH = Path("~/.local/share/go_through_yt.json").expanduser()
  COURSE_LIST = gdrive.get_known_courses()
  BULK_YT_FOLDERS_NAME = "📼 YouTube Videos"

class YTVideo():
  def __init__(self, data: dict) -> None:
    self.title = data['title']
    self.url = data['url']
    self.gid = data['gid']
  def to_json(self) -> str:
    return json.dumps(self.to_data())
  def glink(self) -> str:
    return gdrive_base.DRIVE_LINK.format(self.gid)
  def to_data(self) -> dict:
    return {
      'title': self.title,
      'url': self.url,
      'gid': self.gid,
    }
  def __str__(self) -> str:
    return f"""
    Title: {self.title}
    """

def get_bulk_yt_folder_ids():
  return {
    folder['id']: folder['parents'][0] for folder in
    gdrive_base.all_files_matching(
      f"name='{BULK_YT_FOLDERS_NAME}' and trashed=false",
      "id,parents"
    )
  }

GDOC_PROPS = "id,properties,name,parents"
DOCS_QUERY = " and ".join([
  "mimeType='application/vnd.google-apps.document'",
  "trashed=false",
  "'me' in writers",
  "properties has { key='createdBy' and value='LibraryUtils.LinkSaver' }",
])

class YTQueueDB():
  def __init__(self) -> None:
    self.last_refreshed = None
    if DB_PATH.is_file():
      self.load_state(json.loads(DB_PATH.read_text()))
    if not self.last_refreshed or self.last_refreshed < (datetime.now() - timedelta(days=700)):
      self.refresh()
      self.save_state()
    random.shuffle(self.videos)
    self.i = 0

  def save_state(self) -> None:
    DB_PATH.write_text(self.to_json())
  
  def to_json(self) -> str:
    return json.dumps(self.to_data())
  
  def to_data(self) -> dict:
    return {
      'bulk_yt_folders': self.bulk_yt_folders,
      'videos': [vid.to_data() for vid in self.videos],
      'last_refreshed': str(self.last_refreshed),
    }

  def load_state(self, data: dict) -> None:
    self.bulk_yt_folders = data['bulk_yt_folders']
    self.videos = [YTVideo(d) for d in data['videos']]
    self.last_refreshed = datetime.fromisoformat(data['last_refreshed'])

  def refresh(self) -> None:
    self.bulk_yt_folders = get_bulk_yt_folder_ids()
    self.videos = list()
    for gdoc in gdrive_base.all_files_matching(DOCS_QUERY, GDOC_PROPS):
      if gdoc['parents'][0] not in self.bulk_yt_folders:
        continue
      self.videos.append(YTVideo({
        'gid': gdoc['id'],
        'url': gdoc['properties']['url'],
        'title': gdoc['name'],
      }))
    self.last_refreshed = datetime.now()

  def next(self) -> YTVideo | None:
    if self.i >= len(self.videos):
      return None
    ret = self.videos[self.i]
    self.i += 1
    return ret
  def __len__(self):
    return len(self.videos)

  def mark_previous_completed(self):
    self.i-=1
    del self.videos[self.i]
    self.save_state()

if __name__ == "__main__":
  with yaspin(text="Loading..."):
    queue = YTQueueDB()
  while vid := queue.next():
    print(str(vid))
    print(f"What to do with video {queue.i} of {len(queue)}?")
    choice = radio_dial([
      "Open...",
      "Skip...",
      "Move...",
    ])
    if choice == 1:
      continue
    if choice == 0:
      system_open(vid.url)
    course = input_with_tab_complete("course: ", COURSE_LIST)
    gfolder = gdrive.get_gfolders_for_course(course)
    gdrive.move_gfile(vid.glink(), gfolder)
    queue.mark_previous_completed()

