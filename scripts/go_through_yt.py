#!/bin/python3

from yaspin import yaspin
import json
from time import sleep
import random
from strutils import (
  radio_dial,
  system_open,
)
import gdrive_base
import gdrive

def weighted_shuffle(items: list, weights: list[float]) -> list:
  """
  Shuffle items where higher weights tend toward the top.
  
  Args:
    items: List of items to shuffle
    weights: List of weights (higher = more likely near top)
  
  Returns:
    Shuffled list with heavier items tending toward top
  """
  # Pair each item with a random value raised to (1/weight)
  # Higher weights make the random value larger on average
  paired = [(random.random() ** (1.0 / w), item) 
            for item, w in zip(items, weights)]
  
  # Sort by the random values (descending)
  paired.sort(reverse=True)
  
  # Return just the items
  return [item for _, item in paired]

with yaspin(text="Loading folders..."):
  BULK_YT_FOLDERS_NAME = "📼 YouTube Videos"
  BULK_YT_FOLDERS = gdrive.gcache.files_exactly_named(BULK_YT_FOLDERS_NAME)
  PARENT_FOLDERS = {
    folder['id']: folder['parent_id']
    for folder in gdrive.gcache.get_items([folder['parent_id'] for folder in BULK_YT_FOLDERS])
  }
  PRIVATE_FOLDER_TO_COURSE_SLUG = {
    gdrive_base.folderlink_to_id(value['private']): key
    for key, value in json.loads(gdrive.FOLDERS_DATA_FILE.read_text()).items()
    if value.get('private')
  }
  YT_FOLDER_TO_COURSE_SLUG = {
    folder['id']: PRIVATE_FOLDER_TO_COURSE_SLUG[PARENT_FOLDERS[folder['parent_id']]]
    for folder in BULK_YT_FOLDERS
  }


class YTVideo():
  def __init__(self, data: dict) -> None:
    """Initialize using a Google Drive Dict"""
    self.title = data['name']
    self.url = data['properties']['url']
    self.gid = data['id']
    self.doc_size = data['size']
    self.tentative_course_slug = YT_FOLDER_TO_COURSE_SLUG[data['parent_id']]
  def __str__(self) -> str:
    return f"""
    Title: {self.title}
    Tentative course: {self.tentative_course_slug}
    """

class YTQueueDB():
  def __init__(self) -> None:
    self.pull_from_db()
    with yaspin(text="Shuffling videos..."):
      self.videos = weighted_shuffle(self.videos, [video.doc_size for video in self.videos])
    self.i = 0

  def pull_from_db(self) -> None:
    with yaspin(text="Loading videos..."):
      gdocs = gdrive.gcache.parent_sql_query(
        """file.url_property LIKE '%youtu%' AND
        file.owner = 1 AND
        file.mime_type='application/vnd.google-apps.document' AND
        parent.name = ?""",
        (BULK_YT_FOLDERS_NAME,)
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
    gfolder = gdrive.get_gfolders_for_course(course)
    gdrive.move_gfile(vid.gid, gfolder)

