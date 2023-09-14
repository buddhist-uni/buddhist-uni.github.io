---
layout: page
section: courses
slug: courses
title: Courses
rss_url: feed.xml
rss_title: "Course Announcements"
custom_css: [courselist]
permalink: /courses/
next_link: /courses/buddhism
image_width: 1280
image: "https://www.buddhistuniversity.net/imgs/burmese-nuns-studying.jpg"
image_center_x: 20%
image_center_y: 46%
big_image: "https://upload.wikimedia.org/wikipedia/commons/a/ad/Zhaya_Theingyi-Sagaing-Myanmar-02-gje.jpg"
big_width: 2832
big_height: 1896
banner_info: <a href="https://commons.wikimedia.org/wiki/File:Zhaya_Theingyi-Sagaing-Myanmar-02-gje.jpg">Gerd Eichmann</a>, <a href="https://creativecommons.org/licenses/by-sa/3.0">BY-SA 3.0</a>
---

The Open Buddhist University organizes [content from across the Web]({% link library.md %}) into free, self-directed syllabi on a variety of topics in Buddhist Studies.

## About Our Courses

We currently offer {{ site.data.course_order.size }} courses on the fundamentals of Buddhism.  
**Note:** None of our courses offer degrees or certificates and therefore they don't require any enrollment.
Just click a card below to begin!

### Key

- Click the card to begin the course
- Each course has a unique icon (e.g. <i class="fas fa-chalkboard-teacher"></i>) to identify it.
- <i class="fas fa-person-chalkboard"></i> = Lectures by:
- <i class="far fa-address-book"></i> = Books by:
- {:.ccredits}<i class="far fa-clock"></i> = Approximate time to complete the course

### Interactive Components

If you'd like to discuss what you're learning, feel free to post your questions or thoughts on [the SuttaCentral Discourse Forum](https://discourse.suttacentral.net/?u=khemarato.bhikkhu){:target="_blank"} or [email us](mailto:theopenbuddhistuniversity@gmail.com).
Some courses contain links to (optional) Google Forms which serve for homework assignments and to collect course feedback.
This site may use cookies to enhance your experience, but you can turn this off at any time in [settings](/settings).

## Our Courses

{% for cslug in site.data.course_order %}
{% assign course = site.courses | find: "slug", cslug %}
{% assign courseware = site.content | where: "course", cslug %}
{% assign booklets = courseware | where: "category", "booklets" %}
{% assign textbooks = courseware | where: "category", "monographs" | concat: booklets | sort: "course_mins", "first" | reverse %}
{% assign bauthors = '' | split: '' %}
{% for b in textbooks %}{% assign tbas = b.authors %}{% unless tbas.size > 3%}{% for tba in tbas %}{% unless bauthors contains tba %}{% assign bauthors = bauthors | push: tba %}{% break %}{% endunless %}{% endfor %}{% endunless %}{% endfor %}
{% if bauthors.size >= 5 %}{% assign bauthors = bauthors | slice: 0, 3 | push: "others" %}{% endif %}
{% capture onclick %}onclick="location.href='{{ course.url }}'"{% endcapture %}
{% assign time = courseware | map: "course_mins" | sum | times: course.course_time_multiplier | divided_by: 600.0 | round | times: 10 %}
{% include course-card.html slug=course.slug url=course.url title=course.title icon=course.icon description=course.description time=time lecturers=course.lecturers bauthors=bauthors %}
{% endfor %}

## External Courses

Courses hosted on other websites.
{% assign authors = "analayo" | split: "," %}
{% include course-card.html
  url="https://agamaresearch.dila.edu.tw/wp-content/uploads/2014/06/lectures2012.htm"
  value="0.6"
  title="The Arahant and the Four Noble Truths"
  icon="fas fa-mountain"
  description="The prequel course to Ven. Analayo's <i>Tranquility and Insight</i> course above, this 11 lecture series covers Madhyama-āgama Chapters 3 and 4, centering on the Venerable Arahants at the time of the Buddha."
  time="20"
  lecturers=authors
%}

{% assign authors = "Frances Garret" | split: "," %}
{% include course-card.html
  url="https://www.nettletibetan.ca/"
  value="0.5"
  title="An Introduction to Classical Tibetan"
  icon="fas fa-cable-car"
  description='Two courses introducing the Tibetan Language courtesy of the University of Toronto, taking you from identifying words all the way up to translating your first Buddhist text. <b>Note</b>: This class assumes prior comfort with the Tibetan script. If that\'s not you, see e.g. <i>Translating Buddhism from Tibetan</i> Ch.1–8 before taking this course.'
  time="160"
  lecturers=authors
%}

{% include course-card.html
  url="https://bschawaii.org/shindharmanet/course/"
  value="0.5"
  title="Shin Buddhism in Modern Culture"
  icon="fas fa-street-view"
  description="A short, interactive overview of Jodo Shinshu, from Shinran's life to Japanese Buddhism in the modern United States."
  time="30"
%}


{% assign authors = "Robert Sapolsky" | split: "," %}
{% include course-card.html
  url="https://youtube.com/playlist?list=PL848F2368C90DDC3D"
  value="3"
  title="Human Behavioral Biology"
  icon="fas fa-person-circle-exclamation"
  description="Robert Sapolsky's classic Stanford course explains what makes people tick and should be considered required watching for anyone who interacts with humans. This lecture series would go on to become the 2017 NYT best-seller, <i>Behave: The Biology of Humans at Our Best and Worse</i>."
  time="40"
  lecturers=authors
%}


{% assign authors = "Al Filreis" | split: "," %}
{% include course-card.html
  url="https://www.coursera.org/learn/modpo"
  value="3"
  title="Modern and Contemporary American Poetry"
  icon="fas fa-feather-alt"
  description='An excellent introduction to 20th Century, American poetry from the University of Pennsylvania graduate school, "ModPo" teaches you not just the history of the poems, but how to read them. This course is highly recommended for anyone who likes poetry, but who never "got" that modern stuff.'
  time="90"
  lecturers=authors
%}


{% assign authors = "Timothy Snyder" | split: "," %}
{% include course-card.html
  url="https://youtube.com/playlist?list=PLh9mgdi4rNewfxO7LhBoz_1Mx1MaO6sw_"
  value="2"
  title="The Making of Modern Ukraine"
  icon="fac-ukraine"
  description='Professor Timothy Snyder gives the deep history of Eastern Europe and the formation of the Ukrainian nation, discussing along the way the big question of why we should study history at all. Be sure to check out the course syllabus in addition to the lectures as the readings are an important part of the course.'
  time="40"
  lecturers=authors
%}

## Open Courseware @MIT

OBU Courses are loosely modeled on [MIT's Open Courseware](https://ocw.mit.edu){:target="_blank"}, which have provided free syllabi and other course materials for a large number of their Undergraduate and Graduate-level courses since 2001. For OBU Students, I especially recommend checking out:
{% comment %}These .f3 classes below are used by BuggyTrack{% endcomment %}
- [The Challenge of World Poverty](https://ocw.mit.edu/courses/economics/14-73-the-challenge-of-world-poverty-spring-2011/){:.f3 ga-event-value="2"}
  - To understand the drivers, traps, and opportunities for global poverty with Nobel Laureates Abhijit Banerjee and Esther Duflo.
{:.mb-2}

- [An Introduction to Biology](https://ocw.mit.edu/courses/biology/7-012-introduction-to-biology-fall-2004/){:.f3 ga-event-value="2"}
  - To learn about the principles and methods of the modern life sciences.
{:.mb-2}

- [Sexual and Gender Identities](https://ocw.mit.edu/courses/womens-and-gender-studies/wgs-110j-sexual-and-gender-identities-spring-2016/){:.f3 ga-event-value="0.5"}
  - To learn the surprising history of gender in America.
{:.mb-2}

- [The Rise of Modern Science](https://ocw.mit.edu/courses/science-technology-and-society/sts-003-the-rise-of-modern-science-fall-2010/index.htm){:.f3 ga-event-value="0.5"}
  - To break down the ahistorical mythology of modern science by taking a closer look at its primary sources.
{:.mb-2}

- [Gender and Representation of Asian Women](https://ocw.mit.edu/courses/anthropology/21a-470j-gender-and-representation-of-asian-women-spring-2010/){:.f3 ga-event-value="0.5"}
  - To recognize how politics shape our perceptions.
{:.mb-2}

- [Communicating Across Cultures](https://ocw.mit.edu/courses/21g-019-communicating-across-cultures-spring-2005/){:.f3 ga-event-value="0.5"}
  - To probe the challenges of intercultural dialogue with theoretical frameworks and practical exercises.
{:.mb-2}
