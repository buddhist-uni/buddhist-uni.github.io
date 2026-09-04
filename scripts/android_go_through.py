#!/bin/python3

# This file is only a script and is not importable

# The structure is a bit crazy and nonstandard because
# I want to call "system_open" as quickly as possible
# in the non-init case, and defer as much loading as possible
# to happen _after_ the "system_open" call.

from yaspin import yaspin
with yaspin(text="Initializing..."):
  from strutils import (
    Path,
    git_root_folder,
    md5,
    file_info,
    input_with_prefill,
  )
  from executils import system_open
  from argparse import (
    ArgumentParser,
    BooleanOptionalAction,
    ArgumentDefaultsHelpFormatter,
  )
  parser = ArgumentParser(
    description="Script for manually sorting the Open Access Inbox on-the-go",
    formatter_class=ArgumentDefaultsHelpFormatter,
  )
  parser.add_argument(
    "local_folder",
    nargs='?',
    default=git_root_folder.joinpath("../To Go Through").resolve(),
    type=Path,
    help="Directory storing the inbox files",
  )
  parser.add_argument(
    "--init",
    action=BooleanOptionalAction,
    help="Run the initialization code before jumping into reviewing mode",
    default=False,
  )
  cli_args = parser.parse_args()
  
  predictor = None
  LOCAL_FOLDER: Path
  LOCAL_FOLDER = cli_args.local_folder
  if not LOCAL_FOLDER.is_dir() and not cli_args.init:
    raise ValueError(f"{str(LOCAL_FOLDER)} is not a valid directory.")
  # TODO: parameterize these as well?
  LOCAL_MERGE_FOLDER = git_root_folder.joinpath("../To Merge/")
  LOCAL_SPLIT_FOLDER = git_root_folder.joinpath("../To Split/")
  REMOTE_FOLDER = "1PXmhvbReaRdcuMdSTuiHuWqoxx-CqRa2"
  REMOTE_FOLDER_NAME = "📥 To Go Through"
  MANIFEST_PATH = LOCAL_FOLDER.joinpath('.manifest.json')

def load_normalized_text_for_file(fp: Path, google_id: str) -> str:
  from pdfutils import readpdf
  from epubutils import read_epub
  from tag_predictor import(
    normalize_text,
    save_normalized_text,
    local_normalized_text_file,
    joblib,
    NORMALIZED_DRIVE_FOLDER,
  )
  # Short out early if we can't read the file type
  if fp.suffix.lower() not in ['.pdf', '.epub']:
    return ''
  import gdrive
  from pickle import UnpicklingError
  local_file = local_normalized_text_file(google_id)
  if local_file.is_file():
    try:
      return joblib.load(local_file)
    except (UnpicklingError, EOFError):
      print(f"WARNING: Ignoring bad pickle file at {local_file}")
      local_file.unlink()
  remote_file = gdrive.gcache.files_exactly_named(local_file.name)
  if len(remote_file) > 0:
    remote_file = remote_file[0]
    assert remote_file['parent_id'] == NORMALIZED_DRIVE_FOLDER, f"Unexpected location for remote {local_file.name}"
    gdrive.download_file(remote_file['id'], local_file, verbose=False)
    assert local_file.is_file() and file_info(local_file)[0] == remote_file['md5Checksum'], f"Failed to download {remote_file['id']} to {local_file}"
    try:
      return joblib.load(local_file)
    except (UnpicklingError, EOFError):
      gdrive.gcache.trash_file(remote_file['id'])
      local_file.unlink()
      print(f"WARNING: Found bad remote pickle {local_file.name} at {remote_file['id']}")
  text = ""
  if fp.suffix.lower() == '.pdf':
    text = readpdf(fp)
  elif fp.suffix.lower() == '.epub':
    text = read_epub(fp)
  # If you ever teach me how to read another file type,
  # please tell clean_google_drive's pickle filter about the new extension
  else:
    raise Exception("Should have been handled above.")
  text = normalize_text(text)
  save_normalized_text(google_id, text)
  return text

from dataclasses import asdict, dataclass
import json

@dataclass(slots=True)
class TGTDocument:
  filename: str
  gid: str
  def to_dict(self) -> dict:
    return asdict(self)

class TGTQueueDB():
  def __init__(self, json_path: Path):
    self.json_path = json_path
    if json_path.exists():
      data: dict = json.loads(json_path.read_text())
      self.documents = [
        TGTDocument(**doc)
        for doc in data['documents']
      ]
    else:
      self.documents = []
  def to_json(self) -> str:
    return json.dumps({'documents': [d.to_dict() for d in self.documents]})
  def write(self):
    self.json_path.write_text(self.to_json())

if cli_args.init:
  print(f"Setting up '{LOCAL_FOLDER}' as inbox folder...")
  import gdrive
  folder_slugs = gdrive.load_folder_slugs()
  from bulk_import import (
    get_all_predictable_unread_folders,
    all_folders_with_name_by_course,
    get_or_create_autopdf_folder_for_course,
    TagPredictor,
    tqdm_thread_map,
  )
  from tag_predictor import NORMALIZED_TEXT_FOLDER
  course_predictor = TagPredictor.load()
  unread_id_to_course_name_map, course_name_to_unread_id_map = get_all_predictable_unread_folders(course_predictor.classes)
  course_to_autopdf_folder, autopdf_folder_to_course = all_folders_with_name_by_course(
    REMOTE_FOLDER_NAME,
    "To Go Through",
    unread_id_to_course_name_map,
  )
  remote_folder_ids = set(autopdf_folder_to_course.keys())
  remote_folder_ids.add(REMOTE_FOLDER)
  remote_children = gdrive.gcache.sql_query(
    f"parent_id IN ({','.join('?' * (1+len(course_to_autopdf_folder)))}) AND mime_type != ? AND shortcut_target IS NULL AND mime_type != ?",
    tuple(remote_folder_ids) + ('application/vnd.google-apps.folder', 'application/vnd.google-apps.document', )
  )
  remote_files_by_name: dict[str, dict] = dict()
  for gfile in remote_children:
    assert gfile['name'] not in remote_files_by_name, f"Found duplicate file name \"{gfile['name']}\""
    remote_files_by_name[gfile['name']] = gfile
  from tqdm import tqdm
  print(f"# Removing local duplicates...")
  local_files = [f for f in LOCAL_FOLDER.iterdir() if f.is_file() and not f.name.startswith(".")]
  from collections import defaultdict
  pbar = tqdm(local_files, unit="f")
  size_to_local_names = defaultdict(set)
  for fp in pbar:
    size_to_local_names[fp.stat().st_size].add(fp.name)
  for size, name_list in size_to_local_names.items():
    if len(name_list) <= 1:
      continue
    md5s = [md5(LOCAL_FOLDER.joinpath(name)) for name in name_list]
    md5s_to_name = defaultdict(set)
    for name, hash in zip(name_list, md5s):
      md5s_to_name[hash].add(name)
    for actually_same_name_list in md5s_to_name.values():
      if len(actually_same_name_list) <= 1:
        continue
      name_to_keep = min(actually_same_name_list, key=lambda n: LOCAL_FOLDER.joinpath(n).stat().st_mtime)
      print(f"Keeping: {name_to_keep}")
      for name in actually_same_name_list:
        if name == name_to_keep:
          continue
        fp = LOCAL_FOLDER.joinpath(name)
        print(f"  Deleting: {name}")
        local_files.remove(fp)
        fp.unlink()
  del size_to_local_names
  print(f"# Ensuring all local files are already on Drive and are unsorted...")
  remote_ids_seen = set()
  local_filenames_seen = set()
  def process_local_file(fp: Path):
    remote_file = remote_files_by_name.get(fp.name)
    if not remote_file:
      remote_file = gdrive.gcache.get_trashed_items_with_md5(md5(fp))
      if remote_file:
        print(f"    Deleting already deleted {fp.name}")
        # fp.unlink()
        # For now just move it out to be on the safe side...
        fp.rename(fp.parent.joinpath('../../Download/').joinpath(fp.name))
        return
    if not remote_file:
      # Does the uploading if needed
      remote_file = gdrive.remote_file_for_local_file(
        fp,
        folder_slugs,
        default_folder_id=REMOTE_FOLDER,
      )
    if not remote_file:
      raise ValueError(f"Failed to upload \"{fp.name}\"")
    if remote_file['parent_id'] in remote_folder_ids:
      if remote_files_by_name[fp.name]['md5Checksum'] != remote_file['md5Checksum']:
        print(f"The file we have locally by the name {fp.name} isn't the same as the remote file with that name!")
        # The remote_files_by_name[fp.name] write below makes sure that mapping is corrected
        # and the "We already have..." prompt in the loop below handles what to do with the remote file
        # so actually there's nothing to handle here?
      if fp.name != remote_file['name']:
        msg = (
          f"Found\n  \"{fp.name}\"\n"
          "in the remote folder, but there it's called\n"
          f"  \"{remote_file['name']}\"\n"
          "Renaming the remote to the local name..."
        )
        tqdm.write(msg)
        gdrive.gcache.rename_file(remote_file['id'], fp.name)
        del remote_files_by_name[remote_file['name']]
        remote_file['name'] = fp.name
      remote_files_by_name[fp.name] = remote_file
      remote_ids_seen.add(remote_file['id'])
      local_filenames_seen.add(fp.name)
    else:
      tqdm.write(f"    Deleting already sorted {fp.name}")
      # fp.unlink()
      # For now just move it out to be on the safe side...
      fp.rename(fp.parent.joinpath('../../Download/').joinpath(fp.name))
    if remote_file['parent_id'] == REMOTE_FOLDER and fp.suffix.lower() in ['.pdf', '.epub']:
      if not NORMALIZED_TEXT_FOLDER.joinpath(remote_file['id']+'.pkl').exists():
        load_normalized_text_for_file(fp, remote_file['id'])
  tqdm_thread_map(process_local_file, local_files, max_workers=8, unit="f")
  print(f"# Ensuring all remote files are downloaded locally...")
  children = tqdm(remote_children, unit="f")
  for child in children:
    if child['id'] in remote_ids_seen:
      continue
    name = child['name'] 
    if name in local_filenames_seen:
      tqdm.write(f"We already have a file named '{name}' ( {gdrive.DRIVE_LINK.format(remote_files_by_name[name]['id'])} ).\nPlease decide on a new, unique name for {gdrive.DRIVE_LINK.format(child['id'])}")
      name = input_with_prefill('name (or trash): ', name)
      if not name or name == 'trash':
        tqdm.write("Trashing...")
        gdrive.log_move_reason(
          child['id'],
          new_parent_id='trash',
          old_parent_id=child.get("parent_id", REMOTE_FOLDER),
          reason=f"marked as duplicating {remote_files_by_name[name]['id']}",
        )
        gdrive.gcache.trash_file(child['id'])
        continue
      gdrive.gcache.rename_file(child['id'], name)
      child['name'] = name
      remote_files_by_name[name] = child
    tqdm.write(f"Downloading '{name}' ({round(child['size']/1000000, 2)} MB)...")
    dest_file = LOCAL_FOLDER.joinpath(name)
    gdrive.download_file(
      child['id'],
      destination=dest_file,
      verbose=False,
    )
    local_filenames_seen.add(name)
    if child['parent_id'] == REMOTE_FOLDER and dest_file.suffix in ['.pdf', '.epub']:
       if not NORMALIZED_TEXT_FOLDER.joinpath(child['id']+'.pkl').exists():
          load_normalized_text_for_file(dest_file, child['id'])
  print("# Sorting PDFs into bulk import folders...")
  unsorted_children = gdrive.gcache.sql_query(
    "parent_id = ? AND mime_type = 'application/pdf' AND shortcut_target IS NULL",
    (REMOTE_FOLDER,),
  )
  def sort_pdf_file(child):
    fp = LOCAL_FOLDER.joinpath(child['name'])
    normalized_text = load_normalized_text_for_file(fp, child['id'])
    course = course_predictor.predict([
      normalized_text + ' ' + normalize_text((' '+fp.stem) * 3)
    ], normalized=True)[0]
    new_folder = get_or_create_autopdf_folder_for_course(
      course,
      REMOTE_FOLDER_NAME,
      course_to_autopdf_folder,
      course_name_to_unread_id_map,
      unread_id_to_course_name_map,
      autopdf_folder_to_course,
    )
    gdrive.log_move_reason(
      child['id'],
      new_parent_id=new_folder,
      old_parent_id=REMOTE_FOLDER,
      reason="Automated initial sort",
    )
    gdrive.gcache.move_file(
      child['id'],
      new_folder,
      [REMOTE_FOLDER],
      verbose=False,
    )
    remote_files_by_name[child['name']]['parent_id'] = new_folder
  tqdm_thread_map(sort_pdf_file, unsorted_children, max_workers=8, unit="f")
  print("# Writing local .manifest.json...")
  import website
  website.tags.load()
  website.tags.init_weight_curve(world_weight=0.3, last_weight=0.04)
  files: list[dict] = []
  weights: list[float] = []
  remote_file_names = set(remote_files_by_name.keys())
  # refetch because some files were added or removed above
  local_files = [f for f in LOCAL_FOLDER.iterdir() if f.is_file() and not f.name.startswith(".")]
  local_file_names = {fp.name for fp in local_files}
  assert local_file_names == remote_file_names, f"Somehow we got a mismatch between our {len(local_file_names)} local files and {len(remote_file_names)} remote files!"
  for fname, file in remote_files_by_name.items():
    if file['parent_id'] == REMOTE_FOLDER:
      weight = 0.5
    else:
      course = autopdf_folder_to_course[file['parent_id']]
      weight = website.tags.get_weight_for_tag(course)
    files.append(file)
    weights.append(weight * file['size'])
  from mathutils import weighted_shuffle
  files = weighted_shuffle(files, weights)
  queue = TGTQueueDB(MANIFEST_PATH)
  first_filename = None
  # make sure to keep the first document the same if there is one
  # so as to not interrupt the user if they were in the middle of reading
  # this particular document
  if len(queue.documents) > 0:
    first_filename = queue.documents[0].filename
    del queue.documents[1:]
  queue.documents.extend([
    TGTDocument(filename=doc['name'], gid=doc['id'])
    for doc in files
    if doc['name'] != first_filename
  ])
  queue.write()
  print("Done setting up local folder! Run again without --init to review files")
  exit()

queue = TGTQueueDB(MANIFEST_PATH)
first_time = True

while queue.documents:
    if not first_time:
      queue.write()
    else:
      first_time = False
    doc = queue.documents.pop(0)
    fp = LOCAL_FOLDER.joinpath(doc.filename)
    if not fp.is_file():
      print(f"Expected to find {fp.name} locally... Skipping")
      continue
    print(f"Opening {fp.name}...")
    system_open(fp)
    # We defer all the below imports until after the above system_open call
    # so that the user isn't left waiting and can begin reviewing `fp`
    # immediately.  While their PDF viewer is opening up, we do the below
    # loading "in the background"
    # Yes, this means we're importing every iteration of the loop, but that's
    # okay because python will only actually import the module once.
    # Subsequent imports load the module from the module cache.
    from gdrive_base import DRIVE_LINK
    import gdrive
    with yaspin(text="Processing..."):
      from pdfutils import get_page_count
      from tag_predictor import (
        TagPredictor,
      )
      if predictor is None:
        predictor = TagPredictor.load()
      gf = gdrive.gcache.get_item(doc.gid)
      if not gf:
        raise ValueError(f"Unable to load Google File with id=\"{doc.gid}\"")
      parent = gdrive.gcache.get_item(gf['parent_id'])
      if REMOTE_FOLDER != gf['parent_id'] and parent['name'] != REMOTE_FOLDER_NAME:
        print("\nFile moved already! Moving on...")
        fp.unlink()
        continue
      pagecount = None
      text = load_normalized_text_for_file(fp, gf['id'])
      if fp.suffix.lower() == '.pdf':
        pagecount = get_page_count(fp)
      else:
        pagecount = -(len(text)//-1700)
      glink = DRIVE_LINK.format(gf['id'])
      from tag_predictor import normalize_text
      # TODO: pull the course from the parent_id for autosorted PDFs
      # and only load the predictor for EPUBs
      course = predictor.predict(
        [text + ''.join([' ', normalize_text(gf['name'][:-4])]*3)],
        normalized=True,
      )[0] + "/unread"
    from strutils import flush_input
    flush_input()
    course = gdrive.input_course_string_with_tab_complete(prefill=course)
    if course == "trash":
        gdrive.log_move_reason(
          gf['id'],
          old_parent_id=gf.get('parent_id'),
          new_parent_id='trash',
          reason=input("Reason for trashing: "),
        )
        print("Trashing...")
        gdrive.gcache.trash_file(gf['id'])
        fp.unlink()
    elif course == "to-merge":
        import shutil
        gfolder = gdrive.get_gfolders_for_course(course)
        assert not gfolder[0]
        assert gfolder[1]
        gdrive.log_move_reason(
          gf['id'],
          new_parent_id=gfolder[1],
          old_parent_id=gf.get('parent_id', REMOTE_FOLDER),
          reason="partial file",
        )
        gdrive.move_gfile(glink, gfolder)
        shutil.move(fp, LOCAL_MERGE_FOLDER)
    elif course == "to-split":
        import shutil
        gfolder = gdrive.get_gfolders_for_course(course)
        assert not gfolder[0]
        assert gfolder[1]
        gdrive.log_move_reason(
          gf['id'],
          new_parent_id=gfolder[1],
          old_parent_id=gf.get('parent_id', REMOTE_FOLDER),
          reason="editted volume",
        )
        gdrive.move_gfile(glink, gfolder)
        shutil.move(fp, LOCAL_SPLIT_FOLDER)
    else:
        gfolder = gdrive.get_gfolders_for_course(course)
        is_unr_or_arc = 'unre' in course.lower() or 'archiv' in course.lower()
        # only ask for more info if isn't unread or archive
        tags = []
        description: str = ""
        if not is_unr_or_arc:
          print("tags:")
          while True:
            tag = gdrive.input_course_string_with_tab_complete("  - ")
            if not tag:
              break
            tags.append(tag)
          description = input("Any notes on this move? ").strip()
        if len(description) == 0:
          description = "Preliminary sort"
        gdrive.log_move_reason(
          gf['id'],
          new_parent_id=gfolder[0] or gfolder[1],
          old_parent_id=gf.get('parent_id', REMOTE_FOLDER),
          reason=description,
          alternate_tags=tags,
        )
        if gfolder[0]: # sharing publicly
          # JIT importing for efficiency
          from openaleximporter import (
            prompt_for_work,
            make_library_entry_for_work,
          )
          query = fp.stem.replace("_text", "").split(" -")[0]
          work, _ = prompt_for_work(query.replace("_", " "))
          if work:
            gdrive.move_gfile(glink, gfolder)
            filepath = make_library_entry_for_work(work, course=course, glink=glink, pagecount=pagecount, tags=tags, description=description)
            print(f"\nOpening {filepath}\n")
            system_open(filepath)
            fp.unlink()
            exit(0)
          else:
            print(f"\n\t{glink}\n")
            input("Press enter to move the file and continue with the next one...")
        gdrive.move_gfile(glink, gfolder)
        fp.unlink()
    print("")

