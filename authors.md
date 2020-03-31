---
title: "Authors"
permalink: "/authors/"
layout: page
---

<div>
{% for author in site.authors %}
    <h1 id="{{ author.slug }}">{{ author.title }}</h1>
    {% capture filter %}c.authors contains '{{ author.slug }}'{% endcapture %}
    {% assign contents = site.content | where_exp: "c", filter %}
    {% assign transcont = site.content | where: "translator", author.slug %}
    {% assign readcont = site.content | where: "reader", author.slug %}
    <div>{% include content_list.html contents=contents %}</div>
    {% if readcont.size > 0 %}
    <h3>Reads:</h3>
    <div>{% include content_list.html contents=readcont %}</div>
    {% endif %}
    {% if transcont.size > 0 %}
    <h3>Translated:</h3>
    <div>{% include content_list.html contents=transcont %}</div>
    {% endif %}
{% endfor %}
</div>
