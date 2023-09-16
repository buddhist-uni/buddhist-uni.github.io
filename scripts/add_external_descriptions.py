#!/bin/python3

import os
import json
from pathlib import Path
from random import shuffle

from strutils import (
  input_with_prefill,
  does_md_only_contain_quotes,
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

def get_blurb_for_suttaid(suttaid_str):
  suttaid_str = suttaid_str.lower()
  suttaid = sutta_id_re.match(suttaid_str)
  if not suttaid:
    return None
  book = suttaid.group(1)
  if book == 'vv':
    nums = [int(suttaid.group(2)), int(suttaid.group(3))]
    suttaid = f"vv{nums[1]+VV_VAGGA_COUNTS[nums[0]-1]}"
  else:
    suttaid = suttaid_str
  try:
    return BLURBS[book][f"{book}-blurbs:{suttaid}"].strip()
  except KeyError:
    return None

def process_canon_file(file):
  file = Path(file)
  blurb = get_blurb_for_suttaid(file.stem)
  if not blurb:
    print(" No blurb found")
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
  canon_folder = git_root_folder.joinpath("_content", "canon")
  files = list(canon_folder.iterdir())
  shuffle(files)
  for file in files:
    print(f"Processing {file.stem}...")
    process_canon_file(file)
