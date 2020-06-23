---
title: "June"
---

{% assign cslugs = 'have-you-come-here-to-die_brahm,how-to-meditate_yuttadhammo,mindfulness-intervention-to-youth-issues-in-vietnam_le-trieu,mindfulness-according-to-early-sources_analayo,liberative-role-of-piti-sukha_arbel,anything-you-synthesize_american-dollar,wheel_sohn' | split: ',' %}
{% assign content = site.content | where_exp: "c", "cslugs contains c.slug" %}
<div class="narrow">{% include content_list.html contents=content %}</div>