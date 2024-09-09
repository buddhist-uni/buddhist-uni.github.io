#!/bin/bash

whitelist=(
  "ACKNOWLEDGEMENTS.md"
  "CNAME"
  "COLLECTION_POLICY.md"
  "CONTRIBUTING.md"
  "CONTRIBUTORS.md"
  "README.md"
  "README.txt"
  "Gemfile"
  "Gemfile.lock"
  "cssCacheToken.yml"
  ".gitignore"
)
invalid_files=()
exit_code=0
readarray -t tracked_files < <(git diff-tree --no-commit-id --diff-filter=d --diff-merges=1 --name-only -r HEAD)
for file in "${tracked_files[@]}"; do
  if [[ -f "$file" ]]; then
    filename=$(basename "$file")
    # Check if file is whitelisted
    if [[ " ${whitelist[@]} " =~ " $filename " ]]; then
      continue
    fi
    echo "Checking $file..."
    if ! grep -qE '^[+0-9a-z_\.-]+\.(bash|bib|code-workspace|gitignore|html|ico|js|json|liquid|md|png|py|rb|scss|sh|svg|txt|webmanifest|xml|yaml|yml)$' <<< "$filename"; then
      invalid_files+=("$file")
    fi
    if [[ "${file: -3}" == ".md" ]]; then
      first_bytes=$(xxd -p -l 4 "$file")  # Read the first 4 bytes in hexadecimal format

      if [[ $first_bytes != "2d2d2d0a" ]]; then
          echo "Invalid header in file: $file"
          exit_code=1
      fi
    fi
  fi
done
if [[ ${#invalid_files[@]} -gt 0 ]]; then
  echo "Invalid characters found in the following files:"
  for file in "${invalid_files[@]}"; do
    echo "$file"
  done
  exit 1
else
  echo "All files have valid names."
  exit $exit_code
fi