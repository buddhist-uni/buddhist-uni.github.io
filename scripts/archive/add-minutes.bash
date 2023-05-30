#!/bin/bash
category=av
field=minutes
cd $(git rev-parse --show-toplevel)/_content/$category/
for fd in *.md; do
  echo "$fd..."
  val=$(cat $fd | sed -nr "s/.*${field}: (.*)$/\1/p")
  if [[ ! -z "$val" ]]; then
    printf "  already has $field value $val\n  skipping\n"
    continue
  fi
  url=$(cat $fd  | sed -nr 's/^external_url: \"*([^"]*)\"*.*$/\1/p')
  if [[ -z "$url" ]]; then
    url=$(cat $fd | sed -nr 's/.*drive\.google\.com\/([^"]+).*/https:\/\/drive.google.com\/\1/p' | head -1)
  fi
  if [[ -z "$url" ]]; then
    echo "  has no valid url"
    continue
  fi
  echo "  opening $url in edge..."
  wslview $url
  read -p "  $field:  " val
  if [[ -z "$val" ]]; then
    echo "  skipping"
    continue
  fi
  sed -e '1h;2,$H;$!d;g' -e "s/\n---\n/\n$field: $val\n---\n/g" -i "$fd"
  echo "  done"
done

