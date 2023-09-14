import os
import re
import glob

def modify_markdown(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    modified_lines = []
    previous_line_empty = False
    modification_needed = False

    for line in lines:
        if line.strip() == "":
            previous_line_empty = True
            modified_lines.append(line)
        elif previous_line_empty and re.match(r'^> [a-z]', line) and not line.endswith("  \n"):
            modified_lines.append("> … " + line[2:])
            previous_line_empty = False
            modification_needed = True
        else:
            modified_lines.append(line)
            previous_line_empty = False

    if modification_needed:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(modified_lines)
        print(f"  Modified")
    else:
        print(f"  No changes needed")

def process_all_markdown_files():
    root_dir = "./"  # Replace this with the root directory of your Git repository

    markdown_files = glob.glob(os.path.join(root_dir, "**/*.md"), recursive=True)
    total_files = len(markdown_files)
    print(f"Total Markdown files found: {total_files}")

    for idx, file_path in enumerate(markdown_files, 1):
        print(f"Processing file {idx}/{total_files}: {file_path}")
        modify_markdown(file_path)

if __name__ == "__main__":
    process_all_markdown_files()
    print("Markdown modification complete!")
