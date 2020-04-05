## Further Reading
{% capture filter %}c.tags contains '{{ page.slug }}'{% endcapture %}
{% assign tagged = site.content | where_exp: "c", filter %}
{% if tagged.size > 0 %}<div>{% include content_list.html contents=tagged orderby="year" %}</div><p>or c{% else %}<p>C{% endif %}heck out <a href="{% link courses.md %}">our other courses</a> to continue your studies!</p>


