---
layout: page
title: Courses
permalink: /courses/
---

The University organizes [content]({% link library.md %}) from [across the Web]({% link sources.md %}) into self-paced, free courses on a variety of topics in Buddhist Studies. We currently offer {{ site.data.course_order.size }} courses on the fundamentals of Buddhism:

{% for cslug in site.data.course_order %}
{% assign course = site.courses | where: "slug", cslug | first %}
{% assign courseware = site.content | where: "course", cslug %}
{% assign booklets = courseware | where: "category", "booklets" %}
{% assign textbooks = courseware | where: "category", "monographs" | concat: booklets %}
{% assign bauthors = '' | split: '' %}
{% for b in textbooks %}{% assign tbas = b.authors %}{% unless tbas.size > 3%}{% for tba in tbas %}{% unless bauthors contains tba %}{% assign bauthors = bauthors | push: tba %}{% endunless %}{% endfor %}{% endunless %}{% endfor %}
<h3 class="courselink">{{ forloop.index }}. <a href="{{ course.url }}">{{ course.title }}</a></h3>

<div class="coursedesc">
  <div class="descrow">
    <div class="cicon"><i class="{{ course.icon }}"></i></div>
    <div class="cdesc">{{ course.description | markdownify }}</div>
    <div class="ccredits"><i class="fas fa-weight-hanging"></i> {{ course.time }}</div>
  </div>
  <div class="featuringrow">
    <div class="flabel"><strong>Featuring</strong>:</div>
    {% if course.lecturers %}<div class="lecturers"><i class="fas fa-chalkboard-teacher"></i> {% include content_authors_string.html authors=course.lecturers %}</div>{% endif %}
    {% if bauthors.size > 0 %}<div class="bauthors"><i class="far fa-address-book"></i> {% include content_authors_string.html authors=bauthors %}</div>{% endif %}
  </div>
</div>

{% endfor %}

