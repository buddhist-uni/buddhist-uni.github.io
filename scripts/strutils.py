#!/bin/python3

import random
import os
import json
import re
import string
from math import floor, ceil

whitespace = re.compile('\s+')

def cout(*args):
  print(*args, flush=True, end="")

def stdout_make_room(lines: int):
  cout(''.join(["\n"]*lines))
  cout(f"\033[{lines}A")

def trunc(longstr, maxlen=12) -> str:
  return longstr if len(longstr) <= maxlen else (longstr[:maxlen-1]+'…')

def random_letters(length):
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

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

# Reconstructs a text from an inverted index:
# https://docs.openalex.org/api-entities/works/work-object#abstract_inverted_index
def invert_inverted_index(index: dict) -> list:
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
    print(f"{s}Title: {work['title']}")
    print(f"{s}Author(s): {authorstr(work, 6)}")
    try:
      print(f"{s}DOI: {work['doi']}")
    except KeyError:
      pass
    print(f"{s}Venue: {work['host_venue']['display_name']}")
    print(f"{s}Year: {work['publication_year']}")
    try:
      print(f"{s}Pages: {1+int(work['biblio']['last_page'])-int(work['biblio']['first_page'])}")
    except TypeError:
      print(f"{s}Pages: ?")
    print(f"{s}Cited By: {work['cited_by_count']}")
    if work['abstract_inverted_index']:
      print(f"{s}Abstract: {text_from_index(work['abstract_inverted_index'])}")
    print(f"{s}URL: {work['open_access']['oa_url']}")


def serp_result(work: dict, margin=10) -> str:
  width = os.get_terminal_size().columns
  space = width - margin - 4
  return whitespace.sub(' ', f"{trunc(work['display_name'], floor(0.7*space))} by {trunc(work['hint'], ceil(0.3*space))}")

