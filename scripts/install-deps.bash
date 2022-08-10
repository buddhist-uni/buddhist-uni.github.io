#!/bin/bash

# Make sure to run:
# npm install --no-bin-links OR npm ci
# before running this script

rm -rf assets/webfonts && \
  mkdir assets/webfonts && \
  cp node_modules/@fortawesome/fontawesome-free/webfonts/* assets/webfonts/ 

md5sum package-lock.json assets/css/*.scss _sass/*.scss _sass/minima/* | md5sum | head -c 7 > _data/cssCacheToken.yml
