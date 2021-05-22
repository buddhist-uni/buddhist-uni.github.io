---
layout: page
section: courses
slug: courses
title: Courses
permalink: /courses/
image_width: 1280
image: "https://illeakyw.sirv.com/Images/banners/burmese-nuns-studying.jpg"
image_center_x: 20%
image_center_y: 46%
big_image: "https://upload.wikimedia.org/wikipedia/commons/a/ad/Zhaya_Theingyi-Sagaing-Myanmar-02-gje.jpg"
banner_info: <a href="https://commons.wikimedia.org/wiki/File:Zhaya_Theingyi-Sagaing-Myanmar-02-gje.jpg">Gerd Eichmann</a>, <a href="https://creativecommons.org/licenses/by-sa/3.0">BY-SA 3.0</a>
---

The University organizes [content from across the Web]({% link library.md %}) into free, self-directed syllabi on a variety of topics in Buddhist Studies.

We currently offer {{ site.data.course_order.size }} courses on the fundamentals of Buddhism. Courses with a "<i class="far fa-address-book"></i>" icon are detailed reading guides through works by the listed authors. Courses with a "<i class="fas fa-microphone-alt"></i>" icon also have associated lectures recorded by the listed instructor.

If you'd like to discuss what you're learning with other students of early Buddhism, I recommend posting your thoughts and questions to [the SuttaCentral Forum](https://discourse.suttacentral.net/?u=khemarato.bhikkhu){:target="_blank"} or [emailing us at the University](mailto:theopenbuddhistuniversity@gmail.com).

We hope you enjoy our offerings:

{% for cslug in site.data.course_order %}
{% assign course = site.courses | find: "slug", cslug %}
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

- [The Challenge of World Poverty](https://ocw.mit.edu/courses/economics/14-73-the-challenge-of-world-poverty-spring-2011/){:.f3}
  - To understand the drivers, traps, and opportunities for global poverty with Nobel Laureates Abhijit Banerjee and Esther Duflo.
{:.mb-2}

- [Sexual and Gender Identities](https://ocw.mit.edu/courses/womens-and-gender-studies/wgs-110j-sexual-and-gender-identities-spring-2016/){:.f3}
  - To learn the surprising history of gender in America.
{:.mb-2}

- [The Rise of Modern Science](https://ocw.mit.edu/courses/science-technology-and-society/sts-003-the-rise-of-modern-science-fall-2010/index.htm){:.f3}
  - To break down the ahistorical mythology of modern science by taking a closer look at its primary sources.
{:.mb-2}

- [Gender and Representation of Asian Women](https://ocw.mit.edu/courses/anthropology/21a-470j-gender-and-representation-of-asian-women-spring-2010/){:.f3}
  - To recognize how politics shape our perceptions.
{:.mb-2}

- [Communicating Across Cultures](https://ocw.mit.edu/courses/global-languages/21g-019-communicating-across-cultures-spring-2005/index.htm){:.f3}
  - To probe the challenges of intercultural dialogue with theoretical frameworks and practical exercises.
{:.mb-2}
