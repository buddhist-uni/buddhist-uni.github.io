#!/bin/python3

# This file is to be run by https://github.com/buddhist-uni/analytics/blob/main/.github/workflows/archive.yaml

import json
import yaml

import website

from strutils import fully_encode_url, git_root_folder

website.load()

# Update content_paths.json
selfhosted = [c for c in website.content if c.file_links]
newlinks_to_content_paths = dict()
for c in selfhosted:
  for l in c.file_links:
    newlinks_to_content_paths[
      fully_encode_url(website.data.content['filehost']+l)
    ] = c.content_path
links_to_paths = json.loads(
  git_root_folder.joinpath('../analytics/data/content_paths.json').read_text()
)
links_to_paths.update(newlinks_to_content_paths)
json.dump(
  links_to_paths,
  open(str(git_root_folder.joinpath('../analytics/data/content_paths.json')), 'w'),
  indent=2,
  sort_keys=True,
)

# Update metadata.yaml
metadata = yaml.safe_load(
  git_root_folder.joinpath('../analytics/data/metadata.yaml').read_text()
)
metadata['content_buckets'] = website.data.content['valid_buckets']
yaml.dump(
  metadata,
  open(str(git_root_folder.joinpath('../analytics/data/metadata.yaml')), 'w'),
  indent=2,
  sort_keys=True,
)
