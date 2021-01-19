---
title: "Content Tests"
---

| Test Name | Status |  Notes |
|-----------|--------|--------|
| Count     | {% if site.content.size > 100 %}Pass ✅{% else %}FAIL ❌{% endif %}  | With {{ site.content.size }} items in the library. |
| Excessive Authors | {% assign ea = site.content | where_exp: "c", "c.authors.size > 5" %}{% if ea.size == 0 %}Pass ✅{% else %}FAIL ❌{% endif %}  |  {% assign cout = '' | split: '' %}{% for c in ea %}{% assign cout = cout | push: c.path %}{% endfor %}{{ cout | array_to_sentence_string }}
| Sane file_links | {% assign valid_buckets = "exclusive_01" | split: "," %}{% assign hostedcontent = site.content | where_exp: "c", "c.file_links.size > 0" %}{% assign fs = '' | split: '' %}{% for c in hostedcontent %}{% for l in c.file_links %}{% assign s = l | split: "/" %}{% unless valid_buckets contains s[1] %}{% assign fs = fs | push: c %}{% endunless %}{% endfor %}{% endfor %}{% if fs.size == 0 %}Pass ✅{% else %}FAIL ❌{% endif %}  |  {% for c in fs %}[{{ c.title | split: ":" | first }}]({{ c.url }}) {% endfor %}


