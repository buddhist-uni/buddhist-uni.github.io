from gdrive import move_drive_file, link_to_id, create_drive_shortcut, get_gfolders_for_course, Path

clientsecrets = Path("~/library-utils-client-secret.json")

def move_gfile(glink, course):
  gfid = link_to_id(glink)
  public_fid, private_fid = get_gfolders_for_course(course)
  file = move_drive_file(clientsecrets, gfid, public_fid or private_fid)
  if public_fid and private_fid:
    print("Creating a private shortcut...")
    create_drive_shortcut(clientsecrets, gfid, file.get('name'), private_fid)
  print("Done!")

if __name__ == "__main__":
  glink = input("Google Drive Link: ")
  course = input("course: ")
  move_gfile(glink, course)
