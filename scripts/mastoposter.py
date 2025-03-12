#!/bin/python
# Posts the next piece of content to Mastodon

from datetime import datetime
import json
from mastodon import Mastodon
import tweepy
import re
import os
from urllib.parse import urlparse

import gdrive

from atproto_client import Client as BskyClient
from atproto import models as BskyModels
BskyLinkCard = BskyModels.AppBskyEmbedExternal.Main
BskyLinkDetails = BskyModels.AppBskyEmbedExternal.External
BskyTextFacet = BskyModels.AppBskyRichtextFacet.Main
BskyHashtag = BskyModels.AppBskyRichtextFacet.Tag
BskyByteRange = BskyModels.AppBskyRichtextFacet.ByteSlice

import website

def create_bsky_embed(page: website.ContentFile) -> BskyLinkCard:
  return BskyLinkCard(
    external=BskyLinkDetails(
      title=page.title.replace('*', ''),
      description=page.content.lstrip().split("\n\n")[0].rstrip(),
      uri=website.baseurl+page.url,
    )
  )

def hashtag_facets_for_text(text: str) -> list[BskyTextFacet]:
  ret = []
  tbytes = text.encode()
  # The `index` takes byte ranges
  # so we have to handle the string as bytes
  # rather than as a unicode string
  for t in re.finditer(rb"#(\w+)", tbytes):
    ret.append(BskyTextFacet(
      features=[BskyHashtag(tag=t.group(1).decode())],
      index=BskyByteRange(byteStart=t.start(), byteEnd=t.end())
    ))
  return ret

def write_post_title(page: website.ContentFile) -> str:
  title = page.title
  if ": " in title:
    title = title.split(': ')[-1]
  return title

def length_of_item(page) -> str:
  length = ""
  if page.minutes:
    length = f", {page.minutes}-minute "
  elif page.pages:
    if isinstance(page.pages, str) and "--" in page.pages:
        pages = page.pages.split("--")
        pages = int(pages[1]) - int(pages[0]) + 1
    else:
      pages = int(page.pages)
    length = f", {pages}-page "
  else:
    length = " "
  return length

def get_category_for_item(page: website.ContentFile) -> tuple[str, str]:
  match page.category:
    case "articles":
      emoji = "📰"
      category = "article"
      match page.subcat:
        case "poetry":
          emoji = "📜"
          category = "#poem"
    case "av":
      emoji = "🗣️"
      category = "talk"
      match page.subcat:
        case "poetry":
          category = "#poem"
        case "music":
          category = "listen"
          emoji = "🎵"
        case "film":
          category = "video"
          emoji = "📼"
        case "podcast":
          category = "podcast"
        case "course":
          category = "online course"
          emoji = "🧑‍🏫"
    case "booklets":
      emoji = "📖"
      category = "book"
      match page.subcat:
        case "poetry":
          category = "book of #poetry"
        case "thesis":
          category = "thesis"
    case "canon":
      emoji = "☸️"
      category = "canonical work"
      book = re.split(r'[0-9\.-]', page.slug)[0]
      if book in ['an', 'sn', 'snp', 'kp', 'mn', 'pv', 'vv', 'dn', 'iti', 'thig', 'thag', 'ud']:
        category = "sutta"
      elif book in ['ea', 'da', 'sa', 'ma']:
        category = "āgama"
      elif book in ['t', 'toh']:
        category = "sūtra"
      elif page.subcat == "poetry":
        category = "canonical #poem"
      elif 'abhidhamma' in page.tags or 'abhidharma' in page.tags:
        category = "Abhidharma"
    case "essays":
      emoji = "🗒️"
      category = "essay"
      match page.subcat:
        case "poetry":
          category = "#poem"
    case "excerpts" | "papers":
      emoji = "📑"
      category = "paper"
      match page.subcat:
        case "poetry":
          category = "#poem"
    case "monographs":
      emoji = "📕"
      category = "book"
      match page.subcat:
        case "poetry":
          category = "book of #poetry"
        case "fiction":
          category = "novel"
    case "reference":
      emoji = "🆓"
      category = "resource"
    case _:
      raise RuntimeError("Unknown category")
  if page.translator and page.subcat != "music":
    if category[-1] in ['m', 'y']:
      category += " in"
    category += " translation"
  return (emoji, category)

def hashtagify(text: str) -> str:
  text = text.lower().replace(" ", "-")
  if '-' not in text:
    return text
  return text[0].upper() + re.sub(
    r'-([a-z])',
    lambda match: match.group(1).upper(),
    text[1:],
  )

def write_tags_for_item(page: website.ContentFile) -> list[str]:
  ret = []
  day_of_the_week = datetime.now().weekday() # 0 = Monday
  tags = page.tags or []
  if page.course:
    tags.insert(0, page.course)
  if day_of_the_week == 3: # Thursday
    if int(page.year) < 2000 or 'past' in tags:
      ret.append('TBT')
  for t in tags:
    if not t:
      continue
    tag = website.tags.get(t)
    if tag and tag.hashtag:
      if tag.hashtag not in ret:
        ret.append(tag.hashtag)
    else:
      tag = hashtagify(t)
      if tag not in ret:
        ret.append(tag)
  if day_of_the_week == 4: # Friday
    if page.category in ['booklets', 'monographs']:
      ret.append("FridayReads")
  return [t.replace("Roots", "History") for t in ret]

def write_post_for_item(page: website.ContentFile, include_link=True) -> str:
  title = write_post_title(page)
  length = length_of_item(page)
  emoji, category = get_category_for_item(page)
  tags = write_tags_for_item(page)
  tags = " ".join({f"#{t[0].upper()}{t[1:]}" for t in tags})
  if int(page.year) >= datetime.now().year - 1:
    year = ""
    adjectives = "✨NEW✨, free"
  else:
    year = f" from {page.year}"
    adjectives = "free"
  ret = f"""{emoji} {title} (A {adjectives}{length}{category}{year})

Tags: {tags}"""
  if include_link:
    return ret + f"\n{website.baseurl}{page.url}"
  return ret

def ensure_drive_links_are_shared(page: website.ContentFile) -> None:
  if not page.drive_links:
    return
  gids = [gdrive.link_to_id(glink) for glink in page.drive_links if '.google.com' in glink]
  gids = [gid for gid in gids if gid]
  if len(gids) > 0:
    print(f"Ensuring {' and '.join(gids)} ha{'s' if len(gids) == 1 else 've'} been shared...")
    gdrive.ensure_these_are_shared_with_everyone(gids)

if __name__ == "__main__":
  print("Loading site data...", flush=True)
  website.load()

  DOMAIN = urlparse(website.config.get("mastodon_link")).netloc
  AUTH_TOKEN = os.getenv("MASTODON_TOKEN")
  assert AUTH_TOKEN is not None, "Please set the MASTODON_TOKEN environment variable"
  print("Logging in to Mastodon...", flush=True)
  mastodon = Mastodon(api_base_url=DOMAIN, access_token=AUTH_TOKEN)
  ME = mastodon.me()
  print("Fetching the last few posts...", flush=True)
  last_few_posts = mastodon.account_statuses(
    ME['id'],
    exclude_reblogs=True,
    exclude_replies=True,
    limit=5,
  )
  print("Selecting the next post...", flush=True)
  LINK_FMT = '<a href="' + website.baseurl
  last_few_urls = [c.content.split(LINK_FMT)[1].split('"')[0] for c in last_few_posts if LINK_FMT in c.content]
  assert len(last_few_urls) > 1, "Last few posts didn't have any links. Is the link format correct?"
  idx_to_post = None
  filtered_content = [c for c in website.content if (c.external_url or c.drive_links) and c.status != 'rejected']
  for ridx, c in enumerate(reversed(filtered_content)):
    if c.url in last_few_urls:
      break
    idx_to_post = len(filtered_content) - 1 - ridx
  if idx_to_post is None:
    print("::error title=Nothing to do::No new items left to post to Mastodon")
    import sys
    sys.exit(1)
  assert idx_to_post > 3700, f"Script thinks we're on post number {idx_to_post}"
  mtype = "notice"
  remaining = len(filtered_content) - idx_to_post-1
  if remaining <= 2:
    mtype = "warning"
  print(f"::{mtype} title=Post Selection::Posted item {idx_to_post+1} of {len(filtered_content)} free items ({remaining} remaining after this)", flush=True)
  status = write_post_for_item(filtered_content[idx_to_post])
  matching_posts = [c for c in last_few_posts if c.content.startswith('<p>'+status.split('\n')[0]+'</p>')]
  if matching_posts:
    raise RuntimeError(f"Already posted as {matching_posts[0]['url']}?")
  ensure_drive_links_are_shared(filtered_content[idx_to_post])
  masto_info = mastodon.status_post(
    status=status,
    language="en",
    visibility="public",
  )
  print("::group::Mastodon Response")
  print(json.dumps(masto_info, indent=2, default=str))
  print("::endgroup::", flush=True)
  twitterror = None
  try:
      client = tweepy.Client(
        consumer_key=os.getenv("X_CONSUMER_KEY"),
        consumer_secret=os.getenv("X_CONSUMER_SECRET"),
        access_token=os.getenv("X_ACCESS_TOKEN"),
        access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
      )
      x_resp = client.create_tweet(text=status)
      print("::group::Twitter Response")
      print(json.dumps(x_resp, indent=2, default=str))
      print("::endgroup::", flush=True)
  except Exception as e:
      twitterror = e
  
  client = BskyClient()
  print("Posting to BlueSky...")
  client.login(website.config.get('bluesky_account'), os.getenv('BLUESKY_PASSWORD'))
  text = write_post_for_item(filtered_content[idx_to_post], include_link=False)
  embed = create_bsky_embed(filtered_content[idx_to_post])
  hashtags = hashtag_facets_for_text(text)
  client.send_post(text=text, facets=hashtags, embed=embed)
  print("  done")
  if twitterror:
      raise twitterror

  print("::group::Future Posts")
  while idx_to_post < len(filtered_content) - 1:
    print("")
    idx_to_post += 1
    print(write_post_for_item(filtered_content[idx_to_post]))
    print("")
  print("::endgroup::")
