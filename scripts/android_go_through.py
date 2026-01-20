#!/bin/python3
from yaspin import yaspin
with yaspin(text="Initializing..."):
  from strutils import (
    Path,
    git_root_folder,
    system_open,
    DelayedKeyboardInterrupt,
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
  # TODO: add link to split folder as well?
  LOCAL_MERGE_FOLDER = git_root_folder.joinpath("../To Merge/")
  REMOTE_FOLDER = "1PXmhvbReaRdcuMdSTuiHuWqoxx-CqRa2"
  local_files = sorted(
    [f for f in LOCAL_FOLDER.iterdir() if f.is_file()],
    key=lambda f: -f.stat().st_size, # Largest first
  )

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
  with DelayedKeyboardInterrupt():
    if fp.suffix.lower() == '.pdf':
      text = readpdf(fp)
    elif fp.suffix.lower() == '.epub':
      text = read_epub(fp)
    # If you ever teach me how to read another file type,
    # please tell clean_google_drive's pickle filter about the new extension
    else:
      print(f"Warning! Dunno how to read a {fp.suffix} file!")
      return normalize_text(fp.stem)
    text = normalize_text(text)
    save_normalized_text(gf['id'], text)
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
  from tqdm import tqdm
  print(f"  Ensuring all local files are already on Drive and are unsorted...")
  pbar = tqdm(local_files, unit="file", desc="  ")
  remote_files_seen = set()
  id_for_path = dict()
  for fp in pbar:
    remote_file = gdrive.remote_file_for_local_file(fp, folder_slugs, default_folder_id=REMOTE_FOLDER)
    if not remote_file:
      raise ValueError(f"Failed to find / upload {fp.name} ?")
    if remote_file['parent_id'] == REMOTE_FOLDER:
      remote_files_seen.add(remote_file['id'])
      id_for_path[fp.name] = remote_file['id']
    else:
      pbar.write(f"    Deleting already sorted {fp.name}")
      # fp.unlink()
      # For now just move to be on the safe side...
      fp.rename(fp.parent.joinpath('../../Download/').joinpath(fp.name))
  print(f"  Ensuring all remote files are downloaded locally...")
  children = tqdm(gdrive.gcache.sql_query(
    "parent_id = ? AND mime_type != ? AND shortcut_target IS NULL AND mime_type != ?",
    (REMOTE_FOLDER, 'application/vnd.google-apps.folder', 'application/vnd.google-apps.document', )
  ), unit="file", desc="Downloading")
  for child in children:
    if child['id'] in remote_files_seen:
      continue
    name = child['name'] 
    if name in id_for_path:
      print(f"We already downloaded {gdrive.DRIVE_LINK.format(id_for_path[name])} to '{name}'.\nPlease decide on a new, unique name for {gdrive.DRIVE_LINK.format(child['id'])}")
      name = input_with_prefill('name (or trash): ', name)
      if not name or name == 'trash':
        print("Trashing...")
        gdrive.gcache.trash_file(child['id'])
        continue
      gdrive.gcache.rename_file(child['id'], name)
    children.write(f"Downloading '{name}' ({round(child['size']/1000000, 2)} MB)...")
    gdrive.download_file(
      child['id'],
      destination=LOCAL_FOLDER.joinpath(name),
      verbose=False,
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
        raise NotImplementedError("File not found on Drive at all.")
      if len(gfs) == 1:
        gf = gfs[0]
        if REMOTE_FOLDER != gf['parent_id']:
          print("\nFile moved already! Moving on...")
          fp.unlink()
          continue
      else: # len(gfs) > 1
        tgt_md5 = md5(fp)
        for f in gfs:
          if REMOTE_FOLDER == f['parent_id'] and f['md5_checksum'] == tgt_md5:
            gf = f
            break
        if gf is None:
          raise NotImplementedError("No md5 match found in the TGT folder.")
        trash_it = False
        for f in gfs:
          if f['id'] == gf['id']:
            continue
          if f['md5_checksum'] == tgt_md5:
            if REMOTE_FOLDER == f['parent_id']:
              print("\nFound duplicate file in remote TGT folder. Deleting it...")
              gdrive.gcache.trash_file(f['id'])
            else:
              trash_it = True
        if trash_it:
          print("\nFile moved already! Moving on...")
          gdrive.gcache.trash_file(gf['id'])
          fp.unlink()
          continue
      pagecount = None
      text = load_normalized_text_for_file(fp, gf['id'])
      if fp.suffix.lower() == '.pdf':
        pagecount = get_page_count(fp)
      else:
        pagecount = -(len(text)//-1800)
      glink = DRIVE_LINK.format(gf['id'])
      course = predictor.predict([text], normalized=True)[0] + "/unread"
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

