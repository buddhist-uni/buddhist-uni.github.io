---
title: "Content Tests"
---

| Test Name | Status |  Notes |
|-----------|--------|--------|
| Count     | {% if site.content.size > 100 %}Pass ✅{% else %}FAIL ❌{% endif %}  | With {{ site.content.size }} items in the library. |
| Excessive Authors | {% assign ea = site.content | where_exp: "c", "c.authors.size > 5" %}{% if ea.size == 0 %}Pass ✅{% else %}FAIL ❌{% endif %}  |  {% assign cout = '' | split: '' %}{% for c in ea %}{% assign cout = cout | push: c.path %}{% endfor %}{{ cout | array_to_sentence_string }}


