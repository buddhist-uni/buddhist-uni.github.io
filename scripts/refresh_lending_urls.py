#!/bin/python3

from pathlib import Path
import re

from archivedotorg import find_lendable_archiveorg_url_for_metadata

try:
  import frontmatter
except:
  print("  pip install python-frontmatter")
  quit(1)

def replace_lending_url_for_file(filepath):
  filepath = Path(filepath)
  page = frontmatter.load(filepath)
  newurl = find_lendable_archiveorg_url_for_metadata(page.metadata)
  file = filepath.read_text()
  newfile = re.sub(r"external_url: .+", f"external_url: \"{newurl}\"", file)
  filepath.write_text(newfile)

if __name__ == "__main__":
  print("TODO")

