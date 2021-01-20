---
title: "Exclusive Works"
permalink: "/exclusive/"
layout: page
---

Here you will find links to the content on the site which (to my knowledge) is difficult or impossible to find elsewhere: either because it went offline, it's a derivative work (e.g. I edited a talk) or because it's a file I was given directly (e.g. a file passed around offline). They are collected here in the hopes that this list will be useful to other collectors. You can [download a zip archive containing most of these files, here](https://github.com/buddhist-uni/exclusive_01/archive/main.zip).

<div>
{% assign categories = "av,essays,papers,reference" | split: ',' %}
{% for category_slug in categories %}
    {% assign category = site.categories | where: "slug", category_slug | first %}
    <h1>{{ category.title }}</h1>
    {% assign contents = site.content | where: "category", category_slug %}
    {% assign contents = contents | where_exp: "c", "c.drive_links.size > 0" %}
    {% assign contents = contents | where_exp: "c", "c.external_url == nil" %}
    <div>{% include content_list.html contents=contents orderby="slug" %}</div>
{% endfor %}
</div>
