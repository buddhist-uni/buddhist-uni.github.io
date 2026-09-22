
from typing import Callable, Iterator
from typing import Any
import subprocess
import json
from datetime import datetime
from strutils import (
  Path,
  git_root_folder as root_folder
)
from mathutils import gen_waypoint_power_decay_func

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
    try:
      self.created_at = filecreationtimes[str(self.relative_path)]
    except KeyError:
      self.created_at = datetime.now()
    self.__init_finished = True
  
  @classmethod
  def load(cls, f: Path, **kwargs):
    post = frontmatter.load(f, **kwargs)
    return cls(f, post.content, post.handler, **post.metadata)
  
  def __getattribute__(self, __name: str) -> Any:
    # for convenience, and to mirror Jekyll syntax, allow users
    # to get metadata values directly as attributes on the object
    try:
      return super().__getattribute__(__name)
    except AttributeError:
      return self.metadata.get(__name)

  def __setattr__(self, __name: str, __value: Any) -> None:
    try:
      # if the attribute exists on the parent
      super().__getattribute__(__name)
      # then try to set that one
      super().__setattr__(__name, __value)
    except AttributeError:
      try:
        # if we're still initializing
        super().__getattribute__("__init_finished")
      except AttributeError:
        # set this as a real attribute
        super().__setattr__(__name, __value)
        return
      # all attributes after __init__ go into the metadata instead
      self.metadata[__name] = __value
  
  def __delattr__(self, __name: str) -> None:
    if __name in self.metadata:
      del self.metadata[__name]
    else:
      super().__delattr__(__name)

class AuthorFile(JekyllFile):
  def __init__(self, fd: Path, content, handler=None, **kwargs) -> None:
    super().__init__(fd, content, handler, **kwargs)
    self.url = "/authors/" + fd.stem

class AuthorCollection():
  def __init__(self) -> None:
    self.authors = dict()
  def add(self, author: AuthorFile):
    self.authors[author.slug] = author
  def get(self, author: str) -> AuthorFile | None:
    return self.authors.get(author)
  def __iter__(self):
    ret = list(self.authors.values())
    ret.sort(key=lambda a: a.slug)
    return iter(ret)
  def __len__(self):
    return len(self.authors)

class TagFile(JekyllFile):
  def __init__(self, fd: Path, content, handler=None, **kwargs) -> None:
    super().__init__(fd, content, handler, **kwargs)
    self.url = "/tags/" + fd.stem

class DataCollection():
  def __init__(self) -> None:
    self.content = None
    self.content_downloads: dict[str, int] = dict()

  def load(self):
    if self.content is not None:
      return
    content_config = root_folder.joinpath('_data/content.yml').read_text()
    self.content = yaml.load(content_config, Loader=yaml.Loader)
    self.content_downloads = dict()
    content_downloads = root_folder.joinpath("_data/content_downloads.json")
    # might not exist as it doesn't ship with the repo
    # downloaded via scripts/install-deps.bash
    if content_downloads.is_file():
      downloads_json = content_downloads.read_text()
      self.content_downloads = json.loads(downloads_json)

data = DataCollection()

class TagCollection():
  def __init__(self):
    self.tags: dict[str, TagFile] = dict()
    self.weight_curve: Callable[[float], float] | None = None

  def load(self):
    if len(self.tags) > 0:
      return # already loaded
    for tagfile in root_folder.joinpath('_tags').iterdir():
      if (not tagfile.is_file()) or tagfile.name.startswith('.'):
        continue
      self.add(TagFile.load(tagfile))
    self.finalize()

  def init_weight_curve(self, world_weight=0.3, last_weight=0.04):
    self.load()
    world_tag = self.get('world')
    assert world_tag
    self.weight_curve = gen_waypoint_power_decay_func(
     world_tag.index,
      world_weight,
      len(self),
      last_weight,
    )
    self.unfound_weight = last_weight / 2.0

  def get_weight_for_tag(self, slug: str) -> float:
    if not self.weight_curve:
      self.init_weight_curve()
    assert self.weight_curve
    tag = self.get(slug)
    if not tag:
      return self.unfound_weight
    return self.weight_curve(tag.index)

  def add(self, tag: TagFile):
    tslug = tag.slug
    tag.children = []
    for othertag in self.tags.values():
      if tslug in othertag.parents:
        tag.children.append(othertag.slug)
    assert tag.parents, f"You forgot to add `parents` to {tag.slug}"
    for otherslug in tag.parents:
      if otherslug in self.tags:
        self.tags[otherslug].children.append(tslug)
    self.tags[tslug] = tag

  def finalize(self):
    for tagnum, tag in enumerate(self):
      # inform each tag of its position in the collection
      # according to the Jekyll naming convention
      tag.index0 = tagnum
      tag.index = tagnum + 1
    self.sortChildren()

  def sortChildren(self):
    for tag in self:
      # sortkey is set in some but not all frontmatters
      # pyrefly: ignore [missing-attribute]
      tag.children.sort(key=lambda k: self.get(k).sortkey or 0)

  def get(self, tag: str) -> TagFile | None:
    return self.tags.get(tag)
  def __iter__(self) -> Iterator[TagFile]:
    for filename in config['collections']['tags']['order']:
      if filename[:-3] not in self.tags:
        raise FileNotFoundError(f"_config.yml expected tag file {filename} which doesn't exist")
      yield self.tags[filename[:-3]]
  def __len__(self):
    return len(self.tags)
  def __contains__(self, item: TagFile | str):
    if isinstance(item, TagFile):
      return item.slug in self.tags
    return item in self.tags

tags = TagCollection()
authors = AuthorCollection()
courses: list[JekyllFile] = []
journals: list[JekyllFile] = []
publishers: list[JekyllFile] = []

def normalized_author_name(author: str) -> str:
  if ' ' in author:
    return author
  af = authors.get(author)
  assert af
  return af.title

# Constants for the Expected Timespent Model
# KEEP THESE IN SYNC WITH content-derived-fields.rb
ETM = {
  'max_expected_mins': 60.0,
  'max_expected_mins_featured': 90.0,
  'x_inter': -0.2,
  'y_asymt': -165.0,
}
ETM['offset'] = ETM['x_inter'] / ETM['y_asymt']

class ContentFile(JekyllFile):
  def __init__(self, fd: Path, content, handler=None, **kwargs) -> None:
    fd = Path(fd)
    super().__init__(fd, content, handler, **kwargs)
    self.category = self.relative_path.parts[1]
    if not self.get('tags'):
        self.tags = []
    if not self.get('formats'):
      if self.category == 'av':
        self.formats = ['mp3']
      else:
        self.formats = ['pdf', 'epub']
    
    ######
    # Add fields from content-derived-fields.rb
    ######

    # paths
    self.content_path = f"{self.category}/{fd.stem}"
    self.url = f"/content/{self.content_path}"

    # stars and featuring post
    self.stars = self.base_stars_for_item()
    self.featured_post = None
    self.free = bool(self.get('external_url') or self.get('file_links') or self.get('drive_links'))

    # page_count (won't be set if no "pages" field present)
    if self.get('pages'):
      pages = self.get('pages')
      if isinstance(pages, str) and '--' in pages:
        pages = pages.split('--')
        self.page_count = int(pages[1]) - int(pages[0]) + 1
      else:
        self.page_count = int(pages)

    self.total_mins = float(self.get('minutes') or 0.0)
    if getattr(self, 'page_count', None) and not self.get('minutes'):
      if data.content is None:
        data.load()
      mins_per_page = data.content.get('mins_per_page', 2.0) if data.content else 2.0
      self.total_mins = float(self.page_count) * mins_per_page
      if self.category == 'canon':
        self.total_mins *= 2.5 # Assume canonical works require deeper reading
      elif self.category == 'reference':
        self.total_mins *= 0.1 # Assume reference works will only be partially read

    if self.get('course_time_multiplier') is None:
      self.course_time_multiplier = 1.0
    else:
      self.course_time_multiplier = float(self.get('course_time_multiplier'))
    self.course_mins = int(self.total_mins * self.course_time_multiplier + 0.5)

    # set the expected value of downloading this item
    # note this relies on many of the previously computed field values!
    self.expected_mins = self.calc_expected_mins()
    if self.get('base_value') is None:
      self.base_value = 0.35
    else:
      self.base_value = float(self.get('base_value'))

    if self.expected_mins is not None:
      stars = float(self.stars)
      if self.category == 'canon':
        stars += 1.0
      # 2.5 cents per star per minute. Make sure to keep this value in sync with
      # _include/inline-av-player.html which logs av watch time at the same value
      self.expected_value = 0.025 * stars * float(self.expected_mins)
    else:
      # use old algo as a fallback in case of no pages/minutes value
      self.expected_value = self.base_value
      if str(self.get('status')) == 'featured':
        self.expected_value *= 2.0
    self.expected_value = round(float(self.expected_value), 3)

  # COPIED FROM content-derived-fields.rb
  def base_stars_for_item(self) -> int:
    if str(self.get('status')) == 'rejected':
      return 1
    if not self.get('course'):
      return 2
    if str(self.get('status')) != 'featured':
      return 3
    return 4

  # COPIED FROM content-derived-fields.rb
  def calc_expected_mins(self) -> float | None:
    mins = float(getattr(self, 'total_mins', 0.0) or 0.0)
    if mins == 0:
      return None
    if not getattr(self, 'free', False) and self.get('excerpt_url'):
      mins *= 0.15 # expect excerpts to contain 15% of the original
    ratio = (1.0 - ETM['offset']) / (mins - ETM['y_asymt'])
    ratio *= mins
    ratio += ETM['offset']
    if str(self.get('status')) == 'featured':
      ret = ETM['max_expected_mins_featured'] * ratio
    else:
      ret = ETM['max_expected_mins'] * ratio
    # make adjustments based on relative conversion likelihood for harder-to-access items
    if not self.get('drive_links') and str(self.get('subcat')) == 'podcast':
      ret *= 0.5
    if not getattr(self, 'free', False) and not self.get('excerpt_url'):
      ret *= 0.01
    return ret
    
  
  def external_url_linkfmt(self):
    """Keep up to date with logic in _includes/content_filelinks.html:3"""
    url = self.external_url
    if not url:
      return None
    if "//www.academia.edu/" in url:
      return "Academia.edu"
    if "pdf" in url or \
       "viewcontent.cgi" in url or \
       "download" in url:
      return "pdf"
    if url.endswith(".mp3"):
      return "mp3"
    if url.endswith(".zip"):
      return "zip"
    if url.endswith("html") or url.endswith(".htm"):
      return "html"
    if "youtu" in url:
      return "YouTube (link)"
    return ""

  def primarytag_ordinality(self) -> tuple[str, int]:
    """Mirrors the logic of _include/content_primarytag_ordinality.liquid"""
    if self.course:
      for idx, candidatecourse in enumerate(courses):
        if self.course == candidatecourse.slug:
          return (self.course, idx)
    for idx, candidatetag in enumerate(tags):
      if candidatetag.slug == self.course:
        return (self.course, idx+len(courses))
    for idx, candidatetag in enumerate(tags):
      if candidatetag.slug in self.tags:
        return (candidatetag.slug, idx+len(courses))
    return ('', 9999)
  
  def __lt__(self, other: 'ContentFile'):
    return self.expected_value < other.expected_value

content: list[ContentFile]
content = []

def entry_with_drive_id(gid):
  for entry in content:
    # pyrefly: ignore [not-iterable]
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
  for filepath in root_folder.joinpath("_courses").glob("*.md"):
    courses.append(JekyllFile.load(filepath))
  courses.sort(key=lambda c: c.created_at)
  for contentfolder in root_folder.joinpath('_content').iterdir():
    if (not contentfolder.is_dir()) or contentfolder.name.startswith('.'):
      continue
    for contentfile in contentfolder.iterdir():
      if contentfile.is_dir() or contentfile.name.startswith('.'):
        continue
      content.append(ContentFile.load(contentfile))
  content.sort(key=lambda c: c.url)
  content.sort(key=lambda c: c.created_at)
  tags.load()
  for authorfile in root_folder.joinpath('_authors').iterdir():
    if (not authorfile.is_file()) or authorfile.name.startswith('.'):
      continue
    authors.add(AuthorFile.load(authorfile))
  for journalfile in root_folder.joinpath('_journals').iterdir():
    if (not journalfile.is_file()) or journalfile.name.startswith('.'):
      continue
    journals.append(JekyllFile.load(journalfile))
  for publisherfile in root_folder.joinpath('_publishers').iterdir():
    if (not publisherfile.is_file()) or publisherfile.name.startswith('.'):
      continue
    publishers.append(JekyllFile.load(publisherfile))
  journals.sort(key=lambda j: j.slug)
  publishers.sort(key=lambda j: j.slug)
  data.load()
  if data.content_downloads:
    for c in content:
      c.download_count = data.content_downloads.get(c.content_path, 0)
      if c.external_url or c.drive_links:
        c.download_count += 1
