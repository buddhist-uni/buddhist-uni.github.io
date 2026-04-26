#!/bin/python3

from typing import (
  Collection,
  Callable,
)
import signal
import os
import subprocess
from pathlib import Path
from strutils import (
  git_root_folder,
)
from tqdm.contrib.concurrent import thread_map as tqdm_thread_map
import queue

class DummyYaspin:
    """A no-op version of yaspin for when verbosity is disabled."""
    def __init__(self, *args, **kwargs):
      self.text = kwargs.get("text", "")
      self.spinner = kwargs.get("spinner", "dots")
      self.timer = kwargs.get("timer", False)
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def __getattr__(self, name):
        # Handle common yaspin methods by returning self (for chaining) 
        # or a dummy function that returns self.
        if name in ('ok', 'fail', 'write', 'hide', 'show', 'spinner', 'stop', 'start'):
            return lambda *args, **kwargs: self
        return self
    def __call__(self, *args, **kwargs):
        return self

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
    if file_path.suffix == ".sqlite":
      continue
    try:
      content = file_path.read_text()
      new_content = content.replace(old_uuid, new_uuid)
      file_path.write_text(new_content)
    except UnicodeDecodeError:
      raise ValueError(f"{file_path} is not a valid unicode file")
    print(f"Updated {file_path.relative_to(git_root_folder)} ({old_uuid} -> {new_uuid})")

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


_CAUGHT_EXCEPTIONS = queue.Queue()
def graceful_threadmap_sigint_handler(sig, frame):
  with _CAUGHT_EXCEPTIONS.mutex:
    previous_sigints = sum(isinstance(err, KeyboardInterrupt) for err in _CAUGHT_EXCEPTIONS.queue)
    if previous_sigints >= 2:
      raise KeyboardInterrupt()
  _CAUGHT_EXCEPTIONS.put(KeyboardInterrupt())
  if previous_sigints >= 1:
    print("\n\033[1mCtrl+C detected.\033[0m Press one more time to force an immediate exit...")
  else:
    print("\n\033[1mCtrl+C detected.\033[0m Finishing current downloads and will then exit...")

def graceful_threadmap(fn: Callable, *iterables: Collection, max_workers=8, chunksize=1, **tqdm_kwargs):
  def _wrapped_fn(*args):
    if not _CAUGHT_EXCEPTIONS.empty():
      return None # stop working when told
    try:
      fn(*args)
    except Exception as e:
      _CAUGHT_EXCEPTIONS.put(e)
      import traceback
      print(f"Unhandled exception while running {fn.__name__}{tuple(str(a) for a in args)}: {e}")
      traceback.print_exc()
      return None
  try:
    old_handler = signal.signal(signal.SIGINT, graceful_threadmap_sigint_handler)
  except ValueError:
    old_handler = None
  try:
    ret = tqdm_thread_map(
      _wrapped_fn,
      *iterables,
      max_workers=max_workers,
      chunksize=chunksize,
      **tqdm_kwargs,
    )
  finally:
    if old_handler:
      signal.signal(signal.SIGINT, old_handler)
    if not _CAUGHT_EXCEPTIONS.empty():
      raise _CAUGHT_EXCEPTIONS.get()

