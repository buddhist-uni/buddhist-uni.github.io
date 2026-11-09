---
title: "Assignment Time Tests"
# Stand-ins for content items: the include only reads `pages` and `total_mins`
fixtures:
  - { name: "Minutes", content: { total_mins: 45.0 }, expect: "(45 mins)" }
  - { name: "Singular", content: { total_mins: 1.0 }, expect: "(1 min)" }
  - { name: "Rounds to nearest", content: { total_mins: 7.5 }, expect: "(8 mins)" }
  - { name: "Just under an hour", content: { total_mins: 59.0 }, expect: "(59 mins)" }
  - { name: "An hour", content: { total_mins: 60.0 }, expect: "(1 hr)" }
  - { name: "An hour and a minute", content: { total_mins: 61.0 }, expect: "(1 hr 1 min)" }
  - { name: "Hours and minutes", content: { total_mins: 125.0 }, expect: "(2 hrs 5 mins)" }
  - { name: "Uses total_mins, not the page count", content: { pages: "67--76", page_count: 10, total_mins: 20.0 }, expect: "(20 mins)" }
  - { name: "No size", content: { title: "Sizeless" }, expect: "" }
  - { name: "Rounds down to nothing", content: { total_mins: 0.4 }, expect: "" }
  - { name: "Comma page list", content: { pages: "1--2, 5--6", total_mins: 8.0 }, expect: "" }
  - { name: "Not enabled", enabled: false, content: { total_mins: 45.0 }, expect: "" }
  - { name: "notime", notime: true, content: { total_mins: 45.0 }, expect: "" }
  - { name: "notime as a string", notime: "true", content: { total_mins: 45.0 }, expect: "" }
# Real items, with `field: value` checks that the item is still as expected
library:
  - { path: "_content/av/how-to-love-your-problems_courtin-robina.md", field: minutes, value: 70, expect: "(1 hr 10 mins)" }
  - { path: "_content/booklets/on-love_jayasaro.md", field: pages, value: 19, expect: "(38 mins)" }
  - { path: "_content/articles/buddhism-and-modernity_powers-doug.md", field: pages, value: "67--76", expect: "(20 mins)" }
  - { path: "_content/canon/sn35.238.md", field: pages, value: 3, expect: "(15 mins)" }
---
Test is valid (`mins_per_page` is 2): {% if site.data.content.mins_per_page == 2.0 %}Pass ✅{% else %}FAIL ❌{% endif %}  

{% for t in page.fixtures -%}
{%- if t.enabled == false %}{% assign on = false %}{% else %}{% assign on = true %}{% endif -%}
{%- capture got %}{% include assignment_time.html content=t.content enabled=on notime=t.notime %}{% endcapture -%}
{%- capture want %}{% if t.expect != "" %} <span class="assignment_time">{{ t.expect }}</span>{% endif %}{% endcapture -%}
{{ t.name }}: {% if got == want %}Pass ✅{% else %}FAIL ❌ got `{{ got | strip_html }}`, expected `{{ t.expect }}`{% endif %}  
{% endfor %}
{% for t in page.library -%}
{%- assign c = site.content | find: "path", t.path -%}
{%- capture got %}{% include assignment_time.html content=c enabled=true %}{% endcapture -%}
{%- capture want %} <span class="assignment_time">{{ t.expect }}</span>{% endcapture -%}
{{ t.path }}: {% if c[t.field] != t.value %}FAIL ❌ test is invalid, found `{{ c[t.field] }}`{% elsif got == want %}Pass ✅{% else %}FAIL ❌ got `{{ got | strip_html }}`, expected `{{ t.expect }}`{% endif %}  
{% endfor %}
{% capture blurb %}{% include content_blurb.html category="booklets" slug="on-love_jayasaro" %}{% include content_box.html category="booklets" slug="on-love_jayasaro" %}{% include inline_content.html category="booklets" slug="on-love_jayasaro" %}{% endcapture %}
Includes print no time on pages without `assignment_times`: {% if blurb contains "assignment_time" %}FAIL ❌{% else %}Pass ✅{% endif %}  
