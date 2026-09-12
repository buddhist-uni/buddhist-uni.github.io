#!/bin/python3

from collections.abc import Callable, Iterator
from typing import Any
import re
import bisect
from pathlib import Path
from functools import cached_property
from strutils import (
  git_root_folder,
)
from executils import git_grep
import website
import gdrive
from yaspin import yaspin
from datetime import datetime

DOCUMENT_PREAMBLE = f"""---
title: The Open Buddhist University Subject Tags
---

Version {datetime.now():%Y-%m-%d %H:%M:%S}

This document explains OBU's controlled vocabulary for topics.

Content in the OBU library can get 0 or 1 `course` value and N `tags` set to subject slugs.
Subject slugs are strings composed only of lowercase letters [a-z], numbers [0-9], and hyphens [-].
For example, `material-culture` or `violence-since-ww2` are subject slugs.
The `course` attribute represents the primary topic that the work is about.
The `tags` represent the secondary topics that the work is about.

The primary tag is called its `course` because it represents our best guess at the undergrad-level
course that this work would be assigned in, if it were to be assigned to an undergrad as homework.
Similarly, the secondary `tags` represent other courses that might assign this work, either as
homework or as further/background reading.

Thus, our subject tags are not exactly "keywords," but represent a topic one might study over,
say, a semester.
This means that nearly all topics should be understood to have an implied "Intro to" at the beginning
or perhaps an implied " (General)" at the end.
Do not tag everything about Buddhism with `buddhism`! Only the most introductory material should get
that parent tag. Most items about Buddhism should get a more specific tag, like "Buddhist Cosmology" or
"Modern Chinese Buddhism," etc.

# The Format of this Document

The rest of this markdown file will list and explain our current set of tags.

# The Tags

In alphabetical order by their slug.

"""

class TagMetadata:
  def __init__(
    self,
    tree: "TagTree",
    slug: str,
    site_tag: website.TagFile | None = None,
  ):
    self.tree = tree
    self.slug = slug
    self.site_tag = site_tag
    try:
      self.folder_ids = gdrive.get_gfolders_for_course(slug, invite_to_add=False)
    except ValueError:
      self.folder_ids = (None, None)
    if self.folder_ids[0]:
      self.public_folder = gdrive.gcache.get_item(self.folder_ids[0])
    else:
      self.public_folder = None
    if self.folder_ids[1]:
      self.private_folder = gdrive.gcache.get_item(self.folder_ids[1])
    else:
      self.private_folder = None

  @cached_property
  def inline_name(self) -> str:
    if self.site_tag:
      inline_name = self.site_tag.title
    elif self.public_folder:
      inline_name = self.public_folder['name']
    elif self.private_folder:
      inline_name = self.private_folder['name']
    else:
      return f"`{self.slug}`"
    return inline_name + f" (`{self.slug}`)"

  @cached_property
  def parent(self) -> "TagMetadata | None":
    if self.site_tag:
      if self.site_tag.level == 1:
        return None
      return self.tree.get_tag(self.site_tag.parents[0])
    elif self.private_folder:
      return self.tree.get_tag_where(
        lambda t: t.private_folder and t.private_folder['id'] == self.private_folder['parent_id']
      )
    elif self.public_folder:
      return self.tree.get_tag_where(
        lambda t: t.public_folder and t.public_folder['id'] == self.public_folder['parent_id']
      )
    else:
      raise ValueError(f"I don't know how to determine the parent in that case")

  def get_siblings(self) -> "list[TagMetadata]":
    return self.tree.get_tags_where(
      lambda t: t.parent == self.parent and t.slug != self.slug
    )
  
  def get_children(self) -> "list[TagMetadata]":
    return self.tree.get_tags_where(
      lambda t: t.parent == self
    )
  
  def get_broader(self) -> "list[TagMetadata]":
    # TODO also get Google Drive shortcut locations
    ret = [
      self.tree.get_tag(p)
      for p in self.site_tag.parents[1:]
    ] if self.site_tag else []
    return [p for p in ret if p]
  
  def get_narrower(self) -> "list[TagMetadata]":
    # TODO also get google drive shortcut children
    return self.tree.get_tags_where(
      lambda t: t.site_tag and self.slug in t.site_tag.parents[1:]
    )

  def gen_documentation(self) -> str:
    ret = f"\n\n## `{self.slug}`"
    blurb = None
    if self.site_tag:
      blurb = re.sub(r"\[([^\]]+)\]\(\/tags\/([a-z0-9-]+)\)", r'\1 (see `\2`)', self.site_tag.content).strip()
      ret += f" = {self.site_tag.title}"
      if self.public_folder and self.public_folder['name'] != self.site_tag.title:
        if not (self.public_folder['name'].startswith('The ') and self.public_folder['name'][4:] == self.site_tag.title):
          ret += "\n\n**Alternative Title**: " + self.public_folder['name']
    elif self.public_folder:
      ret += f" = {self.public_folder['name']}"
    if blurb:
      ret += f"\n\n### Description\n\n{blurb}"
    ret += "\n\n### Relationships\n"
    if self.parent:
      ret += "\n**Parent**: "
      ret += self.parent.inline_name
    siblings = self.get_siblings()
    if siblings:
      ret += "\n**Siblings**: ["
      ret += ", ".join([s.inline_name for s in siblings])
      ret += "]"
    children = self.get_children()
    if children:
      ret += "\n**Children**: ["
      ret += ", ".join([s.inline_name for s in children])
      ret += "]"
    broader = self.get_broader()
    if broader:
      ret += "\n**Other Broader**: ["
      ret += ", ".join([s.inline_name for s in broader])
      ret += "]"
    narrower = self.get_narrower()
    if narrower:
      ret += "\n**Other Narrower**: ["
      ret += ", ".join([s.inline_name for s in narrower])
      ret += "]"
    ret += "\n\n"
    return ret

class TagTree:
  def __init__(self):
    self.slug_to_metadata: dict[str, TagMetadata] = dict()
    self.sorted_slugs: list[str] = []
  def load(self):
    for tagfile in website.tags:
      tag = TagMetadata(self, tagfile.slug, site_tag=tagfile)
      self.add_tag(tag)

  def add_tag(self, tag: TagMetadata):
    assert tag.slug not in self.slug_to_metadata
    self.slug_to_metadata[tag.slug] = tag
    bisect.insort(self.sorted_slugs, tag.slug)

  def get_tag(self, slug: str) -> TagMetadata | None:
    return self.slug_to_metadata.get(slug)
  
  def get_tag_where(self, condition: Callable[[TagMetadata], Any]) -> TagMetadata | None:
    for tag in self.slug_to_metadata.values():
      if condition(tag):
        return tag
    return None
  
  def get_tags_where(self, condition: Callable[[TagMetadata], Any]) -> list[TagMetadata]:
    return [
      tag for tag in self.slug_to_metadata.values()
      if condition(tag)
    ]

  def __iter__(self) -> Iterator[TagMetadata]:
    for slug in self.sorted_slugs:
      yield self.slug_to_metadata[slug]

def mark_solid_content():
  solids = set(git_grep('[#y] [sS]olidly'))
  ret = 0
  for c in website.content:
    if c.absolute_path in solids:
      c.is_solid = True
      ret += 1
    else:
      c.is_solid = False
  return ret

def gen_document() -> str:
  ret = DOCUMENT_PREAMBLE
  tag_tree = TagTree()
  with yaspin(text="Compiling the tag tree..."):
    tag_tree.load()
  for tag in tag_tree:
    ret += tag.gen_documentation()
  return ret

def main(outpath: Path):
  with yaspin(text="Loading website...") as sp:
    website.load()
    solids = mark_solid_content()
    sp.ok(text=f"Loaded website and found {solids} \"solid\" pieces")
  outpath.write_text(gen_document())
  print(f"Document written to {outpath}")
  return 0

if __name__ == "__main__":
  import argparse
  argparser = argparse.ArgumentParser(
    description="Generates a markdown file explaining OBU's subject ontology",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
  )
  argparser.add_argument(
    "-o", "--output", nargs="?",
    type=Path,
    default=git_root_folder/'assets'/'obu_subject_ontology.md',
  )
  args = argparser.parse_args()
  exit(main(outpath=args.output))
