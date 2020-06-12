---
title: "June"
---

{% assign cslugs = 'have-you-come-here-to-die_brahm,how-to-meditate_yuttadhammo,mindfulness-intervention-to-youth-issues-in-vietnam_le-trieu' | split: ',' %}
{% assign content = site.content | where_exp: "c", "cslugs contains c.slug" %}
<div class="narrow">{% include content_list.html contents=content %}</div>