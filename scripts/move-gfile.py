from gdrive import *
from strutils import input_with_tab_complete

clientsecrets = Path("~/library-utils-client-secret.json")

def move_gfile(glink, folders):
  gfid = link_to_id(glink)
  public_fid, private_fid = folders
  file = move_drive_file(clientsecrets, gfid, public_fid or private_fid)
  shortcuts = get_shortcuts_to_gfile(clientsecrets, gfid)
  if public_fid and private_fid:
    if len(shortcuts) != 1:
      print("Creating a (new, private) shortcut...")
      create_drive_shortcut(clientsecrets, gfid, file.get('name'), private_fid)
    else:
      s=shortcuts[0]
      print(f"Moving existing shortcut from  {FOLDER_LINK.format(s['parents'][0])}  to  {FOLDER_LINK.format(private_fid)}  ...")
      move_drive_file(clientsecrets, s['id'], private_fid, previous_parents=s['parents'])
  else:
    if len(shortcuts) == 1:
      s=shortcuts[0]
      print(f"Trashing the existing shortcut in {FOLDER_LINK.format(s['parents'][0])} ...")
      trash_drive_file(clientsecrets, s['id'])
  if len(shortcuts)>1:
    urls = "     ".join(map(lambda f: FOLDER_LINK.format(f['parents'][0]), shortcuts))
    raise NotImplementedError(f"Please decide what to do with the multiple old shortcuts in:    {urls}")
  print("Done!")

if __name__ == "__main__":
  glinks = []
  while True:
    glink = input("Google Drive Link (None to continue): ")
    if not glink:
      break
    glinks.append(glink)
  course = input_with_tab_complete("course: ", get_known_courses())
  folders = get_gfolders_for_course(course)
  for glink in glinks:
    move_gfile(glink, folders)
