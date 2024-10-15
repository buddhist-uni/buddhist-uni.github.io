
from typing import Any
import subprocess
from datetime import datetime
from strutils import (
  Path,
  git_root_folder as root_folder
)

try:
  import frontmatter
  import yaml
except:
  print("  pip install pyyaml python-frontmatter")
  quit(1)

config = yaml.load(root_folder.joinpath('_config.yml').read_text(), Loader=yaml.Loader)
baseurl = config.get('url')
filecreationtimes = dict()

class JekyllFile(frontmatter.Post):
  def __init__(self, fd: Path, content, handler=None, **kwargs) -> None:
    fd = Path(fd)
    if 'slug' not in kwargs:
      kwargs['slug'] = fd.stem
    super().__init__(content, handler=handler, **kwargs)
    self.absolute_path = fd
    self.relative_path = fd.relative_to(root_folder)
    self.created_at = filecreationtimes[str(self.relative_path)]
  
  @classmethod
  def load(cls, f: Path, **kwargs):
    post = frontmatter.load(f, **kwargs)
    return cls(f, post.content, post.handler, **post.metadata)
  
  def __getattribute__(self, __name: str) -> Any:
    try:
      return super().__getattribute__(__name)
    except AttributeError:
      return self.metadata.get(__name)

class AuthorFile(JekyllFile):
  def __init__(self, fd: Path, content, handler=None, **kwargs) -> None:
    super().__init__(fd, content, handler, **kwargs)
    self.url = "/authors/" + fd.stem

class AuthorCollection():
  def __init__(self) -> None:
    self.authors = dict()
  def add(self, author: AuthorFile):
    self.authors[author.slug] = author
  def get(self, author: str) -> AuthorFile:
    return self.authors.get(author)
  def __iter__(self):
    return iter(self.authors.values())
  def __len__(self):
    return len(self.authors)

class TagFile(JekyllFile):
  def __init__(self, fd: Path, content, handler=None, **kwargs) -> None:
    super().__init__(fd, content, handler, **kwargs)
    self.url = "/tags/" + fd.stem

class DataCollection():
  def load(self):
    content_config = root_folder.joinpath('_data/content.yml').read_text()
    self.content = yaml.load(content_config, Loader=yaml.Loader)

data = DataCollection()

class TagCollection():
  def __init__(self):
    self.tags = dict()

  def add(self, tag: TagFile):
    tslug = tag.slug
    tag.children = []
    for othertag in self.tags.values():
      if tslug in othertag.parents:
        tag.children.append(othertag.slug)
    for otherslug in tag.parents:
      if otherslug in self.tags:
        self.tags[otherslug].children.append(tslug)
    self.tags[tslug] = tag

  def finalize(self):
    self.sortChildren()

  def sortChildren(self):
    for tag in self:
      tag.children.sort(key=lambda k: self.get(k).sortkey or 0)

  def get(self, tag: str):
    return self.tags.get(tag)
  def __iter__(self):
    return iter(self.tags.values())
  def __len__(self):
    return len(self.tags)
  def __contains__(self, item):
    if isinstance(item, TagFile):
      return item.slug in self.tags
    return bool(self.get(item))

class ContentFile(JekyllFile):
  def __init__(self, fd: Path, content, handler=None, **kwargs) -> None:
    fd = Path(fd)
    super().__init__(fd, content, handler, **kwargs)
    self.category = self.relative_path.parts[1]
    self.content_path = f"{self.category}/{fd.stem}"
    self.url = f"/content/{self.content_path}"
    if not self.get('tags'):
        self.tags = []
    if not self.get('formats'):
      if self.category == 'av':
        self.formats = ['mp3']
      else:
        self.formats = ['pdf', 'epub']

content = []
tags = TagCollection()
authors = AuthorCollection()

def entry_with_drive_id(gid):
  for entry in content:
    for link in entry.get('drive_links', []):
      if gid in link:
        return entry
  return None

def get_file_creation_times():
  """Returns a dict from relative filepath strings to datetime stamps"""
  filecreationtimes = dict()
  SYGIL = '%these-files-modified-at:'
  git_history = subprocess.run(
    ["git", "--git-dir", root_folder.joinpath(".git"),
     "log", "--name-only", "--date=unix",
     f"--pretty=%{SYGIL}%ct"
    ],
    capture_output=True, text=True, check=True).stdout.splitlines()
  timestamp = datetime.now()
  for line in git_history:
    if SYGIL in line:
      timestamp = datetime.fromtimestamp(int(line[len(SYGIL):]))
      continue
    if line == "":
      continue
    filecreationtimes[line] = timestamp
  return filecreationtimes


def load():
  if content:
    return
  filecreationtimes.update(get_file_creation_times())
  for contentfolder in root_folder.joinpath('_content').iterdir():
    if (not contentfolder.is_dir()) or contentfolder.name.startswith('.'):
      continue
    for contentfile in contentfolder.iterdir():
      if contentfile.is_dir() or contentfile.name.startswith('.'):
        continue
      content.append(ContentFile.load(contentfile))
  content.sort(key=lambda c: c.url)
  content.sort(key=lambda c: c.created_at)
  for tagfile in root_folder.joinpath('_tags').iterdir():
    if (not tagfile.is_file()) or tagfile.name.startswith('.'):
      continue
    tags.add(TagFile.load(tagfile))
  tags.finalize()
  for authorfile in root_folder.joinpath('_authors').iterdir():
    if (not authorfile.is_file()) or authorfile.name.startswith('.'):
      continue
    authors.add(AuthorFile.load(authorfile))
  data.load()
