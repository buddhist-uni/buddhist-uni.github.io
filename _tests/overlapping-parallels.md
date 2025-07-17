---
title: Overlapping Parallels
---

{% assign output = "" | split: "" %}
{% assign ignore = "ma,sa,ea,da,mn,an,sn,dn,ud,snp,kn,vv" | split: "," %}

{% assign allcanon = site.content | where: "category", "canon" %}
{% for fromsutta in allcanon %}
{% unless fromsutta.parallels.size > 0 %}
  {% continue %}
{% endunless %}
{% for toslug in fromsutta.parallels %}
{% capture filter %}c.path contains "/{{toslug}}.md"{% endcapture%}
{% assign tosutta = allcanon | find_exp: "c", filter %}
{% unless tosutta %}
  {% continue %}
{% endunless %}
{% assign tags = "" | split: "" %}
{% if fromsutta.course %}
  {% if fromsutta.course == tosutta.course %}
    {% unless ignore contains tosutta.course %}
      {% assign tags = tags | push: tosutta.course %}
    {% endunless %}
  {% endif %}
  {% if tosutta.tags.size > 0 %}
    {% if tosutta.tags contains fromsutta.course %}
      {% unless ignore contains fromsutta.course %}
        {% assign tags = tags | push: fromsutta.course %}
      {% endunless %}
    {% endif %}
  {% endif %}
{% endif %}
{% if tosutta.course %}
  {% if fromsutta.tags contains tosutta.course %}
    {% unless ignore contains tosutta.course %}
      {% assign tags = tags | push: tosutta.course %}
    {% endunless %}
  {% endif %}
{% endif %}
{% if tosutta.tags.size > 0 %}
  {% if fromsutta.tags.size > 0 %}
    {% for t in fromsutta.tags %}
      {% if tosutta.tags contains t %}
        {% unless ignore contains t %}
          {% assign tags = tags | push: t %}
        {% endunless %}
      {% endif %}
    {% endfor %}
  {% endif %}
{% endif %}
{% unless tags.size > 0 %}
  {% continue %}
{% endunless %}
{% capture row %}| [{{fromsutta.slug}}]({{fromsutta.url}}) | [{{tosutta.slug}}]({{tosutta.url}}) | {{ tags | join: ", " }} |{% endcapture%}
{% assign output = output | push: row %}
{% endfor %}{% endfor %}

{% if output.size > 0 %}
NOTE: Cleaning these up is a large project currently in progress.

Found {{ output.size }} pairs of suttas with overlapping tags:

| From | To Sutta |  Tags in common |
|------|----------|-----------------|{% for row in output %}
{{ row }}{% endfor %}
{% else %}
Pass ✅ - No parallels have overlapping tags
{% endif %}

## Anthologies

In addition to the sutta parallels above, suttas should be deduped against the anthologies that contain them (e.g. if a sutta is in an assigned anthology, it shouldn't also be assigned to that course separately as well).

Anthologies yet to be processed:
  - Bhikkhu Bodhi's [selections in the Sutta tag](/search/?q=author%3ABodhi%20tag%3Asutta%20selection%20)
  - [*Common Buddhist Text*](/content/monographs/common-buddhist-text)
  - Ajahn Geoff's *Noble Conversation* and *Sublime Attitudes*
  - and [Jason Espada's anthologies](/search/?q=jason%20espada)

Suttas have been added and deduped from:
  - *The Island*
  - Ajahn Geoff's *The Buddha Smiles*
  - Ajahn Geoff's *Recognizing the Dhamma*
  - Hecker's *Similes of the Buddha*
  - Nyanamoli's *Life of the Buddha*
  - The many wheel publications containing whole sutta translations
