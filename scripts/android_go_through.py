#!/bin/python3
from yaspin import yaspin
with yaspin(text="Initializing..."):
  from strutils import (
    Path,
    git_root_folder,
    system_open,
    md5,
    file_info,
    input_with_prefill,
  )
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
  
  predictor= None
  LOCAL_FOLDER: Path
  LOCAL_FOLDER = cli_args.local_folder
  if not LOCAL_FOLDER.is_dir() and not cli_args.init:
    raise ValueError(f"{str(LOCAL_FOLDER)} is not a valid directory.")
  # TODO: parameterize these as well?
  LOCAL_MERGE_FOLDER = git_root_folder.joinpath("../To Merge/")
  LOCAL_SPLIT_FOLDER = git_root_folder.joinpath("../To Split/")
  REMOTE_FOLDER = "1PXmhvbReaRdcuMdSTuiHuWqoxx-CqRa2"
  REMOTE_FOLDER_NAME = "📥 To Go Through"
  local_files = [f for f in LOCAL_FOLDER.iterdir() if f.is_file()]

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

if cli_args.init:
  print(f"Setting up '{LOCAL_FOLDER}' as inbox folder...")
  import json
  import gdrive
  drive_folders = json.loads(gdrive.FOLDERS_DATA_FILE.read_text())
  private_folder_slugs = {
    gdrive.folderlink_to_id(drive_folders[k]['private']): k
    for k in drive_folders
  }
  public_folder_slugs = {
    gdrive.folderlink_to_id(drive_folders[k]['public']): k
    for k in drive_folders
  }
  folder_slugs = {**private_folder_slugs, **public_folder_slugs}
  from bulk_import import (
    get_all_predictable_unread_folders,
    all_folders_with_name_by_course,
    get_or_create_autopdf_folder_for_course,
    TagPredictor,
    tqdm_thread_map,
  )
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
  remote_files_by_name = dict()
  for gfile in remote_children:
    assert gfile['name'] not in remote_files_by_name, f"Found duplicate file name \"{gfile['name']}\""
    remote_files_by_name[gfile['name']] = gfile
  from tqdm import tqdm
  print(f"# Removing local duplicates...")
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
      remote_file = gdrive.remote_file_for_local_file(
        fp,
        folder_slugs,
        default_folder_id=REMOTE_FOLDER,
      )
    if not remote_file:
      raise ValueError(f"Failed to upload \"{fp.name}\"")
    if remote_file['parent_id'] in remote_folder_ids:
      if fp.name != remote_file['name']:
        msg = (
          f"Found\n  \"{fp.name}\"\n"
          "in the remote folder, but there it's called\n"
          f"  \"{remote_file['name']}\"\n"
          "Renaming the remote to the local name..."
        )
        tqdm.write(msg)
        gdrive.gcache.rename_file(remote_file['id'], fp.name)
        remote_file['name'] = fp.name
      remote_files_by_name[fp.name] = remote_file
      remote_ids_seen.add(remote_file['id'])
      local_filenames_seen.add(fp.name)
    else:
      tqdm.write(f"    Deleting already sorted {fp.name}")
      # fp.unlink()
      # For now just move it out to be on the safe side...
      fp.rename(fp.parent.joinpath('../../Download/').joinpath(fp.name))
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
        gdrive.gcache.trash_file(child['id'])
        continue
      gdrive.gcache.rename_file(child['id'], name)
    tqdm.write(f"Downloading '{name}' ({round(child['size']/1000000, 2)} MB)...")
    dest_file = LOCAL_FOLDER.joinpath(name)
    gdrive.download_file(
      child['id'],
      destination=dest_file,
      verbose=False,
    )
    local_files.append(dest_file)
    local_filenames_seen.add(name)
  del remote_children
  import random
  # randomize for more accurate tqdm est
  local_files.sort(key=lambda f: random.random())
  print("# Extracting text from files...")
  from tag_predictor import NORMALIZED_TEXT_FOLDER, normalize_text
  def extract_text_from(fp):
    if fp.suffix.lower() not in ['.pdf', '.epub']:
      return # Don't even bother trying
    gid = remote_files_by_name[fp.name]['id']
    # Short circuit actually reading the file as existance is good enough here
    if NORMALIZED_TEXT_FOLDER.joinpath(gid+'.pkl').exists():
      return
    load_normalized_text_for_file(fp, gid)
  tqdm_thread_map(extract_text_from, local_files, max_workers=4, unit="f")
  del remote_files_by_name
  print("# Sorting PDFs into bulk import folders...")
  children = gdrive.gcache.sql_query(
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
    gdrive.gcache.move_file(
      child['id'],
      new_folder,
      [REMOTE_FOLDER],
      verbose=False,
    )
  tqdm_thread_map(sort_pdf_file, children, max_workers=8, unit="f")
  print("Done setting up local folder! Run again without --init to review files")
  exit()

local_files.sort(
  key=lambda f: -f.stat().st_size, # Largest first
)
for fp in local_files:
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
      gfs = gdrive.gcache.files_exactly_named(fp.name)
      gf = None
      if not gfs:
        print("File not found on drive with that name. Please rerun this script with --init")
        exit(1)
      if len(gfs) == 1:
        gf = gfs[0]
        parent = gdrive.gcache.get_item(gf['parent_id'])
        if REMOTE_FOLDER != gf['parent_id'] and parent['name'] != REMOTE_FOLDER_NAME:
          print("\nFile moved already! Moving on...")
          fp.unlink()
          continue
      else: # len(gfs) > 1
        tgt_md5 = md5(fp)
        for f in gfs:
          if f['md5Checksum'] == tgt_md5:
            if REMOTE_FOLDER == f['parent_id']:
              gf = f
              break
            parent = gdrive.gcache.get_item(f['parent_id'])
            if parent['name'] == REMOTE_FOLDER_NAME:
              gf = f
              break
        moved_already = False
        if gf is None:
          if any(f['md5Checksum'] == tgt_md5 for f in gfs):
            moved_already = True
          else:
            raise NotImplementedError(f"Unable to find \"{fp.name}\" remotely by MD5, only by name.")
        else:
          for f in gfs:
            if f['id'] == gf['id']:
              continue
            if f['md5Checksum'] == tgt_md5:
              parent = gdrive.gcache.get_item(f['parent_id'])
              if REMOTE_FOLDER == f['parent_id'] or parent['name'] == REMOTE_FOLDER_NAME:
                print("\nFound duplicate file in remote TGT folder. Deleting it...")
                gdrive.gcache.trash_file(f['id'])
              else:
                moved_already = True
        if moved_already:
          print("\nFile moved already! Moving on...")
          gdrive.gcache.trash_file(gf['id'])
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
      course = predictor.predict(
        [text + ''.join([' ', normalize_text(gf['name'][:-4])]*3)],
        normalized=True,
      )[0] + "/unread"
    course = gdrive.input_course_string_with_tab_complete(prefill=course)
    if course == "trash":
        print("Trashing...")
        gdrive.gcache.trash_file(gf['id'])
        fp.unlink()
    elif course == "to-merge":
        import shutil
        gfolder = gdrive.get_gfolders_for_course(course)
        gdrive.move_gfile(glink, gfolder)
        shutil.move(fp, LOCAL_MERGE_FOLDER)
    elif course == "to-split":
        import shutil
        gfolder = gdrive.get_gfolders_for_course(course)
        gdrive.move_gfile(glink, gfolder)
        shutil.move(fp, LOCAL_SPLIT_FOLDER)
    else:
        gfolder = gdrive.get_gfolders_for_course(course)
        if gfolder[0]:
          from openaleximporter import (
            prompt_for_work,
            make_library_entry_for_work,
          )
          query = fp.stem.replace("_text", "").split(" -")[0]
          work, _ = prompt_for_work(query.replace("_", " "))
          if work:
            gdrive.move_gfile(glink, gfolder)
            filepath = make_library_entry_for_work(work, course=course, glink=glink, pagecount=pagecount)
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

