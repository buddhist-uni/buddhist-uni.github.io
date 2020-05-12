---
---

{% include content_box.html category="canon" slug="mn87" %}

{% include content_box.html category="canon" slug="snp1.2" %}

{% assign cslugs = 'island_pasanno-amaro,to-be-or-not-to-be_gessen-masha,an.007.049,sn.035.116' | split: ',' %}
{% assign content = site.content | where_exp: "c", "cslugs contains c.slug" %}
<div class="narrow">{% include content_list.html contents=content %}</div>