---
title: "Exclusive Works"
permalink: "/exclusive/"
layout: page
---

Here you will find links to the content on the site which (to my knowledge) is difficult or impossible to find elsewhere, either because it went offline,  it's a derivative work (e.g. when I edited a talk) or because it's a file I was given directly (e.g. recordings passed around offline). They are collected here in the hopes that this list will be useful to other collectors.

<div>
{% assign categories = "av,essays,reference" | split: ',' %}
{% for category_slug in categories %}
    {% assign category = site.categories | where: "slug", category_slug | first %}
    <h1>{{ category.title }}</h1>
    {% assign contents = site.content | where: "category", category_slug %}
    {% assign contents = contents | where_exp: "c", "c.drive_links.size > 0" %}
    {% assign contents = contents | where_exp: "c", "c.external_url == nil" %}
    <div>{% include content_list.html contents=contents orderby="slug" %}</div>
{% endfor %}
</div>
