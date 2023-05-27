#!/bin/bash

whitelist=(
  "ACKNOWLEDGEMENTS.md"
  "CNAME"
  "COLLECTION_POLICY.md"
  "CONTRIBUTING.md"
  "CONTRIBUTORS.md"
  "README.md"
  "Gemfile"
  "Gemfile.lock"
  "_data/cssCacheToken.yml"
)

invalid_files=()

# Get tracked files using git ls-files and store them in an array
readarray -t tracked_files < <(git diff-tree --no-commit-id --diff-filter=d --diff-merges=1 --name-only -r HEAD)

for file in "${tracked_files[@]}"; do
  if [[ -f "$file" ]]; then
    filename=$(basename "$file")
    # Check if file is whitelisted
    if [[ " ${whitelist[@]} " =~ " $filename " ]]; then
      continue
    fi
    echo "Checking $file..."
    if ! grep -qE '^[+0-9a-z_\.-]+$' <<< "$filename"; then
      invalid_files+=("$file")
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
  exit 0
fi
