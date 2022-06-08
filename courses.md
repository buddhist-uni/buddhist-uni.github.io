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
image: "https://illeakyw.sirv.com/Images/banners/burmese-nuns-studying.jpg"
image_center_x: 20%
image_center_y: 46%
big_image: "https://upload.wikimedia.org/wikipedia/commons/a/ad/Zhaya_Theingyi-Sagaing-Myanmar-02-gje.jpg"
banner_info: <a href="https://commons.wikimedia.org/wiki/File:Zhaya_Theingyi-Sagaing-Myanmar-02-gje.jpg">Gerd Eichmann</a>, <a href="https://creativecommons.org/licenses/by-sa/3.0">BY-SA 3.0</a>
---

<script>
function goto(u,v) {
   if (typeof ga === 'function') {
     let w = Math.floor(v);
     ga('send','event','Outbound Link','click',u,(Math.random()<v-w)?Math.ceil(v):w);
   }
   location.href=u;
}
</script>

The Open Buddhist University organizes [content from across the Web]({% link library.md %}) into free, self-directed syllabi on a variety of topics in Buddhist Studies.

## About Our Courses

We currently offer {{ site.data.course_order.size }} courses on the fundamentals of Buddhism.  
**Note:** None of our courses offer degrees or certificates.

### Icon Key

- <i class="fas fa-chalkboard-teacher"></i> = A unique icon to identify the course
- <i class="far fa-address-book"></i> = Books by:
- <i class="fas fa-person-chalkboard"></i> = Lectures by:
- {:.ccredits}<i class="fas fa-weight-hanging"></i> = <a target="_blank" href="https://en.wikipedia.org/wiki/Course_credit#Credit_hours">Semester Credit Hours</a>

### Interactive Components

If you'd like to discuss what you're learning, feel free to post your questions or thoughts on [the SuttaCentral Discourse Forum](https://discourse.suttacentral.net/?u=khemarato.bhikkhu){:target="_blank"} or [email us](mailto:theopenbuddhistuniversity@gmail.com).
Some courses contain links to (optional) Google Forms which serve for homework assignments and to collect course feedback.
This site may use cookies to enhance your experience, but you can turn this off at any time in [settings](/settings).

## Our Courses

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
    {% if course.lecturers %}<div class="lecturers"><i class="fas fa-person-chalkboard"></i> {% include_cached content_authors_string.html link=true authors=course.lecturers %}</div>{% endif %}
    {% if bauthors.size > 0 %}<div class="bauthors"><i class="far fa-address-book"></i> {% include_cached content_authors_string.html link=true authors=bauthors %}</div>{% endif %}
  </div>
</div>

{% endfor %}

## External Courses

Courses hosted on other websites.

### [The Arahant and the Four Noble Truths](http://agamaresearch.dila.edu.tw/wp-content/uploads/2014/06/lectures2012.htm){:ga-event-value="0.6"}
{:onclick="goto('http://agamaresearch.dila.edu.tw/wp-content/uploads/2014/06/lectures2012.htm,0.6)" .courselink}

<div class="coursedesc">
  <div class="descrow">
    <div onclick="goto('http://agamaresearch.dila.edu.tw/wp-content/uploads/2014/06/lectures2012.htm',0.6)" class="cicon"><i class="fas fa-mountain"></i></div>
    <div class="cdesc">The prequel course to Ven. Analayo's <i>Tranquility and Insight</i> course above, this 11 lecture series covers Madhyama-āgama Chapters 3 and 4, centering on the Venerable Arahants at the time of the Buddha.</div>
    <div class="ccredits"><i class="fas fa-weight-hanging"></i> 1</div>
  </div>
</div>

### [An Introduction to Classical Tibetan](http://www.nettletibetan.ca/){:ga-event-value="0.5"}
{:onclick="goto('http://www.nettletibetan.ca/',0.5)" .courselink}

<div class="coursedesc">
  <div class="descrow">
    <div onclick="goto('http://www.nettletibetan.ca/',0.5)" class="cicon"><i class="fas fa-person-hiking"></i></div>
    <div class="cdesc">Two courses introducing the Tibetan Language courtesy of the University of Toronto, taking you from identifying words all the way up to translating your first Buddhist text. <b>Note</b>: This class assumes prior comfort with <a target="_blank" href="https://en.wikipedia.org/wiki/Tibetan_script">the Tibetan script</a>. If that's not you, see e.g. <i>Translating Buddhism from Tibetan</i> Ch.1–8 before taking this course.</div>
    <div class="ccredits"><i class="fas fa-weight-hanging"></i> 4</div>
  </div>
</div>


### [Shin Buddhism in Modern Culture](http://bschawaii.org/shindharmanet/course/){:ga-event-value="1.5"}
{:onclick="goto('http://bschawaii.org/shindharmanet/course/',1.5)" .courselink}

<div class="coursedesc">
  <div class="descrow">
    <div onclick="goto('http://bschawaii.org/shindharmanet/course/',1.5)" class="cicon"><i class="fas fa-street-view"></i></div>
    <div class="cdesc">A short, interactive overview of Jodo Shinshu, from Shinran's life to Japanese Buddhism in the modern United States.</div>
    <div class="ccredits"><i class="fas fa-weight-hanging"></i> 1</div>
  </div>
</div>

### [Human Behavioral Biology](https://youtube.com/playlist?list=PL848F2368C90DDC3D){:ga-event-value="3"}
{:onclick="goto('https://youtube.com/playlist?list=PL848F2368C90DDC3D',3)" .courselink}

<div class="coursedesc">
  <div class="descrow">
    <div onclick="goto('https://youtube.com/playlist?list=PL848F2368C90DDC3D',3)" class="cicon"><i class="fas fa-person-circle-exclamation"></i></div>
    <div class="cdesc">Robert Sapolsky's classic Stanford course explains what makes people tick and should be considered required watching for anyone who interacts with humans. His lectures went on to become a 2017 best-seller: <i>The Biology of Humans at Our Best and Worse</i>.</div>
    <div class="ccredits"><i class="fas fa-weight-hanging"></i> 2</div>
  </div>
</div>

### [Modern and Contemporary American Poetry](https://www.coursera.org/learn/modpo){:ga-event-value="3"}
{:onclick="goto('https://www.coursera.org/learn/modpo',3)" .courselink}

<div class="coursedesc">
  <div class="descrow">
    <div onclick="goto('https://www.coursera.org/learn/modpo',3)" class="cicon"><i class="fas fa-feather-alt"></i></div>
    <div class="cdesc">An excellent introduction to 20th Century, American poetry from the University of Pennsylvania's graduate school, "ModPo" teaches you not just the history of the poems, but how to read them.
    This course is highly recommended for anyone who likes poetry, but who never "got" that modern stuff.</div>
    <div class="ccredits"><i class="fas fa-weight-hanging"></i> 2</div>
  </div>
</div>

## Open Courseware @MIT

OBU Courses are loosely modeled on [MIT's Open Courseware](https://ocw.mit.edu){:target="_blank"}, which have provided free syllabi and other course materials for a large number of their Undergraduate and Graduate-level courses since 2001. For OBU Students, I especially recommend checking out:

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
