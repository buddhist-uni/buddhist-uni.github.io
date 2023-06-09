#!/bin/python3

import random
import os
import json
import re
import string
import readline
from functools import cache
from collections import defaultdict
from math import floor, ceil
try:
  from titlecase import titlecase
except:
  print("pip install titlecase")
  quit(1)

whitespace = re.compile('\s+')
italics = re.compile('</?(([iI])|(em))[^<>nm]*>')
MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

HOSTNAME_BLACKLIST = {
  "www.questia.com",
}

def cout(*args):
  print(*args, flush=True, end="")

def stdout_make_room(lines: int):
  cout(''.join(["\n"]*lines))
  cout(f"\033[{lines}A")

def input_with_prefill(prompt, text, validator=None):
    def hook():
        readline.insert_text(text)
        readline.redisplay()
    readline.set_pre_input_hook(hook)
    while True:
      result = input(prompt)
      if not validator:
        break
      try:
        if validator(result):
          break
        else:
          continue
      except:
        continue
    readline.set_pre_input_hook()
    return result

def trunc(longstr, maxlen=12) -> str:
  return longstr if len(longstr) <= maxlen else (longstr[:maxlen-1]+'…')

def random_letters(length):
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

def uppercase_ratio(s: str) -> float:
    if not s:
      return 0
    alph = list(filter(str.isalpha, s))
    return sum(map(str.isupper, alph)) / len(alph)

# leaves a string unmolested if the ratio looks reasonable
# could be smarter but this is good enough™️
def title_case(s: str) -> str:
  if not s:
    return ''
  p = uppercase_ratio(s)
  # 11% with high confidence!
  if p < 0.11 or p > 0.20:
    return titlecase(s)
  # If the ratio looks good, trust
  return s

def prompt(question: str, default = None) -> bool:
    reply = None
    hint = "(y/n)"
    if default == "y":
      hint = "[y]/n"
    if default == "n":
      hint = "y/[n]"
    while reply not in ("y", "n"):
        reply = input(f"{question} {hint}: ").casefold()
        if not reply:
          reply = default
    return (reply == "y")

def system_open(filepath):
  os.system(f"open '{filepath}' || termux-open '{filepath}' || vim '{filepath}'")

class FileSyncedSet:
  def __init__(self, fname, normalizer=None):
    self.fname = fname
    self.items = set()
    # normalizer must return a string with no newlines
    self.norm = normalizer or (lambda a: str(a).replace("/n", " "))
    if os.path.exists(fname):
      with open(fname) as fd:
        for l in fd:
          self.items.add(l[:-1])
  def add(self, item):
    item = self.norm(item)
    if item not in self.items:
      self.items.add(item)
      with open(self.fname, "a") as fd:
        fd.write(f"{item}\n")
  def __contains__(self, item):
    return self.norm(item) in self.items

# Reconstructs a text from an inverted index:
# https://docs.openalex.org/api-entities/works/work-object#abstract_inverted_index
def invert_inverted_index(index: dict) -> list:
  if not index:
    return []
  max_i = max(map(lambda ps: max(ps), index.values()))
  ret = [""]*(max_i+1)
  for k in index:
    word = whitespace.sub(' ', k.strip())
    for i in index[k]:
      ret[i] = word
  return ret

def text_from_index(index: dict) -> str:
  return " ".join(invert_inverted_index(index))

# Makes the authors string for the work
# https://docs.openalex.org/api-entities/works/work-object#authorships
def authorstr(work: dict, maxn: int) -> str:
    authors = list(map(lambda a: a['author']['display_name'].replace(',', ''), work['authorships']))
    if len(authors) > maxn:
      authors = authors[:(maxn-1)]
      authors.append('et al')
    return ", ".join(authors)

def print_work(work: dict, indent=0):
    s = "".join([" "]*indent)
    try:
      print(f"{s}Source: {work['primary_location']['source']['display_name']}")
    except (TypeError, KeyError, ValueError):
      print(f"{s}Source: ?")
    print(f"{s}Year: {work['publication_year']}")
    try:
      print(f"{s}Pages: {1+int(work['biblio']['last_page'])-int(work['biblio']['first_page'])}")
    except (TypeError, KeyError, ValueError):
      print(f"{s}Pages: ?")
    print(f"{s}Cited By: {work['cited_by_count']}")
    if work['abstract_inverted_index']:
      print(f"{s}Abstract: {text_from_index(work['abstract_inverted_index'])}")
    print(f"{s}Title: {work['title']}")
    print(f"{s}Author(s): {authorstr(work, 6)}")
    try:
      if work['doi'] != work['open_access']['oa_url']:
        print(f"{s}DOI: {work['doi']}")
    except KeyError:
      pass
    print(f"{s}URL: {work['open_access']['oa_url']}")


def serp_result(work: dict, margin=10) -> str:
  width = os.get_terminal_size().columns
  space = width - margin - 4
  return whitespace.sub(' ', f"{trunc(work['display_name'], floor(0.7*space))} by {trunc(work['hint'], ceil(0.3*space))}")

@cache
def get_author_slugs():
  ret = defaultdict(lambda: None)
  authordir = os.path.normpath(os.path.join(os.path.dirname(__file__), "../_authors"))
  for fn in os.listdir(authordir):
    fullpath = os.path.join(authordir, fn)
    with open(fullpath) as fd:
      if fd.readline() != "---\n":
        raise ValueError(f"{fn} doesn't start with ---")
      aname = fd.readline().split('"')
      if aname[0] != 'title: ':
        raise ValueError(f"{fn} doesn't start with a quoted title")
      ret[aname[1]] = fn.split(".")[0]
  return ret

def get_author_slug(name: str):
  return get_author_slugs()[name]
