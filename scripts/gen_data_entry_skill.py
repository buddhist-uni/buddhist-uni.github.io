#!/bin/python3

from collections.abc import Iterable
import zipfile
from pathlib import Path

import requests

from strutils import git_root_folder
from gen_controlled_vocab_doc import gen_document as gen_tags_doc
from gen_controlled_vocab_doc import DOCUMENT_INTRO as TAG_DOC_INTRO
import website

SKILL_PREAMBLE = """---
name: obu-data-entry
description: Guide for writing the content markdown files for OBU library items.
---

# OBU Data Entry

Unless otherwise asked, your task is to write the Jekyll markdown file for adding a given, indicated work to the OBU website.
Give the user the full file path, the markdown file, and any relevant explanations.

Below you'll find our instructions on the exact format of our content markdown files.
The user prompt may provide you with some field values already (usually the drive link and course).
If they do, they're quite confident in them, but feel free to ask if you think they made a mistake.

In filling out those markdown files, you'll need to supply `course` and `tag` values for the topics covered by the given work.
The attached `references/obu_subject_ontology.md` file contains the full list of approved slug values for these fields and what they mean.
That file is large, so you may want to grep through it for just the bits relevant to the given file.

Along with the markdown file, give an explanation of why you felt this work deserves to be in the selected course and/or tags.
Also, for any tags you considered, but rejected, explain why you decided _not_ to give it that tag.
Remember that these tags aren't just keywords ("oh this is about this") but you think this work should go in an undergrad class
introducing the given topic (a much higher bar).
"""

OTHER_DOCS_INTRO = """
These references are short, simple markdown lists of entities and their slugs:
```markdown
- `entity-slug` = "The Full Name of that Entity"
```

For authors, periodicals, and publishers, if they're on the list, use their slug.
Otherwise, use their name.
"""

content_path = git_root_folder/"_content"
EXAMPLE_FILES = [
  content_path/"articles"/"monumental-stone-sutra-carvings-china-indian-pilgrim-sites_wenzel.md",
  content_path/"monographs"/"converting-american-buddhism_baker-drew.md",
  content_path/"monographs"/"saints-and-psychopaths_hamilton.md",
]

def fetch_adding_items_wiki() -> str:
  req = requests.get("https://raw.githubusercontent.com/wiki/buddhist-uni/buddhist-uni.github.io/Adding-items-to-the-library.md")
  assert req.ok, "Failed to fetch the adding items wiki page"
  return req.text

def gen_main_skill_doc() -> str:
  ret = SKILL_PREAMBLE
  ret += "\n# Adding items to the library: Our content markdown file format\n\n"
  ret += fetch_adding_items_wiki()
  ret += "\n\n# The obu_subject_ontology.md format\n\n" + TAG_DOC_INTRO
  ret += "This concludes the information on how to read the `obu_subject_ontology.md` reference file.\n\n"
  ret += "# The format for publishers.md, authors.md, journals.md\n"
  ret += OTHER_DOCS_INTRO
  ret += f"\n\n# Examples\n\nHere are {len(EXAMPLE_FILES)} examples of what a content markdown file should look like.\n"
  for example_path in EXAMPLE_FILES:
    ret += f"\n\n`{example_path.relative_to(git_root_folder)}`\n~~~markdown\n"
    ret += example_path.read_text().strip() + "\n~~~"
  return ret

def gen_entity_doc(entities: Iterable[website.JekyllFile]) -> str:
  ret = ""
  for entry in iter(entities):
    ret += f"- `{entry.slug}` = \"{entry.title}\"\n"
  return ret

def main(outpath: Path, max_examples: int=1) -> int:
  print("Generating skill file...")
  with zipfile.ZipFile(file=outpath, mode='w', compression=zipfile.ZIP_DEFLATED, compresslevel=4) as skill:
    skill.writestr("SKILL.md", gen_main_skill_doc())
    skill.writestr(
      "references/obu_subject_ontology.md",
      gen_tags_doc(max_examples=max_examples, include_intro=False),
    )
    # The gen_tags_doc above implicitly loads the website data
    skill.writestr(
      "references/authors.md",
      gen_entity_doc(website.authors),
    )
    skill.writestr(
      "references/publishers.md",
      gen_entity_doc(website.publishers),
    )
    skill.writestr(
      "references/journals.md",
      gen_entity_doc(website.journals),
    )
  print(f"Wrote \"{outpath}\"")
  return 0

if __name__ == "__main__":
  import argparse
  argparser = argparse.ArgumentParser(
    description="Generates a Manus-compatible skill zip for the data entry job",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
  )
  argparser.add_argument(
    "-o", "--output",
    type=Path,
    default=git_root_folder/"assets"/"obu-data-entry.zip",
  )
  argparser.add_argument(
    '--max-examples',
    type=int,
    default=1,
  )
  args = argparser.parse_args()
  exit(main(outpath=args.output, max_examples=args.max_examples))
