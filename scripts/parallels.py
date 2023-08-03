import os
import requests
from strutils import naturally_sorted

data_directory = "./_content/canon"

def get_parallels_yaml(sutta_id):
    response = requests.get("https://suttacentral.net/api/parallels/" + sutta_id)
    if response.status_code != 200:
        print("  SC network error!")
        quit(1)
    return parallels_data_to_yaml(response.json())

def parallels_data_to_yaml(data):
    if not data:
       return ""
    from_uid = next(iter(data)).split("#")[0]
    full_parallels = set(item['to']['uid'] for item in data.get(from_uid, []))
    all_parallels = sum(data.values(), [])
    all_parallels = set(item['to']['uid'] for item in all_parallels)
    partial_parallels = all_parallels - full_parallels
    if len(all_parallels) == 0:
        return ""
    ret = "parallels:"
    if len(full_parallels) == 0:
        ret += " []"
    for p in naturally_sorted(full_parallels):
        ret += "\n  - " + p
    if len(partial_parallels) > 0:
        ret += "\n# Partial parallels from SC"
    for p in naturally_sorted(partial_parallels):
        ret += "\n#  - " + p
    return ret

def add_parallels_to_file(file_path, new_yaml_data):
    with open(file_path, 'r') as f:
        content = f.read()
    if content.find("\nparallels:") > 0:
        print(f"  {file_path} already contains parallels! Skipping.")
        return False
    yaml_end = content.find("\n---\n", 3)
    if yaml_end <= 10:
        print("  Error! No yaml end mark found")
        quit(1)
    try:
      with open(file_path, 'w') as f:
        f.write(content[:yaml_end] + '\n' + new_yaml_data + content[yaml_end:])
    except:
      print("  Failed to write to file!")
      quit(1)
    return True

if __name__ == "__main__":
    for file_name in os.listdir(data_directory):
        if file_name.endswith(".md"):
            file_path = os.path.join(data_directory, file_name)
            sutta_id = os.path.splitext(file_name)[0]
            print(f"Getting parallels for {sutta_id}...")
            yaml = get_parallels_yaml(sutta_id)
            if not yaml:
                print(f"  No parallels")
            else:
                if add_parallels_to_file(file_path, yaml):
                    print(f"  modified {file_path}")
