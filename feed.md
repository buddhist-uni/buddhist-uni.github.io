---
title: RSS Feeds
section: blog
permalink: /feed
image: "https://www.buddhistuniversity.net/imgs/origami.jpg"
sirv_options: blur=2
big_image: https://upload.wikimedia.org/wikipedia/commons/8/8f/Origami_%2813777498043%29.jpg
big_width: 5184
big_height: 3456
image_width: 1280
image_height: 853
banner_info: <a href="https://commons.wikimedia.org/wiki/File:Origami_(13777498043).jpg">Helgi Halldórsson</a>, <a href="https://creativecommons.org/licenses/by/2.0">CC BY 2.0</a>
---

RSS is a web technology that allows you to get notified when content is added to your favorite websites.
To use RSS, copy one of the feed URLs below into [an RSS reader](https://en.wikipedia.org/wiki/Comparison_of_feed_aggregators){:target="_blank"} or [RSS-to-email service](https://blogtrottr.com/){:target="_blank"}.

## Blog Posts

| The Newsletter | [{{ "/feed.xml" | absolute_url }}](/feed.xml) |

## Library Content

| All Library Content | [{{ "/feed/content.xml" | absolute_url }}](/feed/content.xml) |

### Library Content by Type

{% for cat in site.categories %}{% if cat.slug == "index" %}{% continue %}{% endif %}| {{ cat.title }} | [{{ "/feed/content/" | append: cat.slug | append: ".xml" | absolute_url }}](/feed/content/{{ cat.slug }}.xml) |
{% endfor %}

### Library Content by Topic

{% assign alltags = site.tags | sort: "title" %}
| Buddhism (General) | [{{ "/feed/content/buddhism.xml" | absolute_url }}](/feed/content/buddhism.xml) |
{% for tag in alltags %}{% if tag.slug == "buddhism" %}{% continue %}{% endif %}| {{ tag.title }} | [{{ "/feed/content/" | append: tag.slug | append: ".xml" | absolute_url }}](/feed/content/{{ tag.slug }}.xml) |
{% endfor %}
