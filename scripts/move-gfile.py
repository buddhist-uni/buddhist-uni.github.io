from gdrive import *

clientsecrets = Path("~/library-utils-client-secret.json")

def move_gfile(glink, course):
  gfid = link_to_id(glink)
  public_fid, private_fid = get_gfolders_for_course(course)
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
  glink = input("Google Drive Link: ")
  course = input("course: ")
  move_gfile(glink, course)
