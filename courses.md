---
layout: page
section: courses
slug: courses
title: Courses
rss_url: feed.xml
rss_title: "Course Announcements"
permalink: /courses/
next_link: /courses/buddhism
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
{% capture onclick %}onclick="location.href='{{ course.url }}'"{% endcapture %}
<h3 {{onclick}} class="courselink"><a href="{{ course.url }}">{{ course.title }}</a></h3>

<div class="coursedesc">
  <div class="descrow">
    <div {{onclick}} class="cicon"><i class="{{ course.icon }}"></i></div>
    <div class="cdesc">{{ course.description | markdownify }}</div>
    <div class="ccredits"><i class="fas fa-weight-hanging"></i> {{ course.time }}</div>
  </div>
  <div class="featuringrow">
    <div class="flabel"><strong>Featuring</strong>:</div>
    {% if course.lecturers %}<div class="lecturers"><i class="fas fa-microphone-alt"></i> {% include content_authors_string.html link=true authors=course.lecturers %}</div>{% endif %}
    {% if bauthors.size > 0 %}<div class="bauthors"><i class="far fa-address-book"></i> {% include content_authors_string.html link=true authors=bauthors %}</div>{% endif %}
  </div>
</div>

{% endfor %}

## External Courses

### [An Introduction to Classical Tibetan](http://www.nettletibetan.ca/){:ga-event-value="0.5"}
{:onclick="location.href='http://www.nettletibetan.ca/'" .courselink}

<div class="coursedesc">
  <div class="descrow">
    <div onclick="location.href='http://www.nettletibetan.ca/'" class="cicon"><i class="fas fa-tram"></i></div>
    <div class="cdesc">Two courses on the Tibetan Language from the University of Toronto, taking you from identifying words all the way to translating your first Buddhist text. Note: This class assumes prior comfort with <a target="_blank" href="https://en.wikipedia.org/wiki/Tibetan_script">the Tibetan script</a>. If that's not you, see e.g. <i>Translating Buddhism from Tibetan</i> Ch.1–8 before taking this course.</div>
    <div class="ccredits"><i class="fas fa-weight-hanging"></i> 2</div>
  </div>
</div>


### [Shin Buddhism in Modern Culture](http://bschawaii.org/shindharmanet/course/){:ga-event-value="1.5"}
{:onclick="location.href='http://bschawaii.org/shindharmanet/course/'" .courselink}

<div class="coursedesc">
  <div class="descrow">
    <div onclick="location.href='http://bschawaii.org/shindharmanet/course/'" class="cicon"><i class="fas fa-street-view"></i></div>
    <div class="cdesc">A short, interactive overview of Jodo Shinshu, from Shinran's life to Japanese Buddhism in the modern United States.</div>
    <div class="ccredits"><i class="fas fa-weight-hanging"></i> 1</div>
  </div>
</div>

### [Human Behavioral Biology](https://youtube.com/playlist?list=PL848F2368C90DDC3D){:ga-event-value="3"}
{:onclick="location.href='https://youtube.com/playlist?list=PL848F2368C90DDC3D'" .courselink}

<div class="coursedesc">
  <div class="descrow">
    <div onclick="location.href='https://youtube.com/playlist?list=PL848F2368C90DDC3D'" class="cicon"><i class="fas fa-baby"></i></div>
    <div class="cdesc">A stunning lecture series by Robert Sapolsky on what makes people tick. Required watching for everyone who has to deal with humans.</div>
    <div class="ccredits"><i class="fas fa-weight-hanging"></i> 2</div>
  </div>
</div>

### [Modern and Contemporary American Poetry](https://www.coursera.org/learn/modpo){:ga-event-value="3"}
{:onclick="location.href='https://www.coursera.org/learn/modpo'" .courselink}

<div class="coursedesc">
  <div class="descrow">
    <div onclick="location.href='https://www.coursera.org/learn/modpo'" class="cicon"><i class="fas fa-feather-alt"></i></div>
    <div class="cdesc">An excellent introduction to the world of 20th Century, American poetry from the University of Pennsylvania's graduate school, "ModPo" teaches you not only the history of the field but more how to approach and read a modern poem.
    This course is highly recommended for anyone who likes poetry, but who never "got" this modern stuff.</div>
    <div class="ccredits"><i class="fas fa-weight-hanging"></i> 2</div>
  </div>
</div>

## Open Courseware @MIT

OBU Courses are loosely modeled on [MIT's Open Courseware](https://ocw.mit.edu){:target="_blank"}, which have provided free syllabi and other course materials for a large number of their Undergraduate and Graduate-level courses since 2001. For OBU Students, I especially recommend checking out:

- [The Challenge of World Poverty](https://ocw.mit.edu/courses/economics/14-73-the-challenge-of-world-poverty-spring-2011/){:.f3}
  - To understand the drivers, traps, and opportunities for global poverty with Nobel Laureates Abhijit Banerjee and Esther Duflo.
{:.mb-2}

- [An Introduction to Biology](https://ocw.mit.edu/courses/biology/7-012-introduction-to-biology-fall-2004/){:.f3}
  - To learn about the principles and methods of the modern life sciences.
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
