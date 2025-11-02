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
