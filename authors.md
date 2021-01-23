---
title: "Authors"
permalink: "/authors/"
layout: page
---
{%- assign all_content = site.content | where_exp: "c", "c.status != 'rejected'" %}
{%- assign author_letters = site.authors | group_by_exp: "a", "a.slug | slice: 0" -%}
{%- assign readers = all_content | where_exp: "c", "c.reader" | group_by: "reader" -%}
{%- assign translators = all_content | where_exp: "c", "c.translator" | group_by: "translator" -%}
<div class="author-list">
{%- for letter in author_letters -%}
<h3 id="{{ letter.name }}">{{ letter.name | upcase }}</h3>
<ul class="author-sublist">
{%- for author in letter.items -%}
    {%- assign catcounts = "" | split: "" -%}
    {%- capture filter %}c.authors contains '{{ author.slug }}'{% endcapture -%}
    {%- assign by_cat = all_content | where_exp: "c", filter | group_by: "category" -%}
    {%- for cat in by_cat -%}
      {%- case cat.name -%}
        {%- when "canon" -%}
          {% capture s %}{{ cat.size }} canonical work{% if cat.size > 1 %}s{% endif %}{% endcapture %}
          {% assign catcounts = catcounts | push: s %}
        {% when "av" %}
          {% capture s %}{{ cat.size }} recording{% if cat.size > 1 %}s{% endif %}{% endcapture %}
          {% assign catcounts = catcounts | push: s %}
        {% when "reference" %}
          {% capture s %}{{ cat.size }} reference work{% if cat.size > 1 %}s{% endif %}{% endcapture %}
          {% assign catcounts = catcounts | push: s %}
        {% else %}
          {% if cat.size == 1 %}{% assign s = cat.name | size | minus: 1 %}{% assign cname = cat.name | slice: 0, s %}{% else %}{% assign cname = cat.name %}{% endif %}
          {% capture s %}{{ cat.size }} {{ cname }}{% endcapture %}
          {% assign catcounts = catcounts | push: s %}
      {% endcase %}
    {% endfor %}

    {% assign contents = readers | where: "name", author.slug | first %}
    {% if contents.size > 0 %}
      {% capture s %}{{ contents.size }} reading{% if contents.size > 1 %}s{% endif %}{% endcapture %}
      {% assign catcounts = catcounts | push: s %}
    {% endif %}

    {% assign contents = translators | where: "name", author.slug | first %}
    {% if contents.size > 0 %}
      {% capture s %}{{ contents.size }} translation{% if contents.size > 1 %}s{% endif %}{% endcapture %}
      {% assign catcounts = catcounts | push: s %}
    {%- endif -%}
    {% assign slugsize = author.slug | size %}
    {% assign slugified = author.title | replace: ".", "0" | slugify: "latin" %}
    {%- assign pivot = author.title_alphabetic_order_pivot | default: 0 -%}
    {% if pivot == 0 %}{% for xx in (1..slugsize) %}
        {% assign pi = slugsize | minus: xx | plus: 1 %}
        {% assign t = author.slug | slice: 0, pi %}
        {% assign p = slugified | split: t %}
        {% if p.size > 1 %}
            {% assign pivot = p | first | size %}
            {% break %}
        {% endif %}
    {% endfor %}{% endif %}
    {%- assign p2e = author.title | size | minus: pivot -%}
    <li id="{{ author.slug }}"><a href="{{ author.url }}">{{ author.title | slice: pivot, p2e }}{% if pivot > 0 %}, {{ author.title | slice: 0, pivot }}{% endif %}</a><div class="catcounts">({{ catcounts | array_to_sentence_string }})</div></li>
{%- endfor -%}
</ul>
{%- endfor -%}
</div>  

