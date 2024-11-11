#!/bin/python3

print("Initializing...")

import argparse
import os.path
import shutil
import subprocess
import yaml

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import website
import gdrive

from strutils import (
  prompt,
  radio_dial,
  write_frontmatter_key,
  git_root_folder,
  input_with_prefill,
  get_untracked_files,
  get_file_sizes,
  format_size,
)
from tqdm import tqdm
from tqdm.contrib.concurrent import process_map as tqdm_process_map
from train_tag_predictor import (
  PDF_TEXT_FOLDER,
  EPUB_TEXT_FOLDER,
)

parser = argparse.ArgumentParser()
parser.add_argument("--dest", type=Path, default=git_root_folder.joinpath("..").resolve())
args = parser.parse_args()

print("Loading the website data...")
website.load()

CFP_SIZE_LIMIT = 26214400 # 25MiB
ARCHIVABLE_FORMATS = {
  'pdf': PDF_TEXT_FOLDER,
  'epub': EPUB_TEXT_FOLDER,
}

for sizestring in ["large", "medium"]:
  folder = (args.dest / f"{sizestring}files")
  if not folder.exists():
    print(f"{str(folder)} does not exist")
    if sizestring == "medium" and prompt("Clone it?"):
      subprocess.run(["git", "clone", "git@github.com:buddhist-uni/mediumfiles.git", str(folder)], check=True)
    elif sizestring == "large":
      print("  making it...")
      folder.mkdir()
    else:
      print("Okay. Will let you sort that out!")
      exit(1)
  if sizestring != "large" and not (folder / ".git").exists():
    raise Exception(f"{str(folder)} is not a git repo")
for fmt in ARCHIVABLE_FORMATS.keys():
  folder = (args.dest / f"small{fmt}s")
  if not folder.exists():
    print(f"{str(folder)} does not exist")
    if prompt("Clone it?"):
      subprocess.run(["git", "clone", "git@github.com:buddhist-uni/small{fmt}s.git", str(folder)], check=True)
    else:
      print("Okay. Will let you sort that out!")
      exit(1)
  if not (folder / ".git").exists():
    raise Exception(f"{str(folder)} is not a git repo")

CONFIG_PATH = git_root_folder / 'scripts' / 'update-cdn-config.yml'

class CFPCDNBuilderConfig:
  def __init__(self, path: Path) -> None:
    self.path = path
    self._data = yaml.safe_load(path.read_text())
  def save(self) -> None:
    self.path.write_text(yaml.dump(self._data))
  def blacklist_domain(self, domain: str) -> None:
    self._data["BLACKLISTED_DOMAINS"].add(domain)
    self.save()
  def whitelist_domain(self, domain: str) -> None:
    self._data["WHITELISTED_DOMAINS"].add(domain)
    self.save()
  def is_domain_blacklisted(self, domain: str) -> bool:
    return domain in self._data["BLACKLISTED_DOMAINS"]
  def is_domain_whitelisted(self, domain: str) -> bool:
    return domain in self._data["WHITELISTED_DOMAINS"]

APP_CONFIG = CFPCDNBuilderConfig(CONFIG_PATH)

def push_all_changes_in_repo(folder: Path, message: str = None) -> None:
  subprocess.run(["git", "-C", str(folder), "add", "."], check=True)
  subprocess.run(["git", "-C", str(folder), "commit", "-m", message or "Update files"], check=True)
  subprocess.run(["git", "-C", str(folder), "push"])

candidates = []
drive_ids_to_fetch = dict()

print("Finding eligible content...")
for item in website.content:
  if not item.drive_links or not (item.external_url or item.source_url):
    continue
  if not item.course or item.status == "rejected":
    continue
  domain = urlparse(item.external_url or item.source_url).netloc
  if APP_CONFIG.is_domain_blacklisted(domain):
    continue
  upto_drive_link = 0
  drive_ids = dict()
  for i in range(len(item.drive_links)):
    fmt = item.formats[i]
    if fmt not in ARCHIVABLE_FORMATS:
      break
    if item.file_links and len(item.file_links) > i and "s/" not in item.file_links[i]:
      break
    upto_drive_link = i + 1
    LOCAL_FOLDER = ARCHIVABLE_FORMATS[fmt]
    gid = gdrive.link_to_id(item.drive_links[i])
    fpath = LOCAL_FOLDER.joinpath(f"{gid}.{fmt}")
    if not fpath.exists():
      drive_ids[gid] = fmt
  has_epub = False
  for i in range(upto_drive_link):
    fmt = item.formats[i]
    if fmt == "epub":
      has_epub = True
      break
  linkfmt = item.external_url_linkfmt()
  if linkfmt not in ["", "YouTube (link)", None] and not has_epub:
    continue
  if has_epub and linkfmt == "pdf":
    continue
  if upto_drive_link > 0:
    candidates.append((item, upto_drive_link))
    drive_ids_to_fetch.update(drive_ids)

# Download all drive_ids_to_fetchinto their respective folders
print(f"Fetching Google Drive metadata...")
filedata = gdrive.batch_get_files_by_id([gid for gid in drive_ids_to_fetch.keys()], "id,size,owners")
drive_files_to_download = []
drive_file_locations = []
bytestodownload = 0
for gfile in tqdm(filedata, total=len(drive_ids_to_fetch)):
  if gfile['owners'][0]['emailAddress'] != "theopenbuddhistuniversity@gmail.com":
    continue
  fmt = drive_ids_to_fetch[gfile['id']]
  drive_files_to_download.append(gfile['id'])
  LOCAL_FOLDER = ARCHIVABLE_FORMATS[fmt]
  fpath = LOCAL_FOLDER.joinpath(f"{gfile['id']}.{fmt}")
  drive_file_locations.append(str(fpath))
  bytestodownload += int(gfile['size'])

print(f"Downloading {len(drive_files_to_download)} files ({bytestodownload/1024/1024/1024:.2f} GB)...")
tqdm_process_map(
  gdrive.download_file,
  drive_files_to_download,
  drive_file_locations,
  [False]*len(drive_files_to_download),
  max_workers=4,
)
print("Done downloading files!")

print("Copying files and setting file_links...")

# Now go through every candidate and format
#   if the file exists in LOCAL_FOLDER
#      copy to args.dest with the flipped name
#      and set the file_link appropriately

for item, upto in candidates:
  domain = urlparse(item.external_url or item.source_url).netloc
  if APP_CONFIG.is_domain_blacklisted(domain):
    continue
  if not APP_CONFIG.is_domain_whitelisted(domain):
    print(f"\n\"{item.title}\" has a link to {item.drive_links[0]} from {item.external_url or item.source_url} (see: https://buddhistuniversity.net{item.url}).", flush=True)
    choice = radio_dial([f"Whitelist {domain}", f"Blacklist {domain}"])
    if choice == 0:
      APP_CONFIG.whitelist_domain(domain)
    elif choice == 1:
      APP_CONFIG.blacklist_domain(domain)
      continue
    else:
      raise NotImplementedError()
  new_file_links = []
  for i in range(upto):
    fmt = item.formats[i]
    LOCAL_FOLDER = ARCHIVABLE_FORMATS[fmt]
    gid = gdrive.link_to_id(item.drive_links[i])
    fpath = LOCAL_FOLDER.joinpath(f"{gid}.{fmt}")
    if not fpath.exists():
      print(f" Skipping undownloaded {gid}.{fmt}")
      break
    new_name = item.slug
    try:
      pivot = item.slug.rindex("_")
      author = item.slug[pivot+1:]
      title = item.slug[:pivot]
      new_name = f"{author}_{item.year}_{title}"
    except ValueError:
      pass
    stsize = fpath.stat().st_size
    if stsize >= CFP_SIZE_LIMIT*2:
      new_name = f"largefiles/{new_name}.{fmt}"
    elif stsize >= CFP_SIZE_LIMIT:
      new_name = f"mediumfiles/{new_name}.{fmt}"
    else:
      new_name = f"small{fmt}s/{new_name}.{fmt}"
    destpath = args.dest / new_name
    if not destpath.exists():
      print(f" Copying {new_name}")
      shutil.copy(fpath, destpath)
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
folders = [f"small{fmt}s" for fmt in ARCHIVABLE_FORMATS.keys()] + ["mediumfiles"]
for lf in folders:
  folder = (args.dest / lf)
  newfiles = get_untracked_files(folder)
  files, totalsize = get_file_sizes(newfiles)
  if totalsize == 0:
    print(f"No new files found in {lf}")
    continue
  print("Will commit the following files:")
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
subprocess.run(["rclone", "copy", "--update", "--progress", str(args.dest / "largefiles"), f"{configname}:{bucketname}"])

print("\nDone copying!")
locals = subprocess.Popen(["ls", str(args.dest / "largefiles")], stdout=subprocess.PIPE)
remotes = subprocess.Popen(
  ["rclone", "ls", "--exclude-from", "-", f"{configname}:{bucketname}"],
  stdin=locals.stdout, stdout=subprocess.PIPE)
locals.stdout.close()
onlyremotes = remotes.communicate()[0].decode("utf-8").strip()
if onlyremotes:
  print("Remote files not found locally (which might be deletable?):")
  print(onlyremotes)
  print("\nTo delete them, run `rclone rm` or `rclone sync`")
