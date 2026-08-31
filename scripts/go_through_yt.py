#!/bin/python3

from yaspin import yaspin
from time import sleep
from strutils import (
  radio_dial,
)
from mathutils import weighted_shuffle
from executils import system_open
import gdrive_base
import gdrive
import website

with yaspin(text="Loading folders..."):
  BULK_YT_FOLDERS_NAME = "📼 YouTube Videos"
  BULK_YT_FOLDERS = gdrive.gcache.files_exactly_named(BULK_YT_FOLDERS_NAME)
  PARENT_FOLDERS = {
    folder['id']: folder['parent_id']
    for folder in gdrive.gcache.get_items([folder['parent_id'] for folder in BULK_YT_FOLDERS])
  }
  PRIVATE_FOLDER_TO_COURSE_SLUG = {
    gdrive_base.folderlink_to_id(value['private']): key
    for key, value in gdrive.FOLDERS_DATA().items()
    if value.get('private')
  }
  YT_FOLDER_TO_COURSE_SLUG = {
    folder['id']: PRIVATE_FOLDER_TO_COURSE_SLUG[PARENT_FOLDERS[folder['parent_id']]]
    for folder in BULK_YT_FOLDERS
  }
  website.tags.load()


class YTVideo():
  def __init__(self, data: dict) -> None:
    """Initialize using a Google Drive Dict"""
    self.title = data['name']
    self.url = data['properties']['url']
    self.gid = data['id']
    self.doc_size = data['size']
    self.tentative_course_slug = YT_FOLDER_TO_COURSE_SLUG[data['parent_id']]
    self.parent_id = data['parent_id']
  def __str__(self) -> str:
    return f"""
    Title: {self.title}
    Tentative course: {self.tentative_course_slug}
    """

class YTQueueDB():
  def __init__(self) -> None:
    self.pull_from_db()
    with yaspin(text="Shuffling videos..."):
      self.videos = weighted_shuffle(self.videos, [
        video.doc_size * website.tags.get_weight_for_tag(video.tentative_course_slug)
        for video in self.videos
      ])
    self.i = 0

  def pull_from_db(self) -> None:
    with yaspin(text="Loading videos..."):
      valid_parent_ids = [f['id'] for f in BULK_YT_FOLDERS]
      placeholders = ','.join('?' * len(valid_parent_ids))
      gdocs = gdrive.gcache.properties_sql_query(
        f"""prop.key = 'url' AND
        prop.value LIKE '%youtu%' AND
        file.owner = 1 AND
        file.mime_type='application/vnd.google-apps.document' AND
        file.parent_id IN ({placeholders})""",
        tuple(valid_parent_ids)
      )
      self.videos = [YTVideo(gdoc) for gdoc in gdocs]

  def next(self) -> YTVideo | None:
    if self.i >= len(self.videos):
      return None
    ret = self.videos[self.i]
    self.i += 1
    return ret

  def __len__(self):
    return len(self.videos)

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
      sleep(3)
    course = gdrive.input_course_string_with_tab_complete(prefill=vid.tentative_course_slug)
    tags = []
    print("tags:")
    while True:
      tag = gdrive.input_course_string_with_tab_complete(prompt='  - ')
      if not tag:
        break
      tags.append(tag)
    gfolder = gdrive.get_gfolders_for_course(course)
    gdrive.log_move_reason(
      vid.gid,
      new_parent_id=gfolder[0] or gfolder[1],
      old_parent_id=vid.parent_id,
      reason="Initial (manual) sort out of the YouTube autosort folder",
      alternate_tags=tags,
    )
    gdrive.move_gfile(vid.gid, gfolder)

