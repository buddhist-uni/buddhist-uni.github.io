---
title: "Authors"
permalink: "/authors/"
layout: page
---
{% assign monographs = site.content | where_exp: "c", "c.path contains '/monographs/'" %}
{% assign booklets = site.content | where_exp: "c", "c.path contains '/booklets/'" %}
{% assign canon = site.content | where_exp: "c", "c.path contains '/canon/'" %}
{% assign papers = site.content | where_exp: "c", "c.path contains '/papers/'" %}
{% assign excerpts = site.content | where_exp: "c", "c.path contains '/excerpts/'" %}
{% assign essays = site.content | where_exp: "c", "c.path contains '/essays/'" %}
{% assign reference = site.content | where_exp: "c", "c.path contains '/reference/'" %}
{% assign articles = site.content | where_exp: "c", "c.path contains '/articles/'" %}
{% assign av = site.content | where_exp: "c", "c.path contains '/av/'" %}

{% assign author_letters = site.authors | group_by_exp: "a", "a.slug | slice: 0" %}

<div class="author-list">
{% for letter in author_letters %}
<h3 id="{{ letter.name }}">{{ letter.name | upcase }}</h3>
<ul class="author-sublist">
{% for author in letter.items %}
    {% assign catcounts = "" | split: "" %}
    {% capture filter %}c.authors contains '{{ author.slug }}'{% endcapture %}
    
    {% assign contents = canon | where_exp: "c", filter %}
    {% if contents.size > 0 %}
      {% capture s %}{{ contents.size }} canonical work{% if contents.size > 1 %}s{% endif %}{% endcapture %}
      {% assign catcounts = catcounts | push: s %}
    {% endif %}
    
    {% assign contents = monographs | where_exp: "c", filter %}
    {% if contents.size > 0 %}
      {% capture s %}{{ contents.size }} monograph{% if contents.size > 1 %}s{% endif %}{% endcapture %}
      {% assign catcounts = catcounts | push: s %}
    {% endif %}
    
    {% assign contents = booklets | where_exp: "c", filter %}
    {% if contents.size > 0 %}
      {% capture s %}{{ contents.size }} booklet{% if contents.size > 1 %}s{% endif %}{% endcapture %}
      {% assign catcounts = catcounts | push: s %}
    {% endif %}
    
    {% assign contents = papers | where_exp: "c", filter %}
    {% if contents.size > 0 %}
      {% capture s %}{{ contents.size }} paper{% if contents.size > 1 %}s{% endif %}{% endcapture %}
      {% assign catcounts = catcounts | push: s %}
    {% endif %}
    
    {% assign contents = excerpts | where_exp: "c", filter %}
    {% if contents.size > 0 %}
      {% capture s %}{{ contents.size }} excerpt{% if contents.size > 1 %}s{% endif %}{% endcapture %}
      {% assign catcounts = catcounts | push: s %}
    {% endif %}
    
    {% assign contents = essays | where_exp: "c", filter %}
    {% if contents.size > 0 %}
      {% capture s %}{{ contents.size }} essay{% if contents.size > 1 %}s{% endif %}{% endcapture %}
      {% assign catcounts = catcounts | push: s %}
    {% endif %}
    
    {% assign contents = articles | where_exp: "c", filter %}
    {% if contents.size > 0 %}
      {% capture s %}{{ contents.size }} article{% if contents.size > 1 %}s{% endif %}{% endcapture %}
      {% assign catcounts = catcounts | push: s %}
    {% endif %}
    
    {% assign contents = av | where_exp: "c", filter %}
    {% if contents.size > 0 %}
      {% capture s %}{{ contents.size }} recording{% if contents.size > 1 %}s{% endif %}{% endcapture %}
      {% assign catcounts = catcounts | push: s %}
    {% endif %}
    
    {% assign contents = reference | where_exp: "c", filter %}
    {% if contents.size > 0 %}
      {% capture s %}{{ contents.size }} reference work{% if contents.size > 1 %}s{% endif %}{% endcapture %}
      {% assign catcounts = catcounts | push: s %}
    {% endif %}
    
    {% assign contents = site.content | where: "reader", author.slug %}
    {% if contents.size > 0 %}
      {% capture s %}{{ contents.size }} reading{% if contents.size > 1 %}s{% endif %}{% endcapture %}
      {% assign catcounts = catcounts | push: s %}
    {% endif %}
    {% assign contents = site.content | where: "translator", author.slug %}
    {% if contents.size > 0 %}
      {% capture s %}{{ contents.size }} translation{% if contents.size > 1 %}s{% endif %}{% endcapture %}
      {% assign catcounts = catcounts | push: s %}
    {% endif %}
    
    <li id="{{ author.slug }}"><a href="{{ author.url }}">{{ author.title }}</a> ({{ catcounts | array_to_sentence_string }})</li>
{% endfor %}
</ul>
{% endfor %}
</div>  

