#!/bin/python3

from pathlib import Path
import re

from strutils import FileSyncedSet, git_root_folder
from archivedotorg import (
  find_lendable_archiveorg_url_for_metadata,
  extract_archiveorg_id,
  is_archiveorg_item_lendable
)

try:
  import frontmatter
except:
  print("  pip install python-frontmatter")
  quit(1)

def refresh_lending_url_for_file(monograph_file):
  monograph_file = Path(monograph_file)
  file_text = monograph_file.read_text()
  page = frontmatter.loads(file_text)
  if 'drive_links' in page.metadata or 'source_url' in page.metadata:
    return False
  print("")
  if 'external_url' in page.metadata:
    aoid = extract_archiveorg_id(page.metadata['external_url'])
    if not aoid:
      print(f"\"{page.metadata['title']}\" is not an Archive.org lending book. Skipping it...")
      return False
    if is_archiveorg_item_lendable(aoid):
      print(f"\"{page.metadata['title']}\" is still lendable :)")
      return False
    newurl = find_lendable_archiveorg_url_for_metadata(page.metadata)
    if newurl:
      print("Replacing external_url...")
      newfile = re.sub(r"external_url: .+", f"external_url: \"{newurl}\"", file_text)
    else:
      print("Removing external_url...")
      newfile = re.sub(r"external_url: .+\n", "", file_text)
    monograph_file.write_text(newfile)
    return True
  url = find_lendable_archiveorg_url_for_metadata(page.metadata)
  if not url:
    return False
  print("Adding external_url to file... :)")
  if file_text.count("\npublisher: ") != 1:
    raise Exception("Wtf? A monograph should have exactly one publisher...")
  newfile = file_text.replace("\npublisher: ", f"\nexternal_url: \"{url}\"\npublisher: ")
  monograph_file.write_text(newfile)
  return True

if __name__ == "__main__":
  monographs_folder = git_root_folder.joinpath("_content", "monographs")
  processed = FileSyncedSet("processed_monographs.txt")
  for monograph_file in monographs_folder.iterdir():
    if monograph_file in processed:
      continue
    refresh_lending_url_for_file(monograph_file)
    processed.add(monograph_file)
  processed.delete_file()

