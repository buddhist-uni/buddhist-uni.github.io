#!/bin/python3

from shutil import rmtree
import re
from pathlib import Path

import website
from strutils import (
  prompt
)

TAG_FOLDER_NAME = 'concepts'
CONTENT_FOLDER_NAME = 'library'
AUTHOR_FOLDER_NAME = 'authors'

MARKDOWN_REGEXES = [
  (re.compile(r'\]\(\/content\/articles\/([0-9a-z_\.-]+)\)'), rf']({CONTENT_FOLDER_NAME}/obu_article_\1.md)'),
  (re.compile(r'\]\(\/content\/av\/([0-9a-z_\.-]+)\)'), rf']({CONTENT_FOLDER_NAME}/obu_av_\1.md)'),
  (re.compile(r'\]\(\/content\/booklets\/([0-9a-z_\.-]+)\)'), rf']({CONTENT_FOLDER_NAME}/obu_book_\1.md)'),
  (re.compile(r'\]\(\/content\/canon\/([0-9a-z_\.-]+)\)'), rf']({CONTENT_FOLDER_NAME}/obu_canon_\1.md)'),
  (re.compile(r'\]\(\/content\/essays\/([0-9a-z_\.-]+)\)'), rf']({CONTENT_FOLDER_NAME}/obu_essay_\1.md)'),
  (re.compile(r'\]\(\/content\/excerpts\/([0-9a-z_\.-]+)\)'), rf']({CONTENT_FOLDER_NAME}/obu_chap_\1.md)'),
  (re.compile(r'\]\(\/content\/monographs\/([0-9a-z_\.-]+)\)'), rf']({CONTENT_FOLDER_NAME}/obu_book_\1.md)'),
  (re.compile(r'\]\(\/content\/papers\/([0-9a-z_\.-]+)\)'), rf']({CONTENT_FOLDER_NAME}/obu_paper_\1.md)'),
  (re.compile(r'\]\(\/content\/reference\/([0-9a-z_\.-]+)\)'), rf']({CONTENT_FOLDER_NAME}/obu_ref_\1.md)'),
  (re.compile(r'\]\(\/authors\/([0-9a-z_\.-]+)\)'), rf']({AUTHOR_FOLDER_NAME}/\1.md)'),
  (re.compile(r'\]\(\/tags\/([0-9a-z_\.-]+)\)'), rf']({TAG_FOLDER_NAME}/obu_\1.md)'),
  (re.compile(r'\]\(\/([\/0-9a-z_\.-]+)\)'), rf']({website.baseurl}/\1)')
]

def remove_curly_brackets(text: str) -> str:
  stack = 0
  result = ""
  for ch in text:
    if ch == "{":
      stack += 1
    elif ch == "}" and stack > 0:
      stack -= 1
    elif stack == 0:
      result += ch
  return result

def obsidianify_markdown(text: str) -> str:
  text = remove_curly_brackets(text)
  for regex, sub in MARKDOWN_REGEXES:
    text = regex.sub(sub, text)
  return text

def make_tag_list(tags) -> str:
  ret = []
  for p in tags:
    t = website.tags.get(p)
    if t:
      ret.append(f'[{t.title}]({TAG_FOLDER_NAME}/obu_{p}.md)')
  return ' | '.join(ret)

def export_tag(tag: website.TagFile, outdir: Path) -> None:
  parents = make_tag_list(tag.parents)
  children = make_tag_list(tag.children)
  if children:
    children = f"\n\n- Subcategories: {children}"
  outpath = outdir.joinpath(f"obu_{tag.slug}.md")
  outpath.write_text(f"""---
title: "{tag.title}"
aliases:
  - "{tag.title}"
url: "{website.baseurl}{tag.url}"
tags:
  - "#concept"
---

- categories: {parents}

{obsidianify_markdown(tag.content)}{children}
""")

def export_author(author: website.AuthorFile, outdir: Path):
  outpath = outdir.joinpath(f"{author.slug}.md")
  outpath.write_text(f"""---
title: "{author.title}"
aliases:
  - "{author.title}"
url: "{website.baseurl}{author.url}"
tags:
  - "#obu-author"
  - "#people"
---

{obsidianify_markdown(author.content)}
""")

def export_content(content: website.ContentFile, outdir: Path) -> None:
  cat = ''
  match content.relative_path.parts[1]:
    case 'articles':
      cat = 'article'
    case 'av':
      cat = 'av'
    case 'booklets':
      cat = 'book'
    case 'canon':
      cat = 'canon'
    case 'essays':
      cat = 'essay'
    case 'excerpts':
      cat = 'chap'
    case 'monographs':
      cat = 'book'
    case 'papers':
      cat = 'paper'
    case 'reference':
      cat = 'ref'
  outpath = outdir.joinpath(f"obu_{cat}_{content.relative_path.name}")
  tags = []
  if content.course:
    tags.append(content.course)
  if content.tags:
    tags.extend(content.tags)
  additional_metadata = ""
  if content.subcat == "podcast":
    additional_metadata += '\n  - "#podcasts"'
  authors = []
  for author in content.authors or []:
    if ' ' in author:
      authors.append(f"[[{author}]]")
    else:
      authors.append(f"[{website.authors.get(author).title}]({AUTHOR_FOLDER_NAME}/{author}.md)")
  authors = ", ".join(authors) or "Unknown"
  outpath.write_text(f"""---
title: "{content.title}"
aliases:
  - "{content.title.split(':')[0]}"
url: "{website.baseurl}{content.url}"
tags:
  - "#obu-biblio"
  - "#{cat}"
  - "#n"
  - "#k"{additional_metadata}
---
**Categories**: {make_tag_list(tags)}

**Related Links:** [[]]

# Title: {content.title}
### Author(s): {authors}
### Date Published: {content.year}
# Quotes / Summary:

{obsidianify_markdown(content.content)}
""")

if __name__ == "__main__":
  output_folder = website.root_folder.joinpath('exports')
  if not output_folder.exists():
    output_folder.mkdir()
  output_folder = output_folder.joinpath('obsidian_vault')
  if output_folder.exists():
    if not prompt('exports/obsidian_vault exists. Overwrite? '):
      quit(1)
    rmtree(output_folder)
  output_folder.mkdir()
  tags_out_folder = output_folder.joinpath(TAG_FOLDER_NAME)
  tags_out_folder.mkdir()
  content_out_folder = output_folder.joinpath(CONTENT_FOLDER_NAME)
  content_out_folder.mkdir()
  author_out_folder = output_folder.joinpath(AUTHOR_FOLDER_NAME)
  author_out_folder.mkdir()
  website.load()
  for tag in website.tags:
    export_tag(tag, tags_out_folder)
  for content in website.content:
    export_content(content, content_out_folder)
  for author in website.authors:
    export_author(author, author_out_folder)
