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
    <div>{% include content_list.html contents=contents %}</div>
{% endfor %}
</div>
