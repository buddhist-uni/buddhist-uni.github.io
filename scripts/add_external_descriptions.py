#!/bin/python3

import os
import json
from pathlib import Path

from strutils import (
  input_with_prefill,
  git_root_folder,
  cumsum,
  sutta_id_re
)

try:
  import frontmatter
except:
  print("  pip install python-frontmatter")
  quit(1)

data_folder = git_root_folder.joinpath("_data")
VV_VAGGA_COUNTS = cumsum([0, 17, 11, 10, 12, 14, 10, 11])

def does_md_only_contain_quotes(text):
  paragraphs = list(filter(lambda p: not not p, map(lambda p: p.strip(), text.split("\n\n"))))
  for p in paragraphs:
    if not p.startswith('>'):
      return False
  return True

BLURBS = {
  'an',
  'sn',
  'iti',
  'mn',
  'pv',
  'vv',
  'dn',
  'snp',
  'ud'
}
BLURBS = {k: json.loads(data_folder.joinpath(f"{k}-blurbs_root-en.json").read_text()) for k in BLURBS}

def process_canon_file(file):
  file = Path(file)
  suttaid = sutta_id_re.match(file.stem)
  if not suttaid:
    print(" Not a sutta")
    return False
  book = suttaid.group(1)
  if book == 'vv':
    nums = [int(suttaid.group(2)), int(suttaid.group(3))]
    suttaid = f"vv{nums[1]+VV_VAGGA_COUNTS[nums[0]-1]}"
    print(f"  {file.stem} => {suttaid}")
  else:
    suttaid = file.stem
  try:
    blurb = BLURBS[book][f"{book}-blurbs:{suttaid}"]
  except KeyError:
    print(" No blurb for this sutta :(")
    return False
  filetext = file.read_text()
  page = frontmatter.loads(filetext)
  if not does_md_only_contain_quotes(page.content):
    print(" Page already contains a description")
    return False
  indented_desc = page.content.replace('\n', '  \n')
  print(f" Existing description:\n  {indented_desc}")
  blurb = input_with_prefill(" Blurb to add:\n::", blurb)
  if blurb:
    filetext += f"\n\n{blurb}\n\n"
    file.write_text(filetext.replace("\n\n\n\n", "\n\n").replace("\n\n\n", "\n\n"))
  else:
    filetext += "\n<!---->\n"
    file.write_text(filetext)
  return True

if __name__ == "__main__":
  canon_folder = Path(os.path.normpath(os.path.join(os.path.dirname(__file__), "../_content/canon/")))
  for file in canon_folder.iterdir():
    print(f"Processing {file.stem}...")
    process_canon_file(file)

