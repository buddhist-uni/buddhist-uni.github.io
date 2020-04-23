---
title: "Topics"
permalink: "/tags/"
layout: page
---

Here you'll find the content on the site organized thematically. Very similar to <a href="{% link courses.md %}">the courses</a> but with less structure and commentary, the reading lists here put the works front and center, and allow you to zero in on what you might be looking for right now.

<ul class="master_tags_list">
{% assign tags = site.tags | sort: "slug" %}
{% for tag in tags %}
    <li><a class="tag_link" href="{{ tag.url }}">{{ tag.title }}</a>: {{ tag.excerpt }}</li>
{% endfor %}
</ul>
