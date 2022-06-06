#!/bin/bash

# Make sure to run:
# npm install --no-bin-links
# before running this script

mkdir -p assets/webfonts && \
  cp node_modules/@fortawesome/fontawesome-free/webfonts/* assets/webfonts/ 
