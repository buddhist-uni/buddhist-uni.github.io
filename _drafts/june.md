---
title: "June"
---

{% assign cslugs = 'have-you-come-here-to-die_brahm' | split: ',' %}
{% assign content = site.content | where_exp: "c", "cslugs contains c.slug" %}
<div class="narrow">{% include content_list.html contents=content %}</div>