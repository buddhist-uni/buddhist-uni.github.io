#!/bin/bash
# Ensures all html and md files are in NFC Normalized Unicode (as our chosen font, Garamond, cannot handle combining characters)
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

for file in `git ls-tree --name-only --full-tree -r HEAD`; do
    if [ -f $file ]; then
        if [[ $file == *.html ]] || [[ $file == *.md ]]
        then
            echo Analyzing "$file"...
            uconv -x Any-NFC $file > tmp
            if cmp --silent tmp "$file"; then
                rm tmp
            else
                mv -f tmp $file
                echo Changed "$file"!
            fi
        fi
    else
        echo 'Found a file, "$file", that does not exist! Maybe whitespace in a filename? Or you (re)moved a previously tracked file?'
    fi
done

