---
title: "May Flowers"
---

This months readings are back to basics. There are two new topical reading lists on [Monastic Buddhism]({% link _tags/monastic.md %}) and [Buddhist Ethics]({% link _tags/ethics.md %}) and I've added a number of [suttas]({% link _categories/canon.md %}) to the library.

There's a lot of good stuff there to check out, but here are a few especially nice flowers just for you:

{% assign cslugs = 'mn87,snp1.2,war-and-peace_bodhi-geoff,island_pasanno-amaro,to-be-or-not-to-be_gessen-masha,an.007.049,ma025,sn.035.116,thig.14.01' | split: ',' %}
{% assign content = site.content | where_exp: "c", "cslugs contains c.slug" %}
<div class="narrow">{% include content_list.html contents=content %}</div>

I hope you enjoy the bouquet!

Yours etc,  
The Librarian

