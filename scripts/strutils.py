#!/bin/python3

import random
import sys
import signal
import termios
import hashlib
import tty
import os
import json
import io
import fcntl
import subprocess
import struct
import re
import urllib.parse
import string
import readline
from pathlib import Path
from functools import cache, reduce
from collections import defaultdict
from math import floor, ceil
try:
  from titlecase import titlecase
except:
  print("pip install titlecase pyyaml")
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

whitespace = re.compile(r'\s+')
digits = re.compile(r'(\d+)')
italics = re.compile(r'</?(([iI])|(em))[^<>nm]*>')
MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
abnormalchars = re.compile(r'[^\w\s]')
sutta_id_re = re.compile(r'^([a-zA-Z]+)(\d+)[\.]?([-–\d]*)$')
yt_url_to_id_re = re.compile(r'(?:youtube(?:-nocookie)?\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?|live)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})')
yt_url_to_plid_re = re.compile(r'[&?]list=([^&]+)')
yaml_key = re.compile(r"^[a-z_]+:.*")

HOSTNAME_BLACKLIST = {
  "www.questia.com",
  "scholarbank.nus.edu.sg",
}

git_root_folder = Path(os.path.normpath(os.path.join(os.path.dirname(__file__), "../")))

def git_grep(pattern: str) -> list[Path]:
  try:
    result = subprocess.run(
      ['git', 'grep', '-l', pattern],
      cwd=git_root_folder,
      capture_output=True,
      text=True,
      check=True
    )
    return [git_root_folder / file for file in result.stdout.splitlines()]
  except subprocess.CalledProcessError:
    return []

def replace_text_across_repo(old_uuid: str, new_uuid: str):
  for file_path in git_grep(old_uuid):
    content = file_path.read_text()
    new_content = content.replace(old_uuid, new_uuid)
    file_path.write_text(new_content)
    print(f"Updated {file_path.relative_to(git_root_folder)} ({old_uuid} -> {new_uuid})")

def approx_eq(a, b, absdiff=1.0, percent=1.0):
  diff = a - b
  m = a
  if diff < 0:
    diff = 0 - diff
    m = b
  if diff < absdiff:
    return True
  if m < 0:
    m = diff - m
  if (100.0 * diff / m) < percent:
    return True
  return False

def sanitize_string(text):
  return abnormalchars.sub('', whitespace.sub(' ', text)).strip()

def atoi(text):
    return int(text) if text.isdigit() else text

def md5(text: bytes | str | Path):
  """Note: assumes text is the thing to hash. Pass a Path object for files."""
  bts = None
  if isinstance(text, bytes):
    bts = text
  if isinstance(text, str):
    bts = text.encode()
  if isinstance(text, Path):
    bts = text.read_bytes()
  if bts is None:
    raise ValueError(f"Expected bytes or str or Path, got {type(text)}")
  return hashlib.md5(bts).hexdigest()

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

def iolen(fd):
  pos = fd.tell() # get current position
  fd.seek(0, io.SEEK_END) # move to the end
  length = fd.tell() # get final position
  fd.seek(pos) # restore original position
  return length

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

def get_terminal_size():
  try:
    return termios.tcgetwinsize(sys.stdout)
  except AttributeError: # before python 3.11
    for fd in (0, 1, 2):
      try:
        h, w, hp, wp = struct.unpack('HHHH', fcntl.ioctl(fd, termios.TIOCGWINSZ, struct.pack('HHHH', 0, 0, 0, 0)))
        return w, h
      except OSError:
        pass
    # if all else fails, fall back to env variables or some sane, default values
    return int(os.environ.get('COLUMNS', 80)), int(os.environ.get('LINES', 24))

def stdout_make_room(lines: int):
  """Saves the current cursor position and ensures n lines are free below it

  returns the number of lines the terminal actually shifted up by"""
  cout(ANSI_SAVE_POSITION)
  if lines <= 0:
    return 0
  br, bc = get_cursor_position()
  nr, nc = get_terminal_size()
  diff = lines + br - nr
  cout(''.join(["\n"]*lines))
  cout(ANSI_RESTORE_POSITION)
  if diff > 0:
    cout(ANSI_MOVE_UP(diff))
    cout(ANSI_SAVE_POSITION)
    return diff
  return 0

def checklist_prompt(options: list[str], default=False):
  selections = []
  if isinstance(default, list):
    selections = default[:len(options)] + [False] * max(0, len(options) - len(default))
  else:
    selections = [default for i in options]
  tsize = os.get_terminal_size()
  length = len(options)
  i = 0
  room = min(tsize.lines - 2, length) + 1
  r = (0, room-1)
  space = tsize.columns - 6
  options = [trunc(t, space) for t in options]
  stdin = sys.stdin.fileno()
  stdout_make_room(room)
  old_settings = termios.tcgetattr(stdin)
  tty.setraw(stdin)
  try:
    while True:
      cout(f"{ANSI_RESTORE_POSITION}{ANSI_ERASE_HERE_TO_END}{ANSI_RESTORE_POSITION}")
      for j in range(r[0], r[1]):
        if j == i:
          cout(">")
        else:
          cout(" ")
        cout("[")
        if selections[j]:
          cout("X")
        else:
          cout(" ")
        cout(f"] {options[j]}")
        cout(ANSI_RETURN_N_DOWN(1))
      if i == length:
        cout("> ")
      else:
        cout("  ")
      cout("Accept")
      ch = sys.stdin.read(1)
      if ch == '\x03':
        raise KeyboardInterrupt()
      elif ch in ['\r', '\x04', '\n', ' ', 'x', 'X', '-']:
        if i == length:
          break
        else:
          selections[i] = not selections[i]
      elif ch == '\x1b': # ESC
        ch = sys.stdin.read(1)
        if ch == '[': # we're getting a control char (e.g. arrow keys)
          ch = sys.stdin.read(1)
          # A=up, B=down, C=right, D=left, H=home, F=end
          if i > 0 and (ch == 'A' or ch == 'D'):
            i -= 1
            if i < r[0]:
              r = (r[0]-1, r[1]-1)
          if (ch == 'B' or ch == 'C') and (length > i):
            i += 1
            if i > r[1]:
              r = (r[0]+1, r[1]+1)
          if ch == "F":
            i = length
            r = (length-room+1, length)
          if ch == 'H':
            i = 0
            r = (0, room-1)
  finally:
    cout(f"{ANSI_RESTORE_POSITION}{ANSI_RETURN_N_DOWN(room)}\n")
    termios.tcsetattr(stdin, termios.TCSADRAIN, old_settings)
  return selections

def radio_dial(options):
  SEARCH_ROOM = 3
  i = 0
  length = len(options)
  stdout_make_room(SEARCH_ROOM)
  space = os.get_terminal_size().columns - 10
  options = [trunc(t, space) for t in options]
  stdin = sys.stdin.fileno()
  old_settings = termios.tcgetattr(stdin)
  tty.setraw(stdin)
  def _redisplay():
      cout(f"{ANSI_RESTORE_POSITION}{ANSI_ERASE_HERE_TO_END}{ANSI_RESTORE_POSITION}")
      if i > 0:
        cout(f"{ANSI_COLOR_DIM}   {i}/{length}: {options[i-1]}{ANSI_COLOR_RESET}")
      cout(ANSI_RETURN_N_DOWN(1))
      cout(f" > {i+1}/{length}: {options[i]}")
      if length > i + 1:
        cout(ANSI_RETURN_N_DOWN(1))
        cout(f"{ANSI_COLOR_DIM}   {i+2}/{length}: {options[i+1]}{ANSI_COLOR_RESET}")
  try:
    while True:
      _redisplay()
      ch = sys.stdin.read(1)
      if ch == '\x03':
        raise KeyboardInterrupt()
      elif ch in ['\r', '\x04', '\n']:
        break
      elif ch >= '1' and ch <= '9' and length < 9 and ord(ch) - ord('1') < length:
        i = ord(ch) - ord('1')
        _redisplay()
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

def input_list(prompt):
  print(prompt)
  ret = []
  while True:
    item = input(" - ")
    if not item:
      break
    ret.append(item)
  return ret

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

def input_with_tab_complete(prompt, typeahead_suggestions, delims=None, prefill=None):
    prev_complr = readline.get_completer()
    prev_delims = readline.get_completer_delims()
    readline.set_completer(lambda text, state: (
      [s for s in typeahead_suggestions if s.startswith(text)][state]
))
    readline.set_completer_delims(delims or ' /')
    readline.parse_and_bind('tab: complete')
    if prefill:
      ret = input_with_prefill(prompt, prefill)
    else:
      ret = input(prompt)
    readline.set_completer(prev_complr)
    readline.set_completer_delims(prev_delims)
    return ret

class DelayedKeyboardInterrupt:
    # https://stackoverflow.com/a/21919644
    # Use as:
    # with DelayedKeyboardInterrupt():
    #   critical_uninterupted_code()
    def __enter__(self):
        self.signal_received = False
        self.old_handler = signal.signal(signal.SIGINT, self.handler)
                
    def handler(self, sig, frame):
        self.signal_received = (sig, frame)
        print("SIGINT Received: Just gunna wrap something up first...")
    
    def __exit__(self, type, value, traceback):
        signal.signal(signal.SIGINT, self.old_handler)
        if self.signal_received:
            self.old_handler(*self.signal_received)

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

def prompt(question: str, default:str = None) -> bool:
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
  filepath = str(filepath)\
    .replace(" ", "\\ ")\
    .replace("$", "\\$")\
    .replace("&", "\\&")\
    .replace('"', "\\\"")\
    .replace("`", "\\`")\
    .replace("(", "\\(")\
    .replace(")", "\\)")\
    .replace("'", "\\\'")\
    .replace(";", "\\;")
  os.system(f"xdg-open {filepath}")

class FileSyncedSet:
  def __init__(self, fname, normalizer=None):
    self.fname = fname
    self.items = set()
    # normalizer must return a string with no newlines
    self.norm = normalizer or (lambda a: str(a).replace("\n", " "))
    if os.path.exists(fname):
      with open(fname) as fd:
        for l in fd:
          l = l[:-1]
          self.items.add(l) if l else None
  def add(self, item):
    item = self.norm(item)
    if item not in self.items:
      self.items.add(item)
      with open(self.fname, "a") as fd:
        fd.write(f"{item}\n")
  def remove(self, item):
    item = self.norm(item)
    if item not in self.items:
      return
    self.items.remove(item)
    self._rewrite_file()
  def _rewrite_file(self):
    with open(self.fname, "w") as fd:
      for item in self.items:
        fd.write(f"{item}\n") if item else None
  def delete_file(self):
    os.remove(self.fname)
    self.items = set()
  def peak(self):
    ret = self.items.pop()
    self.items.add(ret)
    return ret
  def pop(self):
    ret = self.items.pop()
    self._rewrite_file()
    return ret
  def __len__(self):
    return len(self.items)
  def __contains__(self, item):
    return self.norm(item) in self.items

class FileSyncedMap:
  def __init__(self, file_path, keynormalizer=None):
    self.fname = file_path
    self.items = dict()
    self.norm = keynormalizer or (lambda a: str(a))
    if os.path.exists(file_path):
      with open(file_path) as fd:
        self.items = json.load(fd)
  def _rewrite_file(self):
    with open(self.fname, "w") as fd:
      json.dump(self.items, fd)
  def delete_file(self):
    os.remove(self.fname)
    self.items = dict()
  def __len__(self):
    return len(self.items)
  def __contains__(self, item):
    return self.norm(item) in self.items
  def get(self, item, default=None):
    return self.items.get(self.norm(item), default)
  def __getitem__(self, item):
    return self.items[self.norm(item)]
  def set(self, item, value):
    self.items[self.norm(item)] = value
    self._rewrite_file()
  def __setitem__(self, item, value):
    self.set(item, value)
  def __delitem__(self, item):
    del self.items[self.norm(item)]
    self._rewrite_file()
  def update(self, values):
    self.items.update(values)
    self._rewrite_file()
  def keyfor(self, value):
    try:
      return list(self.items.keys())[list(self.items.values()).index(value)]
    except ValueError:
      return None

def file_info(file_name):
  md5 = hashlib.md5()
  size = 0
  with open(file_name, "rb") as f:
    while chunk := f.read(1024):
        md5.update(chunk)
        size += len(chunk)
  return (md5.hexdigest(), size)

def get_untracked_files(git_root: Path | str = "."):
    """Get list of untracked files from git status"""
    try:
        # Run git status to get untracked files
        result = subprocess.run(
            ['git', '-C', str(git_root), 'ls-files', '--others', '--exclude-standard'],
            capture_output=True,
            text=True,
            check=True
        )
        files = result.stdout.splitlines()
        if isinstance(git_root, Path):
          return [git_root / file for file in files]
        return [os.path.join(git_root, file) for file in files]
    except subprocess.CalledProcessError:
        print("Error: Not a git repository or git command failed")
        return []
    except FileNotFoundError:
        print("Error: Git is not installed or not in PATH")
        return []

def get_file_sizes(files):
    """Calculate sizes of given files"""
    total_size = 0
    file_sizes = {}
    
    for file in files:
        try:
            size = os.path.getsize(file)
            file_sizes[file] = size
            total_size += size
        except (FileNotFoundError, OSError) as e:
            print(f"Error getting size of {file}: {e}")
    return file_sizes, total_size

def format_size(size_in_bytes):
    """Convert size in bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.2f} PB"

def write_frontmatter_key(path: Path, key: str, value, insert_after_key=None):
  """Takes a markdown file and top-level frontmatter key and sets it to value
  
  insert_after_key will add the new key after that key if it doesn't exist
  """
  lines = path.read_text().split("\n")
  key = f"{key}:"
  if not yaml_key.match(key):
    raise ValueError("Key isn't a valid yaml key")
  if insert_after_key:
    insert_after_key = f"{insert_after_key}:"
    if not yaml_key.match(insert_after_key):
      raise ValueError("Insert after key isn't a valid yaml key")
  else:
    insert_after_key = "---"
  assert lines[0] == "---"
  ourkeystartsline = None
  nextkeystartsline = None
  insertafterkeystartsline = None
  insertafterkeyendsline = None
  for i in range(1, len(lines)):
    if yaml_key.match(lines[i]) or lines[i] == "---":
      if nextkeystartsline is None and ourkeystartsline is not None:
        nextkeystartsline = i
      if (insertafterkeystartsline is not None or lines[i] == "---") and insertafterkeyendsline is None:
        insertafterkeyendsline = i
    if lines[i] == "---":
      break
    if lines[i].startswith(insert_after_key):
      insertafterkeystartsline = i
    if lines[i].startswith(key):
      ourkeystartsline = i
  if isinstance(value, list):
    if not isinstance(value[0], str):
      raise ValueError("Teach me how to handle lists of non-strings")
    new_lines = []
    for c in value:
      v = c.replace("\"", "\\\"")
      if "\n" in v:
        raise ValueError("Teach me how to handle lists with newline strings")
      new_lines.append(f"  - \"{v}\"")
    if ourkeystartsline is None:
      path.write_text("\n".join(
        lines[:insertafterkeyendsline] + [key] + new_lines + lines[insertafterkeyendsline:]
      ))
    else:
      path.write_text("\n".join(
        lines[:ourkeystartsline+1] + new_lines + lines[nextkeystartsline:]
      ))
  elif not value:
    if not ourkeystartsline:
      return
    path.write_text("\n".join(lines[:ourkeystartsline] + lines[nextkeystartsline:]))
    return
  else:
    raise ValueError(f"Unknown value type {type(value)}")

# Takes a partially encoded URL (such as /Nibbāna%20and%20Abhidhamma)
# and returns the fully encoded URL (i.e. with /Nibb%C4%81na%20and%20Abhidhamma)
def fully_encode_url(url):
    # Split the URL into components
    scheme, netloc, path, params, query, fragment = urllib.parse.urlparse(url)
    
    # Encode the path
    path = urllib.parse.quote(urllib.parse.unquote(path), safe='/')
    
    # Manually reconstruct the URL to avoid urllib.parse.urlunparse undoing the encoding
    result = scheme + '://' + netloc
    if path:
        result += path
    if params:
        result += ';' + params
    if query:
        result += '?' + query
    if fragment:
        result += '#' + fragment
    return result

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
