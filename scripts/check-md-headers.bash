#!/bin/bash

whitelist=("CONTRIBUTING.md" "CONTRIBUTORS.md" "README.md")

check_file() {
    file="$1"
    first_bytes=$(xxd -p -l 4 "$file")  # Read the first 4 bytes in hexadecimal format

    if [[ $first_bytes != "2d2d2d0a" ]]; then
        echo "Invalid header in file: $file"
        exit_code=1
    fi
}

exit_code=0  # Initialize the exit code

cd $(git rev-parse --show-toplevel)

# Iterate through Git-tracked files
while IFS= read -r file; do
    if [[ "${whitelist[*]}" =~ "${file}" ]]; then
        :
    elif [[ "${file: -3}" == ".md" ]]; then
        check_file "$file"
    fi
done < <(git ls-files)

exit $exit_code
