#!/bin/python

import gdrive
import gdrive_base
import datetime
from collections import defaultdict
from functools import cache
from strutils import git_root_folder, md5

ROOT_FOLDER = "1NRjvD6E997jdaRpN5zAqxnaZv0SM-SOv"
FIELDS = "id,name,mimeType,size,shortcutDetails,createdTime,webViewLink"
MY_EMAILS = {
  'd97d9501979b0a1442b0482418509a84',
}

TD = 'td style="padding:5pt;"'

def human_readable_size(bytes_size):
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    if bytes_size == 0:
        return "0 B"
    index = 0
    size = float(bytes_size)
    while size >= 922 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.2f} {units[index]}"

def headerize(text, depth):
  if depth < 1:
    return ''
  if depth <= 4:
    return f"<h{depth}>{text}</h{depth}>"
  if depth <= 6:
    return f'<h{depth}><span style="font-size=11pt;">{text}</span></h{depth}>'
  space = "&nbsp;&nbsp;"*(depth-1)
  return f"<p>{space}+ {text}</p>"

seen_folders = set()

class DriveFolder:
  def __init__(self, name: str, folderid: str, createdTime: str, depth: int) -> None:
    if folderid in seen_folders:
      raise ValueError(f"Folder already seen: {folderid}")
    seen_folders.add(folderid)
    print(f"Loading folder \"{name}\"...")
    self.name = name
    self.id = folderid
    self.createdTime = createdTime
    self.depth = depth
    self.files = []
    subfolders = []
    shortcuts = []
    query = f"trashed=false AND '{folderid}' in parents"
    for child in gdrive.all_files_matching(query, FIELDS):
      if child['mimeType'] == 'application/vnd.google-apps.folder':
        subfolders.append(child)
        continue
      if child['mimeType'] == 'application/vnd.google-apps.shortcut':
        shortcuts.append(child)
        continue
      child['size'] = int(child.get('size', 0))
      self.files.append(child)
    if len(shortcuts) > 0:
      print(f"  Resolving {len(shortcuts)} shortcut(s)...")
      for child in gdrive.batch_get_files_by_id(
        [c['shortcutDetails']['targetId'] for c in shortcuts],
        FIELDS+',owners'
      ):
        shortcut = [s for s in shortcuts if s['shortcutDetails']['targetId'] == child['id']][0]
        owner = child['owners'][0]
        if md5(owner['emailAddress']) in MY_EMAILS:
          print(f"  Skipping {shortcut['name']}->{child['name']} because it's owned by me")
          continue
        child['originalName'] = child['name']
        child['originalCreatedTime'] = child['createdTime']
        child['name'] = shortcut['name']
        child['createdTime'] = shortcut['createdTime']
        if child['mimeType'] == 'application/vnd.google-apps.folder':
          subfolders.append(child)
        else:
          child['size'] = int(child.get('size', 0))
          self.files.append(child)
    print(f"  Got {len(self.files)} files and {len(subfolders)} subfolders")
    self.subfolders = []
    for child in subfolders:
      self.subfolders.append(DriveFolder(
        child['name'],
        child['id'],
        child['createdTime'],
        self.depth + 1,
      ))
    self.files = sorted(self.files, key=lambda f: f['name'])
    self.subfolders = sorted(self.subfolders, key=lambda f: f.name)
  
  @cache
  def total_size(self):
    return sum(f['size'] for f in self.files) + sum(f.total_size() for f in self.subfolders)
  
  @cache
  def total_count(self):
    return sum(f.total_count() for f in self.subfolders) + len(self.files)
  
  def file_count_by_mimetype(self):
    ret = defaultdict(lambda: {'size': 0, 'count': 0})
    for t in set([g['mimeType'] for g in self.files]):
      fs = [f for f in self.files if f['mimeType'] == t]
      ret[t] = {'size': sum(f['size'] for f in fs), 'count': len(fs)}
    for child in self.subfolders:
      subcounts = child.file_count_by_mimetype()
      for t in subcounts:
        ret[t]['count'] += subcounts[t]['count']
        ret[t]['size'] += subcounts[t]['size']
    return ret
  
  def list_files(self):
    space = '&nbsp;&nbsp;'*self.depth
    ret = [headerize(
      f'<a href="{gdrive_base.FOLDER_LINK_PREFIX}{self.id}">{self.name}</a> <span style="color:#666666;">({human_readable_size(self.total_size())})</span>',
      self.depth,
    )]
    for child in self.files:
      ret.append(f"""<p>{space}- <a href="{child['webViewLink']}">{child['name']}</a></p>""")
    for child in self.subfolders:
      ret.append(child.list_files())
    return '\n'.join(ret)

if __name__ == "__main__":

  root = DriveFolder("A Curated Buddhist G-Library", ROOT_FOLDER, "2019-01-01T00:00:00Z", 0)
  total_size = human_readable_size(root.total_size())
  total_count = root.total_count()
  print("\n==================\nFinished fetching data!\n==================\n")

  html = f"""<html>
    <head><meta content="text/html; charset=UTF-8"></head>
    <body class="doc-content">
      <p class="title" style="font-size:26pt;padding-bottom:3pt;line-height:1.15;page-break-after:avoid;font-family:&quot;Arial&quot;;orphans:2;widows:2;text-align:left;"><span style="font-weight:400;text-decoration:none;vertical-align:baseline;font-size:26pt;font-family:&quot;Arial&quot;;font-style:normal">Buddhist G-Library Catalog</span></p>
      <p>An automatically generated list of all the files in the Library.</p>
      <p>Generated on {datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")}</p><p></p>
      <p>In total, the library is {total_size} large and contains {total_count} files. They break down by MIME type as follows:</p>
      <table><tr style="text-decoration:underline;"><{TD}>MIME Type</td><{TD}>Count</td><{TD}>Size</td></tr>
      {"".join(f"<tr><{TD}>{t}</td><{TD}>{c['count']}</td><{TD}>{human_readable_size(c['size'])}</td></tr>" for t, c in root.file_count_by_mimetype().items())}
      <tr style="font-weight:700;"><{TD}>Total</td><{TD}>{total_count}</td><{TD}>{total_size}</td></tr>
      </table><p></p><h1>Files</h1><p></p>{root.list_files()}
    </body>
  </html>
  """
  htmlfile = git_root_folder.joinpath("catalog.html")
  htmlfile.write_text(html)

  print("Replacing public doc with new version...")
  docid = gdrive.create_doc(
    html=html,
    creator="CatalogBuilder",
    replace_doc="1IYrQyVyr8FfbHwRLH5OzwSQG9mhgl0av73klfi-t0DQ",
  )
  if not docid:
    raise RuntimeError("Failed to upload catalog.html")
  else:
    htmlfile.unlink()
  print(f"Done! See https://docs.google.com/document/d/{docid}/edit")
