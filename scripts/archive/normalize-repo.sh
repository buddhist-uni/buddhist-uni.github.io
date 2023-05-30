#!/bin/bash
# Ensures all html and md files are in NFC Normalized Unicode (as some fonts cannot handle combining characters)
if [ -f tmp ]; then
    echo tmp file already exists!
    exit 1
fi
echo "Importing..."
if ! command -v uconv; then
    echo "Please install the uconv command"
    exit 1
fi

echo ""

readarray -t tracked_files < <(git ls-tree --name-only --full-tree -r HEAD)

for file in "${tracked_files[@]}"; do
    if [ -f "$file" ]; then
        if [[ "$file" == *.html ]] || [[ "$file" == *.md ]]
        then
            echo Analyzing "$file"...
            uconv -x Any-NFC "$file" > tmp
            if cmp --silent tmp "$file"; then
                rm tmp
            else
                mv -f tmp "$file"
                echo Changed "$file"!
            fi
        fi
    else
        echo "Found a file, '$file', that does not exist! You (re)moved a previously tracked file?"
    fi
done

