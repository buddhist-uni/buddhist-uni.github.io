#!/bin/bash
category=av
subcat=podcast
cd $(git rev-parse --show-toplevel)/_content/$category/
for fd in *.md; do
  read -p "Is $fd a $subcat? [y|N] " ISIT
  if [ "$ISIT" = "y" ]; then
    printf "2\na\nsubcat: $subcat\n.\nw\nq" | red -s "$fd"
  fi
done

qpdf --empty --pages  "1.pdf" '1-z' "2.pdf" '2-z' "3.pdf" '2-z' "4.pdf" '2-z' "5.pdf" '2-z' "6.pdf" '2-z' "7.pdf" '2-z' "8.pdf" '2-z' "9.pdf" '2-z' "10.pdf" '2-z' "11.pdf" '2-z' -- 'out.pdf'