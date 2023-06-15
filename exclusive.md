---
title: "Exclusive Works"
section: library
permalink: "/exclusive/"
layout: page
---

Here you will find links to the content on the site which is difficult to find elsewhere: either because it went offline, it was edited, or because it's a file that was previously circulating offline. They are collected here in the hope that it will be useful to other collectors. You can [download a zip archive containing many of these files here](https://github.com/buddhist-uni/exclusive_01/archive/main.zip).

## Works by Type
- [Articles](#articles)
- [Audio](#av)
- [Essays](#essays)
- [Papers](#papers)
- [Reference Shelf](#reference)

<div>
{% assign categories = "articles,av,essays,papers,reference" | split: ',' %}
{% for category_slug in categories %}
    {% assign category = site.categories | find: "slug", category_slug %}
    <h2 id="{{ category.slug }}">{{ category.title }}</h2>
    {% assign contents = site.content | where: "category", category_slug %}
    {% assign contents = contents | where_exp: "c", "c.drive_links.size > 0" %}
    {% assign contents = contents | where_exp: "c", "c.external_url == nil" %}
    <div>{% include content_list.html contents=contents orderby="slug" %}</div>
{% endfor %}
</div>
