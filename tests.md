---
title: "Integration Tests"
permalink: "/tests/"
layout: page
---

{% for test in site.tests %}
- [{{ test.title }}]({{ test.url }})
{% endfor %}
- [Monthly Link Audits](https://github.com/buddhist-uni/buddhist-uni.github.io/issues?q=is%3Aissue+Monthly+Link+Report+author%3Aapp%2Fgithub-actions)
