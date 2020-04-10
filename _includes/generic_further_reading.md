## Further Reading

{% assign all_content = site.content | where_exp: "c", "c.status != 'rejected'" %}
{% assign categories = site.data.content_categories %}
{% capture filter_exp %}c.tags contains '{{ page.slug }}'{% endcapture %}
{% for catslug in categories %}
  {% capture cat_filter %}c.path == "content/{{ catslug }}.md"{% endcapture %}
  {% assign category = site.pages | where_exp: "c", cat_filter | first %}
  {% capture cat_filter %}c.path contains '/{{ catslug }}/'{% endcapture %}
  {% assign cat_content = all_content | where_exp: "c", cat_filter %}
  {% assign tagged_content = cat_content | where_exp: "c", filter_exp %}
  {% if tagged_content.size > 0 %}
<h4 id="further-{{ catslug }}">{{ category.title }}</h4>
<div>{% include content_list.html contents=tagged_content orderby="slug" %}</div>
  {% endif %}
{% endfor %}

or check out <a href="{% link courses.md %}">our other courses</a> to continue your studies!
