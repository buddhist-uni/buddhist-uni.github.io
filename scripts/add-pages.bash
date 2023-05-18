#!/bin/bash
category=canon
field=pages
cd $(git rev-parse --show-toplevel)/_content/$category/
for fd in *.md; do
  echo "$fd..."
  val=$(cat $fd | sed -nr "s/.*${field}: (.*)$/\1/p")
  if [[ ! -z "$val" ]]; then
    printf "  already has $field value $val\n  skipping\n"
    continue
  fi
  val=$(cat $fd | sed -nr "s/.*minutes: (.*)$/\1/p")
  if [[ ! -z "$val" ]]; then
    printf "  already has minutes value $val\n  skipping\n"
    continue
  fi
  url=$(cat $fd | sed -nr 's/.*drive\.google\.com\/file\/d\/([^"%?#\/]+).*/https:\/\/drive\.google\.com\/file\/d\/\1/p' | head -1)
  if [[ -z "$url" ]]; then
    url=$(cat $fd  | sed -nr 's/^external_url: \"*([^"]*)\"*.*$/\1/p')
  fi
  if [[ -z "$url" ]]; then
    echo "  has no valid url"
    termux-open "$fd"
    continue
  fi
  termux-open "$url"
  # echo "  downloading $url..."
  # gdown "$url" -O temp.pdf # gdown needs gdrive file id not url
  read -p "  $field:  " val
  # val=$(exiftool -n -p '$PageCount' temp.pdf)
  if [[ -z "$val" ]]; then
    #val=$(echo "$(exiftool -n -p '$Duration' temp.pdf) / 60" | bc)
    #rm temp.pdf
    #if [[ -z "$val" ]]; then
     # echo "  unknow value"
     # termux-open "$fd"
     # continue
   # fi
   # echo "  adding minutes: $val"
   # sed -e '1h;2,$H;$!d;g' -e "s/\n---\n/\nminutes: $val\n---\n/g" -i "$fd"
   # echo "  done"
    echo "  skipping"
    continue
  fi
  # rm temp.pdf
  echo "  adding pages: $val"
  sed -e '1h;2,$H;$!d;g' -e "s/\n---\n/\n$field: $val\n---\n/g" -i "$fd"
  echo "  done"
done

