---
---

{% include content_box.html category="canon" slug="mn87" %}

{% assign cslugs = 'island_pasanno-amaro,to-be-or-not-to-be_gessen-masha,an.007.049' | split: ',' %}
{% assign content = site.content | where_exp: "c", "cslugs contains c.slug" %}
<div class="narrow">{% include content_list.html contents=content %}</div>