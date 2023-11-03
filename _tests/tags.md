---
title: "Tag Tests"
---

A series of tests to check the integrity of the tag configuration.

| Test Name | Status | Notes |
|-----------|--------|-------|
| All tags in _config.yml order | {% assign pivottags = site.tags | map: "name" | join: " " | split: " mandarin.md " %}{% if pivottags.size == 1 %}Pass ✅{% else %}FAIL ❌{% endif %}  |  {% if pivottags.size > 1 %}These tags need to be added: `{{ pivottags | last }}`{% else %}All in!{% endif %} |
| If published, parent is | {% assign failures = "" | split: "" %}{% for tag in site.tags %}{% assign parent = site.tags | find: "slug", tag.parents[0] %}{% unless parent and tag.status == "published" %}{% continue %}{% endunless %}{% unless parent.status == "published" or tag.level == 1 %}{% assign failures = failures | push: tag.name %}{% endunless %}{% endfor %}{% if failures.size == 0 %}Pass ✅{% else %}FAIL ❌{% endif %}  |  {% if failures.size > 0 %}These tags have unpublished parents: `{{ failures | join: " " }}`{% else %}None dangling!{% endif %} |
| Parents appear before children in tag order (except for "-religion" tags, pairs across the Buddhism/secular divide and "modern") | {% assign pivottags = site.tags | map: "name" | join: " " | split: " world.md " %}{% assign buddhismtags = pivottags | first %}{% assign seculartags = pivottags | last %}{% assign failures = "" | split: "" %}{% assign seen = "modern" | split: "," %}{% for tag in site.tags %}{% if tag.slug contains "religion" %}{% continue %}{% endif %}{% for pslug in tag.parents %}{% assign parent = site.tags | find: "slug", pslug %}{% unless parent %}{% continue %}{% endunless %}{% if buddhismtags contains tag.name and seculartags contains parent.name %}{% continue %}{% endif %}{% unless seen contains pslug %}{% capture pair %}({{tag.slug}}, {{pslug}}){% endcapture %}{% assign failures = failures | push: pair %}{% endunless %}{% endfor %}{% assign seen = seen | push: tag.slug %}{% endfor %}{% if failures.size == 0 %}Pass ✅{% else %}FAIL ❌{% endif %}  |  {% if failures.size > 0 %}(child, parent) pairs that are out of order: `{{ failures | join: " " }}`{% else %}All partial orderings are respected.{% endif %} |
