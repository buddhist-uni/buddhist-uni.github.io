#!/bin/python3
from yaspin import yaspin
with yaspin(text="Initializing..."):
  from strutils import (
    git_root_folder,
    system_open,
    DelayedKeyboardInterrupt,
    md5,
  )
  
  predictor= None
  LOCAL_FOLDER = git_root_folder.joinpath("../To Go Through")
  LOCAL_MERGE_FOLDER = git_root_folder.joinpath("../To Merge/")
  REMOTE_FOLDER = "1PXmhvbReaRdcuMdSTuiHuWqoxx-CqRa2"
  local_files = sorted([f for f in LOCAL_FOLDER.iterdir() if f.is_file()], key=lambda f: -f.stat().st_size)
  from gdrive_base import DRIVE_LINK

for fp in local_files:
    print(f"Opening {fp.name}...")
    system_open(fp)
    import gdrive
    with yaspin(text="Processing..."):
      from pdfutils import readpdf, get_page_count
      from epubutils import read_epub
      from tag_predictor import (
        TagPredictor,
        normalize_text,
        save_normalized_text,
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
      text = ''
      with DelayedKeyboardInterrupt():
        if fp.suffix.lower() == '.pdf':
          text = readpdf(fp)
          pagecount = get_page_count(fp)
        elif fp.suffix.lower() == '.epub':
          text = read_epub(fp)
          pagecount = -(len(text)//-2200)
        else:
          print(f"Warning! Dunno how to read a {fp.suffix} file!")
          text = fp.stem
        text = normalize_text(text)
        save_normalized_text(gf['id'], text)
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

