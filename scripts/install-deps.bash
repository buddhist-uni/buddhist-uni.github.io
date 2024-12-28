#!/bin/bash

# Installs misc (non-gem) dependencies for the Jekyll build
# Make sure to:
#   1) run `npm install --no-bin-links` OR `npm ci`
#      BEFORE running this script
#   2) run this script from the root of the repo

rm -rf assets/webfonts && \
  mkdir assets/webfonts && \
  cp node_modules/@fortawesome/fontawesome-free/webfonts/* assets/webfonts/ 

wget https://buddhistuniversity.net/analytics/content/download_counts.json --output-document="_data/content_downloads.json"

md5sum package-lock.json assets/css/*.scss _sass/*.scss _sass/minima/* _layouts/* _plugins/addicontips.rb _includes/content_icon.html | md5sum | head -c 7 > _data/cssCacheToken.yml
