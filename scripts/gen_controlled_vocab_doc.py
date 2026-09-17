#!/bin/python3

from numpy import isin
from collections.abc import Callable, Iterator
from typing import Any
import re
import bisect
from pathlib import Path
from functools import cached_property
from strutils import (
  git_root_folder,
  english_join,
)
from executils import git_grep
import website
import gdrive
from yaspin import yaspin
from datetime import datetime
from tag_predictor import TagPredictor

DOCUMENT_PREAMBLE = f"""---
title: The Open Buddhist University Subject Tags
---

Version {datetime.now():%Y-%m-%d %H:%M:%S}

This document explains OBU's controlled vocabulary for topics.

Subject slugs are strings composed only of lowercase letters [a-z], numbers [0-9], and hyphens [-].
For example, `material-culture` or `violence-since-ww2` are subject slugs.

A work's primary tag is called its `course` because it represents our best guess at the undergrad-level
course that this work would be assigned in, if it were to be assigned to an undergrad as homework.
Similarly, the secondary `tags` represent other courses that might assign this work, either as
homework or as further/background reading.

Thus, our subject tags are not exactly "keywords," but represent a topic one might study over,
say, a semester.
This means that nearly all topics should be understood to have an implied "Intro to" at the beginning
or perhaps an implied " (General)" at the end.
Do not tag everything about Buddhism with `buddhism`! Only the most introductory material should get
that parent tag. Most items about Buddhism should get a more specific tag, like "Buddhist Cosmology" or
"Modern Chinese Buddhism," etc as appropriate.

# The Format of this Document

The rest of this markdown file will list and explain our current set of tags.

The "Discriminative Vocabulary" section lists the most common terms that a one-vs-rest
Support Vector Machine Classifier (SVC) learned to use to discriminate this tag as compared to the
tags listed in parentheses.
Specifically, the terms have the 20 largest `log(document_frequency) * svc_coefficient` values.

# The Tags

In alphabetical order by their slug.

"""
trim_punc = re.compile(r'^[^\w]+|[^\w]+$')

RELATIONSHIP_LIST_STYLE = "\n- "

class TagMetadata:
  def __init__(
    self,
    tree: "TagTree",
    slug: str,
    site_tag: website.TagFile | None = None,
    site_course: website.JekyllFile | None = None,
  ):
    self.tree = tree
    self.slug = slug
    self.site_tag = site_tag
    self.site_course = site_course
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
    elif self.site_course:
      inline_name = self.site_course.title
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
      if self.site_tag.get('level') == 1:
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
    elif self.site_course and self.site_course.get('tags'):
      return self.tree.get_tag(self.site_course.tags[0])
    else:
      raise ValueError(f"I don't know how to determine the parent in that case")

  def get_siblings(self) -> "list[TagMetadata]":
    return self.tree.get_tags_where(
      lambda t: t.parent == self.parent and t != self
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
    if self.site_tag and self.site_tag.get('level') == 1:
      ret.append(self.tree.get_tag(self.site_tag.parents[0]))
    if self.site_course and self.site_course.get('tags'):
      ret.extend([
        self.tree.get_tag(p)
        for p in self.site_course.tags[1:]
        if p not in {q.slug for q in ret if q}
      ])
    return [p for p in ret if p]
  
  def get_narrower(self) -> "list[TagMetadata]":
    # TODO also get google drive shortcut children
    return self.tree.get_tags_where(
      lambda t: (t.site_tag and self.slug in t.site_tag.parents[1:]) or \
        (t.site_course and t.site_course.get('tags') and self.slug in t.site_course.tags[1:])
    )

  def gen_documentation(self) -> str:
    ret = f"\n\n## `{self.slug}`"
    blurb = None
    if self.site_tag:
      blurb = re.sub(r"\[([^\]]+)\]\(\/tags\/([a-z0-9-]+)\)", r'\1 (see `\2`)', self.site_tag.content).strip()
      ret += f" = {self.site_tag.title}"
      if self.site_course:
        blurb = self.site_course.description + '\n\n' + blurb
        coursename = self.site_course.title
        if self.site_course.get('subtitle'):
          coursename += f": {self.site_course.subtitle}"
        if coursename != self.site_tag.title:
          ret += "\n\n**Full Title**: \"" + coursename + '\"'
      if self.public_folder and self.public_folder['name'] != self.site_tag.title:
        if not (self.public_folder['name'].startswith('The ') and self.public_folder['name'][4:] == self.site_tag.title):
          ret += "\n\n**Alternative Title**: " + self.public_folder['name']
    elif self.site_course:
      ret += f" = {self.site_course.title}"
      if self.site_course.get('subtitle'):
        ret += f": {self.site_course.subtitle}"
      blurb = self.site_course.description
    elif self.public_folder:
      ret += f" = {self.public_folder['name']}"
    elif self.private_folder:
      ret += f" = {self.private_folder['name']}"
    if blurb:
      ret += f"\n\n### Description\n\n{blurb}"
    ret += "\n\n### Relationships\n"
    if self.parent:
      ret += "\n**Parent**: "
      ret += self.parent.inline_name
    siblings = self.get_siblings()
    if siblings:
      ret += "\n**Siblings**:" + RELATIONSHIP_LIST_STYLE
      ret += RELATIONSHIP_LIST_STYLE.join([s.inline_name for s in siblings])
    children = self.get_children()
    if children:
      ret += "\n**Children**:" + RELATIONSHIP_LIST_STYLE
      ret += RELATIONSHIP_LIST_STYLE.join([s.inline_name for s in children])
    broader = self.get_broader()
    if broader:
      ret += "\n**Related Broader**:" + RELATIONSHIP_LIST_STYLE
      ret += RELATIONSHIP_LIST_STYLE.join([s.inline_name for s in broader])
    narrower = self.get_narrower()
    if narrower:
      ret += "\n**Related Narrower**:" + RELATIONSHIP_LIST_STYLE
      ret += RELATIONSHIP_LIST_STYLE.join([s.inline_name for s in narrower])
    ret += "\n\n"
    predictor = TagPredictor.load()
    if self.slug in predictor.classes:
      ret += "### Discriminative Vocabulary\n\n"
      dis_vocab = predictor.get_discriminating_vocab_for_tag(self.slug, n=20)
      parent_dis = dis_vocab.get('parent')
      child_dis = dis_vocab.get('children')
      def format_word_cloud(cloud, name):
        return f"**`{self.slug}` vs its {name} ({english_join([f"`{i}`" for i in cloud['versus']])})**:\n" \
          + f"[{', '.join(trim_punc.sub('', t) for t in cloud['terms'])}]\n\n"
      if parent_dis:
        ret += format_word_cloud(parent_dis, "parent/siblings")
      if child_dis:
        ret += format_word_cloud(child_dis, "children")
    # TODO add examples section
    return ret

class TagTree:
  def __init__(self):
    self.slug_to_metadata: dict[str, TagMetadata] = dict()
    self.sorted_slugs: list[str] = []

  def load(self):
    for tagfile in website.tags:
      tag = TagMetadata(self, tagfile.slug, site_tag=tagfile)
      self.add_tag(tag)
    for coursefile in website.courses:
      tag = self.get_tag(coursefile.slug)
      if tag:
        tag.site_course = coursefile
      else:
        tag = TagMetadata(self, coursefile.slug, site_course=coursefile)
        self.add_tag(tag)
    self._folder_id_to_slug_map = gdrive.load_folder_slugs()
    self.load_subfolders_of('buddhism')
    self.load_subfolders_of('world')
  
  def load_subfolders_of(self, slug: str):
    private_folder_url = gdrive.FOLDERS_DATA()[slug]['private']
    assert isinstance(private_folder_url, str)
    private_folder_id = gdrive.folderlink_to_id(private_folder_url)
    assert private_folder_id
    subfolders = gdrive.gcache.get_subfolders(private_folder_id, include_shortcuts=False)
    for subfolder in subfolders:
      if subfolder['id'] not in self._folder_id_to_slug_map:
        continue
      subslug = self._folder_id_to_slug_map[subfolder['id']]
      if not self.get_tag(subslug):
        self.add_tag(TagMetadata(self, subslug))
      self.load_subfolders_of(subslug)

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
  
  def __len__(self) -> int:
    return len(self.sorted_slugs)

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
  max_len = 0
  longest_slug = ''
  with yaspin(text="Compiling the tag tree..."):
    tag_tree.load()
  for tag in tag_tree:
    tag_doc = tag.gen_documentation()
    ret += tag_doc
    if len(tag_doc) > max_len:
      max_len = len(tag_doc)
      longest_slug = tag.slug
  print(f"Generated {len(tag_tree)} tag docs!")
  print(f"The longest doc was for {longest_slug}, at {max_len} characters.")
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
