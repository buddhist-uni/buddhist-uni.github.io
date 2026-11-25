---
title: "Assignment Time Tests"
# Stand-ins for content items, reckoned with time=true unless a time is given: the include only reads `pages`, `minutes` and `total_mins`
fixtures:
  - { name: "Minutes", content: { minutes: 45, total_mins: 45.0 }, expect: "(45 mins)" }
  - { name: "Singular", content: { minutes: 1, total_mins: 1.0 }, expect: "(1 min)" }
  - { name: "A recording stays exact", content: { minutes: 23, total_mins: 23.0 }, expect: "(23 mins)" }
  - { name: "A recording rounds to the nearest minute", content: { minutes: 119.5, total_mins: 119.5 }, expect: "(2 hrs)" }
  - { name: "A recording rounds down to nothing", content: { minutes: 0.3, total_mins: 0.3 }, expect: "" }
  - { name: "Just under an hour", content: { minutes: 59, total_mins: 59.0 }, expect: "(59 mins)" }
  - { name: "An hour", content: { minutes: 60, total_mins: 60.0 }, expect: "(1 hr)" }
  - { name: "An hour and a minute", content: { minutes: 61, total_mins: 61.0 }, expect: "(1 hr 1 min)" }
  - { name: "Hours and minutes", content: { minutes: 125, total_mins: 125.0 }, expect: "(2 hrs 5 mins)" }
  - { name: "Uses total_mins, not the page count", content: { pages: "67--76", page_count: 10, total_mins: 50.0 }, expect: "(~1 hr)" }
  - { name: "No size", content: { title: "Sizeless" }, expect: "" }
  - { name: "Comma page list", content: { pages: "1--2, 5--6", total_mins: 8.0 }, expect: "" }
  - { name: "Hidden", time: false, content: { total_mins: 45.0 }, expect: "" }
  - { name: "Minutes given", time: 25, content: { pages: 100, total_mins: 200.0 }, expect: "(~30 mins)" }
  - { name: "A recording's minutes given", time: 23, content: { minutes: 90, total_mins: 90.0 }, expect: "(23 mins)" }
  - { name: "No minutes given", time: 0, content: { total_mins: 45.0 }, expect: "" }
  - { name: "A label", time: "a few minutes a day", content: { total_mins: 45.0 }, expect: "(a few minutes a day)" }
  - { name: "A label starting with a number", time: "2 weeks", content: { total_mins: 45.0 }, expect: "(2 weeks)" }
  - { name: "An empty label", time: "", content: { total_mins: 45.0 }, expect: "" }
# The shortest and longest readings that get each label
steps:
  - ["~5 mins", { total_mins: 0.2 }, { total_mins: 5 }]
  - ["~10 mins", { total_mins: 6 }, { total_mins: 11 }]
  - ["~15 mins", { total_mins: 12 }, { total_mins: 16 }]
  - ["~20 mins", { total_mins: 17 }, { total_mins: 22 }]
  - ["~30 mins", { total_mins: 23 }, { total_mins: 33 }]
  - ["~45 mins", { total_mins: 34 }, { total_mins: 49 }]
  - ["~1 hr", { total_mins: 50 }, { total_mins: 66 }]
  - ["~1.5 hrs", { total_mins: 67 }, { total_mins: 99 }]
  - ["~2 hrs", { total_mins: 100 }, { total_mins: 132 }]
  - ["~3 hrs", { total_mins: 133 }, { total_mins: 198 }]
  - ["~4 hrs", { total_mins: 199 }, { total_mins: 264 }]
  - ["~5 hrs", { total_mins: 265 }, { total_mins: 330 }]
# Real items, with `field: value` checks that the item is still as expected
library:
  - { path: "_content/av/how-to-love-your-problems_courtin-robina.md", field: minutes, value: 70, expect: "(1 hr 10 mins)" }
  - { path: "_content/canon/sn22.86.md", field: minutes, value: 4, expect: "(4 mins)" }
  - { path: "_content/booklets/on-love_jayasaro.md", field: pages, value: 19, expect: "(~45 mins)" }
  - { path: "_content/articles/buddhism-and-modernity_powers-doug.md", field: pages, value: "67--76", expect: "(~20 mins)" }
  - { path: "_content/canon/sn35.238.md", field: pages, value: 3, expect: "(~15 mins)" }
---
Test is valid (`mins_per_page` is 2): {% if site.data.content.mins_per_page == 2.0 %}Pass ✅{% else %}FAIL ❌{% endif %}  

{% for t in page.fixtures -%}
{%- if t.time == nil %}{% assign tm = true %}{% else %}{% assign tm = t.time %}{% endif -%}
{%- capture got %}{% include assignment_time.html content=t.content time=tm %}{% endcapture -%}
{%- capture want %}{% if t.expect != "" %} <span class="assignment_time">{{ t.expect }}</span>{% endif %}{% endcapture -%}
{{ t.name }}: {% if got == want %}Pass ✅{% else %}FAIL ❌ got `{{ got | strip_html }}`, expected `{{ t.expect }}`{% endif %}  
{% endfor %}
{% for t in page.steps -%}
{%- capture got %}{% for e in t offset: 1 %}{% include assignment_time.html content=e time=true %}{% endfor %}{% endcapture -%}
{%- capture want %} <span class="assignment_time">({{ t[0] }})</span> <span class="assignment_time">({{ t[0] }})</span>{% endcapture -%}
{{ t[0] }} from {{ t[1].total_mins }} to {{ t[2].total_mins }}: {% if got == want %}Pass ✅{% else %}FAIL ❌ got `{{ got | strip_html }}`{% endif %}  
{% endfor %}
{% for t in page.library -%}
{%- assign c = site.content | find: "path", t.path -%}
{%- capture got %}{% include assignment_time.html content=c time=true %}{% endcapture -%}
{%- capture want %} <span class="assignment_time">{{ t.expect }}</span>{% endcapture -%}
{{ t.path }}: {% if c[t.field] != t.value %}FAIL ❌ test is invalid, found `{{ c[t.field] }}`{% elsif got == want %}Pass ✅{% else %}FAIL ❌ got `{{ got | strip_html }}`, expected `{{ t.expect }}`{% endif %}  
{% endfor %}
{% capture blurb %}{% include content_blurb.html category="booklets" slug="on-love_jayasaro" %}{% include content_box.html category="booklets" slug="on-love_jayasaro" %}{% include inline_content.html category="booklets" slug="on-love_jayasaro" %}{% endcapture %}
Includes print no time on pages without `assignment_times`: {% if blurb contains "assignment_time" %}FAIL ❌{% else %}Pass ✅{% endif %}  
{% capture timed %}{% include content_blurb.html category="booklets" slug="on-love_jayasaro" time="x" %}{% include content_box.html category="booklets" slug="on-love_jayasaro" time="x" %}{% include inline_content.html category="booklets" slug="on-love_jayasaro" time="x" %}{% endcapture %}
Includes pass a time on: {% assign n = timed | split: "(x)" | size %}{% if n == 4 %}Pass ✅{% else %}FAIL ❌{% endif %}
