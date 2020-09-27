---
layout: page
title: Courses
permalink: /courses/
---

The University organizes [content]({% link library.md %}) from [across the Web]({% link sources.md %}) into self-paced, free courses on a variety of topics in Buddhist Studies. We currently offer 4 courses on the fundamentals of Buddhism:

{% for cslug in site.data.course_order %}
{% assign course = site.courses | where: "slug", cslug | first %}
### [<i class="{{ course.icon }}"></i> {{ course.title }}]({{ course.url }})
{{ course.description }}  
{% endfor %}

