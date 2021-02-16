#!/bin/bash
for file in `git ls-tree --name-only --full-tree -r HEAD`; do
    if [[ $file == *.html ]] || [[ $file == *.md ]]
    then
        echo Normalizing "$file"...
        uconv -x Any-NFC $file > tmp
        mv -f tmp $file
    fi
done

