#!/bin/python3

print("Initializing...")

import argparse
import csv
import os.path
import shutil
import subprocess
import yaml
import re

from collections import defaultdict
from typing import Callable
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from filecmp import cmp as files_are_same

import website
import gdrive_base
import gdrive

from strutils import (
  prompt,
  radio_dial,
  write_frontmatter_key,
  git_root_folder,
  input_with_prefill,
  get_file_sizes,
  format_size,
)
from executils import get_untracked_files
from tqdm import tqdm
from tqdm.contrib.concurrent import process_map as tqdm_process_map

parser = argparse.ArgumentParser()
parser.add_argument("--dest", type=Path, default=git_root_folder.joinpath("..").resolve())
parser.add_argument("--reportcsv", type=Path)
args = parser.parse_args()

if not args.reportcsv:
  print("Please download a copy of the \"Related Content List\" report as a CSV from OBU's GA4 Account => Explore Tab, fix the header so it's a real CSV and then pass it in as --reportcsv")
  exit(1)

print("Loading the website data...")
reportreader = csv.DictReader(args.reportcsv.open('r'))
revenue_per_url = defaultdict(float)
for row in reportreader:
  path = urlparse(row['Page referrer']).path
  revenue_per_url[path] += float(row['Item revenue'])

website.load()

CFP_SIZE_LIMIT = 26214400 # 25MiB
ARCHIVABLE_FORMATS = [
  'pdf',
  'epub',
]

for sizestring in ["large", "medium"]:
  folder = Path(args.dest / f"{sizestring}files")
  if folder.exists():
    if sizestring != "large":
      assert (folder / ".git").is_dir(), f"{str(folder)} is not a git repo"
      subprocess.run(["git", "pull"], check=True)
  else:
    print(f"{str(folder)} does not exist")
    if sizestring == "medium" and prompt("Clone it?"):
      subprocess.run(["git", "clone", "git@github.com:buddhist-uni/mediumfiles.git", str(folder)], check=True)
    elif sizestring == "large":
      print("  making it...")
      folder.mkdir()
    else:
      print("Okay. Will let you sort that out!")
      exit(1)
for fmt in ARCHIVABLE_FORMATS:
  folder = (args.dest / f"small{fmt}s")
  if folder.exists():
    assert (folder/".git").is_dir(), f"{folder} exists but isn't a git dir"
    subprocess.run(["git", "pull"], check=True)
  else:
    print(f"{str(folder)} does not exist")
    if prompt("Clone it?"):
      subprocess.run(["git", "clone", "git@github.com:buddhist-uni/small{fmt}s.git", str(folder)], check=True)
    else:
      print("Okay. Will let you sort that out!")
      exit(1)

CONFIG_PATH = git_root_folder / 'scripts' / 'update-cdn-config.yml'

class CFPCDNBuilderConfig:
  def __init__(self, path: Path) -> None:
    self.path = path
    self._data = yaml.safe_load(path.read_text())
  def save(self) -> None:
    self.path.write_text(yaml.dump(self._data))
  def blacklist_domain(self, domain: str) -> bool:
    self._data["BLACKLISTED_DOMAINS"].add(domain)
    self.save()
    return False
  def whitelist_domain(self, domain: str) -> bool:
    self._data["WHITELISTED_DOMAINS"].add(domain)
    self.save()
    return True
  def whitelist_publisher(self, publisher: str) -> bool:
    self._data["WHITELISTED_PUBLISHERS"].add(publisher)
    self.save()
    return True
  def whitelist_journal(self, journal: str) -> bool:
    self._data["WHITELISTED_JOURNALS"].add(journal)
    self.save()
    return True
  def is_domain_blacklisted(self, domain: str) -> bool:
    return domain in self._data["BLACKLISTED_DOMAINS"]
  def is_domain_whitelisted(self, domain: str) -> bool:
    return domain in self._data["WHITELISTED_DOMAINS"]
  def is_publisher_whitelisted(self, publisher: str) -> bool:
    return publisher in self._data["WHITELISTED_PUBLISHERS"]
  def is_journal_whitelisted(self, journal: str) -> bool:
    return journal in self._data["WHITELISTED_JOURNALS"]
  def is_searchable_pdf(self, slug: str) -> bool:
    return slug in self._data["SEARCHABLE_PDFS"]
  def is_redirect_pdf(self, slug: str) -> bool:
    return slug in self._data["REDIRECT_PDFS"]
  def mark_pdf_good(self, slug: str) -> None:
    self._data["SEARCHABLE_PDFS"].add(slug)
    self.save()
  def mark_pdf_for_redirect(self, slug: str) -> None:
    self._data["REDIRECT_PDFS"].add(slug)
    self.save()

APP_CONFIG = CFPCDNBuilderConfig(CONFIG_PATH)

def push_all_changes_in_repo(folder: Path, message: str | None = None) -> None:
  subprocess.run(["git", "-C", str(folder), "add", "."], check=True)
  subprocess.run(["git", "-C", str(folder), "commit", "-m", message or "Update files"], check=True)
  subprocess.run(["git", "-C", str(folder), "push"])

candidates: list[tuple[website.ContentFile, int]] = [] # The int is how many of its drive_links to consider copying over

print("Finding eligible content...")
for item in website.content:
  if not item.drive_links:
    continue # We only add file_links from launched drive files
    # we do a more thorough check of the drive_links below when we actually try to add it
    # this round of filtering is just to filter out the obvious rejects
  if item.status == "rejected":
    continue
  if item.file_links:
    continue # This script only adds missing file_links
  url = item.external_url or item.source_url
  if url:
    domain = urlparse(url).netloc
    if APP_CONFIG.is_domain_blacklisted(domain):
      continue
  upto_drive_link = 0
  for i in range(len(item.drive_links)):
    try:
      fmt = item.formats[i]
    except IndexError:
      print(f"Not enough formats in {item.url}")
      raise
    if fmt not in ARCHIVABLE_FORMATS:
      break
    if item.file_links and len(item.file_links) > i and "s/" not in item.file_links[i]:
      break
    upto_drive_link = i + 1
  has_epub = False
  for i in range(upto_drive_link):
    fmt = item.formats[i]
    if fmt == "epub":
      has_epub = True
      break
  linkfmt = item.external_url_linkfmt()
  if not (linkfmt  in ["", "YouTube (link)", None] or has_epub):
    continue
  if upto_drive_link > 0:
    candidates.append((item, upto_drive_link))

small_pdf_canonical_urls: list[tuple[str, website.ContentFile]] = list() # of (filename, canonicalitem)
small_pdf_headers_file: Path = args.dest / "smallpdfs" / "_headers"

if small_pdf_headers_file.is_file():
  print("Loading old smallpdfs/_headers...")
  previous_headers_file = small_pdf_headers_file.read_text().split('\n\n')
  content_url_to_item: dict[str, website.ContentFile] = {
    item.url: item for item in website.content
  }
  for line in previous_headers_file:
    match = re.search(r"(?P<pdf>/[^\s]+\.pdf)[\s\S]*?Link:\s*<(?P<url>[^>]+)>", line)
    assert match, f"Failed to parse ```{line}``` from {small_pdf_headers_file}"
    pdf_filename = match.group("pdf")
    canonurl = match.group("url")
    small_pdf_canonical_urls.append((pdf_filename, content_url_to_item[canonurl]))
  print(f"  loaded {len(small_pdf_canonical_urls)} old smallpdf headers")
  del content_url_to_item

def is_actually_selfhostable(item: website.ContentFile) -> bool:
  external_url = item.external_url or item.source_url
  if external_url:
    domain = urlparse(external_url).netloc
  else:
    domain = ""
  # Because we add to the blacklist during the loop, recheck it
  if domain and APP_CONFIG.is_domain_blacklisted(domain):
    return False
  # All whitelisted items get copied over
  if domain and APP_CONFIG.is_domain_whitelisted(domain):
    return True
  if item.journal and APP_CONFIG.is_journal_whitelisted(item.journal):
    return True
  if item.publisher and APP_CONFIG.is_publisher_whitelisted(item.publisher):
    return True
  
  # If not whitelisted and we have a legit external_url, no need for a third copy
  if item.external_url and not item.external_url.startswith("https://web.archive.org"):
    return False
  
  # If we're down to a web.archive url but have a backup url, that's okay too
  if item.external_url and str(item.external_url).startswith("https://web.archive.org") and item.alternate_url:
    return False

  # So now in this case, we have at best a web.archive.org external_url (or none at all)
  # and no alternate_url and we don't know if this item is white or black listed
  # so, let's ask the user what to do:

  print(f"\n{item.content_path} has drive_links but no good external_url.  Back it up to file_links?", flush=True)

  radio_choices: list[tuple[str, Callable]] = []
  if domain:
    radio_choices.append((f"Whitelist {domain}", lambda: APP_CONFIG.whitelist_domain(domain)))
    radio_choices.append((f"Blacklist {domain}", lambda: APP_CONFIG.blacklist_domain(domain)))
  if item.publisher:
    radio_choices.append((f"Whitelist publisher: {item.publisher}", lambda: APP_CONFIG.whitelist_publisher(item.publisher)))
  if item.journal:
    radio_choices.append((f"Whitelist journal: {item.journal}", lambda: APP_CONFIG.whitelist_journal(item.journal)))
  radio_choices.append(("Teach me how to do something else", lambda: exit(1)))
  
  choice = radio_dial([choice[0] for choice in radio_choices])
  return radio_choices[choice][1]()


for item, upto in candidates:
  if not is_actually_selfhostable(item):
    continue
  
  new_file_links = []
  for i in range(upto):
    fmt = item.formats[i]
    gid = gdrive_base.link_to_id(item.drive_links[i])
    assert isinstance(gid, str), f"Unable to parse {item.drive_links[i]}"
    gitem = gdrive.gcache.get_item(gid)
    assert gitem, f"Unable to load {gid} from Google Drive"
    fpath = gdrive.gcache.get_cache_path_for_file(gitem)
    assert fpath, f"{gid} for {item.content_path} is not downloadable?"
    if not fpath.is_file():
      fpath = gdrive.gcache.download_file_to_cache(gitem, verbose=True)
      assert fpath and fpath.is_file(), f"Failed to download {gid} for {item.content_path}"
    new_name = item.slug
    try:
      pivot = item.slug.rindex("_")
      author = item.slug[pivot+1:]
      title = item.slug[:pivot]
      new_name = f"{author}_{item.year}_{title}"
    except ValueError:
      pass # just use the item's slug as-is
    stsize = fpath.stat().st_size
    assert stsize > 0, f"File isn't"
    if stsize >= CFP_SIZE_LIMIT*2:
      new_name = f"largefiles/{new_name}.{fmt}"
    elif stsize >= CFP_SIZE_LIMIT:
      new_name = f"mediumfiles/{new_name}.{fmt}"
    else:
      new_name = f"small{fmt}s/{new_name}.{fmt}"
      if fmt == "pdf":
        small_pdf_canonical_urls.append((new_name.replace("smallpdfs", ""), item))
    destpath = args.dest / new_name
    if not (destpath.exists() and files_are_same(fpath, destpath)):
      shutil.copy2(fpath, destpath)
    new_file_links.append(new_name)
  item.file_links = new_file_links
  write_frontmatter_key(
    item.absolute_path,
    "file_links",
    new_file_links,
    insert_after_key="drive_links",
  )
print("Done!")

# Commit the changes to the git repos

# First we add the canonical rel link headers to as many of the smallpdfs as we can
small_pdf_canonical_urls.sort(key=lambda t: revenue_per_url[t[1].url] + (t[1].download_count * 0.01), reverse=True)
headerrules = []
for filename, item in small_pdf_canonical_urls:
  url = item.url
  if APP_CONFIG.is_searchable_pdf(url):
    continue
  if len(headerrules) >= 100: # CFPages has a 100 rule limit for _headers
    break
  if not APP_CONFIG.is_redirect_pdf(url):
    if revenue_per_url[url] > 1.0:
      if prompt(f"Is the PDF for {website.baseurl}{url} good enough to feature on Google?", default='n'):
        APP_CONFIG.mark_pdf_good(url)
        continue
      else:
        APP_CONFIG.mark_pdf_for_redirect(url)
    else: # if not much revenue anyway, just use the "featured" value as a proxy and don't waste my time asking
      if item.status == "featured":
        continue
  headerrules.append(f"""{filename}
  Link: <{website.baseurl}{url}>; rel="canonical"
""")
small_pdf_headers_file.write_text("\n".join(headerrules))

folders = [f"small{fmt}s" for fmt in ARCHIVABLE_FORMATS] + ["mediumfiles"]
for lf in folders:
  folder = (args.dest / lf)
  newfiles = get_untracked_files(folder)
  files, totalsize = get_file_sizes(newfiles)
  if totalsize == 0:
    print(f"No new files found in {lf}")
    continue
  print(f"Will commit the following files to {lf}:")
  for f, s in files.items():
    print(f"  {os.path.basename(f)} ({format_size(s)})")
  print(f"Total size: {format_size(totalsize)}")
  input("Press enter to continue")
  print(f"\nPushing {lf}...")
  push_all_changes_in_repo(folder, f"Automated {datetime.now().strftime('%Y-%m-%d')} update")

if prompt("Run rclone config?"):
  subprocess.run(['rclone', 'config'])
print("Alrighty then! Please provide:")
configname = input_with_prefill("rclone config name: ", "r2")
bucketname = input_with_prefill("bucket name: ", "large-public-downloadables")
dryrunoutput = subprocess.run(
  ["rclone", "copy", "--update", "--dry-run", str(args.dest / "largefiles"), f"{configname}:{bucketname}"],
  capture_output=True,
  text=True
)
if dryrunoutput.returncode:
  print("There was an error running rclone")
  print(dryrunoutput.stderr)
  quit(dryrunoutput.returncode)
if "0 B / 0 B" in dryrunoutput.stderr:
  print("No files to copy!")
else:
  print("\n===DRY RUN===")
  print(dryrunoutput.stderr)
  input("\nPress enter to execute the above...")
  subprocess.run(["rclone", "copy", "--update", "--progress", str(args.dest / "largefiles"), f"{configname}:{bucketname}"])
  print("\n===Done uploading!===\n")

# Find if there are any r2 files we can delete
locals = subprocess.Popen(["ls", str(args.dest / "largefiles")], stdout=subprocess.PIPE)
remotes = subprocess.Popen(
  ["rclone", "ls", "--exclude-from", "-", f"{configname}:{bucketname}"],
  stdin=locals.stdout, stdout=subprocess.PIPE)
# pyrefly: ignore [missing-attribute]
locals.stdout.close()
onlyremotes = remotes.communicate()[0].decode("utf-8").strip()
if onlyremotes:
  print("Remote files not found locally (which might be deletable?):")
  print(onlyremotes)
  print("\nTo delete them, run `rclone rm` or `rclone sync`")
