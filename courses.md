---
layout: page
title: Courses
permalink: /courses/
image: "https://illeakyw.sirv.com/Images/banners/buddha_teaching_watercolor.jpg"
image_width: 1338
image_center_x: 99%
image_center_y: 42%
big_image: "https://upload.wikimedia.org/wikipedia/commons/2/24/044_Teaching_the_Five_Disciples_%289014362720%29.jpg"
banner_info: <a href="https://commons.wikimedia.org/wiki/File:044_Teaching_the_Five_Disciples_(9014362720).jpg">Photo Dharma</a>, <a href="https://creativecommons.org/licenses/by/2.0">CC BY 2.0</a>
---

The University organizes [content]({% link library.md %}) from [across the Web]({% link sources.md %}) into self-paced, free courses on a variety of [topics in Buddhist Studies]({% link tags.md %}). We currently offer {{ site.data.course_order.size }} courses on the fundamentals of Buddhism:

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
    <div onclick="location.href='{{ course.url }}'" class="cicon"><i class="{{ course.icon }}"></i></div>
    <div class="cdesc">{{ course.description | markdownify }}</div>
    <div class="ccredits"><i class="fas fa-weight-hanging"></i> {{ course.time }}</div>
  </div>
  <div class="featuringrow">
    <div class="flabel"><strong>Featuring</strong>:</div>
    {% if course.lecturers %}<div class="lecturers"><i class="fas fa-microphone-alt"></i> {% include content_authors_string.html authors=course.lecturers %}</div>{% endif %}
    {% if bauthors.size > 0 %}<div class="bauthors"><i class="far fa-address-book"></i> {% include content_authors_string.html authors=bauthors %}</div>{% endif %}
  </div>
</div>

{% endfor %}

## Secular Courses (@MIT)

OBU Courses are loosely modeled on [MIT's Open Courseware](https://ocw.mit.edu){:target="_blank"}, which provide free syllabi and other course materials for a large number of their Undergraduate and Graduate-level courses. For OBU Students, I especially recommend:

- [Communicating Across Cultures](https://ocw.mit.edu/courses/global-languages/21g-019-communicating-across-cultures-spring-2005/index.htm){:.f3 .uifont}
  - To probe the challenges of intercultural dialogue with theoretical frameworks and practical exercises.
{:.mb-2}

- [Sexual and Gender Identities](https://ocw.mit.edu/courses/womens-and-gender-studies/wgs-110j-sexual-and-gender-identities-spring-2016/){:.f3 .uifont}
  - To learn the surprising history of gender in America.
{:.mb-2}

- [The Challenge of World Poverty](https://ocw.mit.edu/courses/economics/14-73-the-challenge-of-world-poverty-spring-2011/){:.f3 .uifont}
  - To understand the drivers, traps, and opportunities for global poverty with Nobel Laureates Abhijit Banerjee and Esther Duflo.
{:.mb-2}

- [The Rise of Modern Science](https://ocw.mit.edu/courses/science-technology-and-society/sts-003-the-rise-of-modern-science-fall-2010/index.htm){:.f3 .uifont}
  - To break down the ahistorical mythology of modern science by taking a closer look at its primary sources.
{:.mb-2}

- [Gender and Representation of Asian Women](https://ocw.mit.edu/courses/anthropology/21a-470j-gender-and-representation-of-asian-women-spring-2010/){:.f3 .uifont}
  - To recognize how politics shape our perceptions.
{:.mb-2}
