#!/bin/python3

import requests
import xml.etree.ElementTree as XML
from archivedotorg import archive_urls

SITEMAP_NAMESPACE = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

def all_urls_in_website(domain):
    # Fetch the XML sitemap using requests
    response = requests.get(domain+"/sitemap.xml")
    if not response.ok:
      print(f"Couldn't load the sitemap for {domain}")
      return
    print(f"Got the sitemap for {domain} ({len(response.text)}bytes)")
    root = XML.fromstring(response.text)
    # Find all URL elements using XPath
    url_elements = root.findall(".//ns:url", SITEMAP_NAMESPACE)
    togo = len(url_elements)
    # Extract and yield the URLs
    for url_element in url_elements:
        loc_element = url_element.find("ns:loc", SITEMAP_NAMESPACE)
        if loc_element is not None:
            yield loc_element.text

if __name__ == "__main__":
  skip_past = "Last successful URL"
  urls = list(all_urls_in_website("https://buddhistuniversity.net"))
  try:
    skip_past = urls.index(skip_past)
    urls = urls[skip_past+1:]
  except:
    pass
  archive_urls(urls)

