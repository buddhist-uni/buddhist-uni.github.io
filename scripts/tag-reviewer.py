#!/bin/python3

import os

from yaspin import yaspin

import website
from strutils import (
  FileSyncedSet,
  system_open,
  input_list,
  radio_dial
)

togothrough = FileSyncedSet(os.path.expanduser("~/contentitemstoreview.txt"))

def setup_review():
    with yaspin(text="Loading website contents into memory..."):
      website.load()
    print("Welcome to the tag reviewer!")
    include_courses = set(input_list("What courses/tags do you want to review?"))
    include_tags = set(input_list("What only tags to review?")) | include_courses
    exclude_tags = set(input_list("What tags to exclude?"))
    exclude_courses = set(input_list("What courses to exclude?"))
    with yaspin(text="Setting up..."):
      for c in website.content:
        if c.course and c.course in exclude_courses:
          continue
        tags = set(c.tags or [])
        if not tags.isdisjoint(exclude_tags):
          continue
        if (c.course and c.course in include_courses) or (not tags.isdisjoint(include_tags)):
          togothrough.add(c.absolute_path)
    print(f"Found {len(togothrough)} items to review.")

if __name__ == "__main__":
    if len(togothrough) == 0:
        setup_review()
    i = 1
    total = len(togothrough)
    while len(togothrough) > 0:
        contentfile = togothrough.peak()
        item = website.ContentFile.load(contentfile)
        print(f"Reviewing ({i}/{total}) \"{item.title}\" by {item.authors}...")
        system_open(contentfile)
        input("Press enter to continue...")
        i += 1
        togothrough.remove(contentfile)
