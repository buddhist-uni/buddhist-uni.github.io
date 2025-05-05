#!/bin/python3
from yaspin import yaspin
with yaspin(text="Initializing..."):
  from strutils import (
    git_root_folder,
    system_open,
    input_with_tab_complete,
    DelayedKeyboardInterrupt,
  )
  
  course_list = None
  predictor= None
  LOCAL_FOLDER = git_root_folder.joinpath("../To Go Through")
  LOCAL_MERGE_FOLDER = git_root_folder.joinpath("../To Merge/")
  REMOTE_FOLDER = "1PXmhvbReaRdcuMdSTuiHuWqoxx-CqRa2"
  local_files = sorted([f for f in LOCAL_FOLDER.iterdir() if f.is_file()], key=lambda f: -f.stat().st_size)

for fp in local_files:
  print(f"Opening {fp.name}...")
  system_open(fp)
  with yaspin(text="Processing..."):
    import gdrive
    from pdfutils import readpdf, get_page_count
    from epubutils import read_epub
    from tag_predictor import (
      TagPredictor,
      normalize_text,
      save_normalized_text,
    )
    
    if predictor is None:
      course_list = gdrive.get_known_courses()
      predictor = TagPredictor.load()
    gfs = gdrive.files_exactly_named(fp.name)
    gf = None
    if not gfs:
      raise NotImplementedError("File not found on Drive at all.")
    if len(gfs) == 1:
      gf = gfs[0]
      if REMOTE_FOLDER not in f['parents']:
        print("File moved already! Moving on...")
        fp.unlink()
        continue
    else: # len(gfs) > 1
      for f in gfs:
        if REMOTE_FOLDER in f['parents']:
          gf = f
          break
      if gf is None:
        print("File moved already! Moving on...")
        fp.unlink()
        continue
      tgt_md5 = gf['md5Checksum']
      trash_it = False
      for f in gfs:
        if f['id'] == gf['id']:
          continue
        if f['md5Checksum'] == tgt_md5:
          if REMOTE_FOLDER in f['parents']:
            print("Found duplicate file in remote TGT folder. Deleting it...")
            gdrive.trash_drive_file(f['id'])
          else:
            trash_it = True
      if trash_it:
        print("File moved already! Moving on...")
        gdrive.trash_drive_file(gf['id'])
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
    glink = gdrive.DRIVE_LINK.format(gf['id'])
    course = predictor.predict([text], normalized=True)[0] + "/unread"
  course = input_with_tab_complete("course: ", course_list, prefill=course)
  if course == "trash":
      print("Trashing...")
      gdrive.trash_drive_file(gf['id'])
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

