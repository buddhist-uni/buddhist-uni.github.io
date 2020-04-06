---
layout: default
---
<article class="post">

  <header class="post-header">
    <h1 class="post-title">{{ page.title | escape }}</h1>
  </header>

  <div class="post-content">
    <div class="description">{{ content }}</div>
    <div class="content">
      <h2>Content</h2>
        {% capture filter %}c.authors contains '{{ page.slug }}'{% endcapture %}
    {% assign contents = site.content | where_exp: "c", filter %}
    {% assign transcont = site.content | where: "translator", page.slug %}
    {% assign readcont = site.content | where: "reader", page.slug %}
    <div>{% include content_list.html contents=contents orderby="year" %}</div>
    {% if readcont.size > 0 %}
    <h3>Reads:</h3>
    <div>{% include content_list.html contents=readcont orderby="year" %}</div>
    {% endif %}
    {% if transcont.size > 0 %}
    <h3>Translated:</h3>
    <div>{% include content_list.html contents=transcont orderby="year" %}</div>
    {% endif %}
    </div>
  </div>

</article>