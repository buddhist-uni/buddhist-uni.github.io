The Data Files in this directory are config files used for building the site.

*.yml files are site settings
*.json files contain data from:

SuttaCentral
------------
The *-blurbs_root-en.json files are downloaded raw from https://github.com/suttacentral/bilara-data/tree/published/root/en/blurb
These files don't update often, but should periodically (yearly?) be synced with their upstream versions.

TheSunShade / Readingfaithfully
-------------------------------
The accesstoinsight, dhammatalks and suttafriends json files are reformatted versions of the json data embedded here: https://github.com/thesunshade/citation-helper/tree/main/src/webSites
DhammaTalks will regularly add new content so that file needs periodic manual syncing.

Note that (for now) the SuttaCentral Blurb Data and Citation Helper Data are currently only being used by the Python importers in the `scripts` directory and are not used by Jekyll.

Google Drive
------------
The drive_folders.json file is a manually maintained map of links to the folders on drive behind each published and planned tag.
