---
title: "Authors"
permalink: "/authors/"
section: library
layout: page
banner_info: <a href="https://commons.wikimedia.org/wiki/File:(Above)_sBed-byed_(Gopaka),_holding_a_book;_Wellcome_V0018272_(cropped).jpg">Wellcome Library</a>, <a href="https://creativecommons.org/licenses/by/4.0">CC BY 4.0</a>
image: "https://illeakyw.sirv.com/Images/banners/gopaka-book.jpeg"
sirv_options: saturation=-8&brightness=3&blur=1
image_width: 480
image_center_x: 30%
image_center_y: 29%
big_image: "https://upload.wikimedia.org/wikipedia/commons/e/ec/%28Above%29_sBed-byed_%28Gopaka%29%2C_holding_a_book%3B_Wellcome_V0018272_%28cropped%29.jpg"
big_width: 1265
big_height: 2025
---
{%- assign all_content = site.content | where_exp: "c", "c.status != 'rejected'" %}
{%- assign author_letters = site.authors | group_by_exp: "a", "a.slug | slice: 0" | sort: "name" -%}
{%- assign readers = all_content | where_exp: "c", "c.reader" | group_by: "reader" -%}
{%- comment -%}Note that there's a subtle bug below: this cannot find works that were translated by multiple authors. Since this is rare, I haven't prioritized fixing it...{%- endcomment -%}
{%- assign translators = all_content | where_exp: "c", "c.translator" | group_by: "translator" -%}

{% for letter in author_letters %}[{{ letter.name | upcase }}](#{{ letter.name }})  {% endfor %}

<div class="author-list">
{%- for letter in author_letters -%}
<h3 id="{{ letter.name }}">{{ letter.name | upcase }}</h3>
<ul class="author-sublist">
{%- assign authorsublist = letter.items | sort: "slug" -%}
{%- for author in authorsublist -%}
    {%- assign catcounts = "" | split: "" -%}
    {%- capture filter -%}c.authors contains '{{ author.slug }}'{%- endcapture -%}
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

    {% assign contents = readers | find: "name", author.slug %}
    {% if contents.size > 0 %}
      {% capture s %}{{ contents.size }} reading{% if contents.size > 1 %}s{% endif %}{% endcapture %}
      {% assign catcounts = catcounts | push: s %}
    {% endif %}

    {% assign contents = translators | find: "name", author.slug %}
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

