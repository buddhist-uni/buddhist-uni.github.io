#!/bin/python3
from yaspin import yaspin
with yaspin(text="Initializing..."):
  from strutils import (
    git_root_folder,
    system_open,
    input_with_tab_complete,
  )
  import gdrive
  from pdfutils import readpdf
  from epubutils import read_epub
  from tag_predictor import (
    TagPredictor,
    normalize_text,
    save_normalized_text,
  )
  
  course_list = None
  predictor= None
  LOCAL_FOLDER = git_root_folder.joinpath("../To Go Through")
  REMOTE_FOLDER = "16-z8CRbEfo3L8DTUpR76Sq1uCs4Am5b_"
  local_files = sorted([f for f in LOCAL_FOLDER.iterdir() if f.is_file()], key=lambda f: -f.stat().st_size)

for fp in local_files:
  print(f"Opening {fp.name}...")
  system_open(fp)
  with yaspin(text="Processing..."):
    if predictor is None:
      course_list = gdrive.get_known_courses()
      predictor = TagPredictor.load()
    gfs = gdrive.files_exactly_named(fp.name)
    gf = None
    for f in gfs:
      if REMOTE_FOLDER in f['parents']:
        gf = f
        break
    if gfs and not gf:
      print("File moved already! Moving on...")
      fp.unlink()
      continue
    if not gfs:
      raise NotImplementedError("File not found on Drive at all.")
    if fp.suffix.lower() == '.pdf':
      text = readpdf(fp)
    elif fp.suffix.lower() == '.epub':
      text = read_epub(fp)
    else:
      print(f"Warning! Dunno how to read a {fp.suffix} file!")
      text = fp.stem
    text = normalize_text(text)
    save_normalized_text(gf['id'], text)
    course = predictor.predict([text], normalized=True)[0] + "/unread"
  course = input_with_tab_complete("course: ", course_list, prefill=course)
  gfolder = gdrive.get_gfolders_for_course(course)
  gdrive.move_gfile(gdrive.DRIVE_LINK.format(gf['id']), gfolder)
  print("")
  fp.unlink()
