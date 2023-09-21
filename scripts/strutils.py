#!/bin/python3

import random
import sys
import termios
import tty
import os
import json
import re
import string
import readline
from pathlib import Path
from functools import cache, reduce
from collections import defaultdict
from math import floor, ceil
try:
  from titlecase import titlecase
except:
  print("pip install titlecase")
  quit(1)

ANSI_COLOR_DIM = "\033[2m"
ANSI_COLOR_RESET = "\033[0m"
ANSI_SAVE_POSITION = "\033[s"
ANSI_RESTORE_POSITION = "\033[u"
ANSI_ERASE_HERE_TO_END = "\033[0J"
ANSI_ERASE_HERE_TO_LINE_END = "\033[0K"
def ANSI_RETURN_N_UP(n):
  return f"\033[{n}F"
def ANSI_RETURN_N_DOWN(n):
  return f"\033[{n}E"
def ANSI_MOVE_LEFT(n):
  return f"\033[{n}D"
def ANSI_MOVE_RIGHT(n):
  return f"\033[{n}C"
def ANSI_MOVE_DOWN(n):
  return f"\033[{n}B"
def ANSI_MOVE_UP(n):
  return f"\033[{n}A"
# For more, see https://gist.github.com/fnky/458719343aabd01cfb17a3a4f7296797

whitespace = re.compile('\s+')
digits = re.compile('(\d+)')
italics = re.compile('</?(([iI])|(em))[^<>nm]*>')
MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
abnormalchars = re.compile('[^\w\s]')
sutta_id_re = re.compile(r'^([a-zA-Z]+)(\d+)[\.]?([-–\d]*)$')

HOSTNAME_BLACKLIST = {
  "www.questia.com",
}

git_root_folder = Path(os.path.normpath(os.path.join(os.path.dirname(__file__), "../")))

def sanitize_string(text):
  return abnormalchars.sub('', whitespace.sub(' ', text)).strip()

def atoi(text):
    return int(text) if text.isdigit() else text

def cumsum(vec):
    return reduce(lambda a,x: a+[a[-1]+x] if a else [x], vec, [])

def natural_key(text):
    '''
    alist.sort(key=natural_keys) sorts in human order
    '''
    return [ atoi(c) for c in digits.split(text) ]

def naturally_sorted(alist):
  return sorted(alist, key=natural_key)

def cout(*args):
  print(*args, flush=True, end="")

def get_cursor_position():
    """Returns (row, col)""" # á la termios.tcgetwinsize
    # code courtesy of https://stackoverflow.com/a/69582478/1229747
    stdinMode = termios.tcgetattr(sys.stdin)
    _ = termios.tcgetattr(sys.stdin)
    _[3] = _[3] & ~(termios.ECHO | termios.ICANON)
    termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, _)
    try:
        sys.stdout.write("\x1b[6n")
        sys.stdout.flush()
        _ = ""
        while not (_ := _ + sys.stdin.read(1)).endswith('R'):
            pass
        res = re.match(r".*\[(?P<y>\d*);(?P<x>\d*)R", _)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, stdinMode)
    if(res):
        return (atoi(res.group("y")), atoi(res.group("x")))
    return (-1, -1)

def stdout_make_room(lines: int):
  """Saves the current cursor position and ensures n lines are free below it
  
  returns the number of lines the terminal actually shifted up by"""
  cout(ANSI_SAVE_POSITION)
  if lines <= 0:
    return 0
  br, bc = get_cursor_position()
  nr, nc = termios.tcgetwinsize(sys.stdout)
  diff = lines + br - nr
  cout(''.join(["\n"]*lines))
  cout(ANSI_RESTORE_POSITION)
  if diff > 0:
    cout(ANSI_MOVE_UP(diff))
    cout(ANSI_SAVE_POSITION)
    return diff
  return 0

def radio_dial(options):
  SEARCH_ROOM = 3
  i = 0
  length = len(options)
  stdout_make_room(SEARCH_ROOM)
  stdin = sys.stdin.fileno()
  old_settings = termios.tcgetattr(stdin)
  tty.setraw(stdin)
  try:
    while True:
      cout(f"{ANSI_RESTORE_POSITION}{ANSI_ERASE_HERE_TO_END}{ANSI_RESTORE_POSITION}")
      if i > 0:
        cout(f"{ANSI_COLOR_DIM}   {i}/{length}: {options[i-1]}{ANSI_COLOR_RESET}")
      cout(ANSI_RETURN_N_DOWN(1))
      cout(f" > {i+1}/{length}: {options[i]}")
      if length > i + 1:
        cout(ANSI_RETURN_N_DOWN(1))
        cout(f"{ANSI_COLOR_DIM}   {i+2}/{length}: {options[i+1]}{ANSI_COLOR_RESET}")
      ch = sys.stdin.read(1)
      if ch == '\x03':
        raise KeyboardInterrupt()
      elif ch in ['\r', '\x04', '\n']:
        break
      elif ch == '\x1b': # ESC
        ch = sys.stdin.read(1)
        if ch == '[': # we're getting a control char (e.g. arrow keys)
          ch = sys.stdin.read(1)
          # A=up, B=down, C=right, D=left, H=home, F=end
          if i > 0 and (ch == 'A' or ch == 'D'):
            i -= 1
          if (ch == 'B' or ch == 'C') and (length > i + 1):
            i += 1
          if ch == "F":
            i = length - 1
          if ch == 'H':
            i = 0
      else:
        pass
  finally:
    cout(f"{ANSI_RESTORE_POSITION}{ANSI_RETURN_N_DOWN(SEARCH_ROOM)}\n")
    termios.tcsetattr(stdin, termios.TCSADRAIN, old_settings)
  return i

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

def input_with_tab_complete(prompt, typeahead_suggestions):
    readline.set_completer(lambda text, state: (
      [s for s in typeahead_suggestions if s.startswith(text)][state]
))
    readline.parse_and_bind('tab: complete')
    ret = input(prompt)
    readline.set_completer(None)
    return ret

def trunc(longstr, maxlen=12) -> str:
  return longstr if len(longstr) <= maxlen else (longstr[:maxlen-1]+'…')

def does_md_only_contain_quotes(text):
  paragraphs = list(filter(lambda p: not not p, map(lambda p: p.strip(), text.split("\n\n"))))
  for p in paragraphs:
    if not p.startswith('>'):
      return False
  return True

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
  def delete_file(self):
    os.remove(self.fname)
    self.items = set()
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


@cache
def get_author_slugs():
  ret = defaultdict(lambda: None)
  authordir = git_root_folder.joinpath("_authors")
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
