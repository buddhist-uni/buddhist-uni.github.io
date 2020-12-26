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

OBU Courses are loosely modeled on [MIT's Open Courseware](https://ocw.mit.edu){:target="_blank"}, which provide free syllabi and other course materials for a large number of their Undergraduate and Graduate-level courses. I especially recommend:

- [MIT 21G.19: Communicating Across Cultures](https://ocw.mit.edu/courses/global-languages/21g-019-communicating-across-cultures-spring-2005/index.htm){:target="_blank"}
  - Probe the challenges of intercultural dialogue with theoretical frameworks and practical exercises.
- [MIT WGS.110J: Sexual and Gender Identities](https://ocw.mit.edu/courses/womens-and-gender-studies/wgs-110j-sexual-and-gender-identities-spring-2016/){:target="_blank"}
  - Learn the surprising history of gender in America.
- [MIT 14.73: The Challenge of World Poverty](https://ocw.mit.edu/courses/economics/14-73-the-challenge-of-world-poverty-spring-2011/){:target="_blank"}
  - Understand the drivers, traps, and opportunities for global poverty with Nobel Laureates Abhijit Banerjee and Esther Duflo.
- [MIT STS.003: The Rise of Modern Science](https://ocw.mit.edu/courses/science-technology-and-society/sts-003-the-rise-of-modern-science-fall-2010/index.htm){:target="_blank"}
  - Break down the ahistorical mythology of modern science by taking a close look at its primary sources.
- [MIT WGS.274J: Gender and Representation of Asian Women](https://ocw.mit.edu/courses/anthropology/21a-470j-gender-and-representation-of-asian-women-spring-2010/){:target="_blank"}
  - Recognize how politics shape perception.
