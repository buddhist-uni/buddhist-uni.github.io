---
title: "Exclusive Works"
permalink: "/exclusive/"
layout: page
---

Here you will find links to all the content on the site which to my knownledge doesn't exist elsewhere on the open internet or is especially difficult to find, either because it was taken down, because it's my own derivative work (e.g. when I edited a talk) or because it's a file I was given directly (e.g. chanting recordings passed around offline). They are collected here in the hopes that this list will be useful to other collectors.

<div>
{% assign categories = "av,essays" | split: ',' %}
{% for category_slug in categories %}
    {% capture cpath %}content/{{ category_slug }}.md{% endcapture %}
    {% assign category = site.pages | where: "path", cpath | first %}
    <h1>{{ category.title }}</h1>
    {% capture filter %}c.path contains '/{{ category_slug }}/'{% endcapture %}
    {% assign contents = site.content | where_exp: "c", filter %}
    {% assign contents = contents | where_exp: "c", "c.drive_links.size > 0" %}
    {% assign contents = contents | where_exp: "c", "c.external_url == nil" %}
    <div>{% include content_list.html contents=contents %}</div>
{% endfor %}
</div>
