---
layout: default
---

<article class="course">                                                                                                
  <header class="post-header">
    <h1 class="post-title">{{ page.title | escape }}</h1>

{% if page.parents %}
{% assign parents = '' | split: '' %}
{% for pslug in page.parents %}
    {% assign parent = site.tags | where: "slug", pslug | first %}
    {% unless parent %}{% continue %}{% endunless %}
    {% capture plink %}<a href="{{ parent.url }}">{{ parent.title }}</a>{% endcapture %}
    {% assign parents = parents | push: plink %}
{% endfor %}
{% if parents.size > 0 %}
<em>Supertopic{% if parents.size > 1 %}s{% endif %}: {{ parents | array_to_sentence_string }}</em>
{% endif %}{% endif %}

{% if page.children %}
{% assign children = '' | split: '' %}
{% for cslug in page.children %}
    {% assign child = site.tags | where: "slug", cslug | first %}
    {% unless child %}{% continue %}{% endunless %}
    {% capture clink %}<a href="{{ child.url }}">{{ child.title }}</a>{% endcapture %}
    {% assign children = children | push: clink %}
{% endfor %}
{% if children.size > 0 %}
<em>Subtopic{% if children.size > 1 %}s{% endif %}: {{ children | array_to_sentence_string }}</em>
{% endif %}{% endif %}
{% assign course = site.courses | where: "slug", page.slug | first %}
{% if course %}
<p><em>For a more structured walkthrough of this content, see <a href="{{ course.url }}">the "{{ course.title }}" course</a>.</em></p>
{% endif %}
  </header>

  <div class="post-content">
    <div class="tag_desc">{{ content }}</div>
<h2>Featured Works</h2>
<div>
{% assign category = site.content | where: "course", page.slug %}
{% include content_list.html contents=category %}
</div><h2>Related Works</h2><div>
{% capture filter_exp %}c.tags contains '{{ page.slug }}'{% endcapture %}
{% assign category = site.content | where_exp: "c", filter_exp %}
{% include content_list.html contents=category %}
</div>

  </div>

</article>

