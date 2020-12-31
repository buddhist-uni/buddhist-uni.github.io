---
title: "A New Reading List on Meditation"
---

Today I'm proud to finally announce [the meditation reading list]({% link _tags/meditation.md %}).

It might strike some as odd that a site about Buddhism could exist for months without a section on meditation, yet for as pivotal a psychotechnology as meditation is, it is also a rather contentious and challenging topic to teach---especially over the internet.  While far from the final word on the subject, the bibliography here should provide a good starting point for the study and practice of meditation. And while far from complete, the reading list already contains some of my favorite talks, articles, and songs (!) which I highly recommend you check out:

{% assign cslugs = 'have-you-come-here-to-die_brahm,how-to-meditate_yuttadhammo,mindfulness-intervention-to-youth-issues-in-vietnam_le-trieu,mindfulness-according-to-early-sources_analayo,addressing-the-american-problem_stein-zac,liberative-role-of-piti-sukha_arbel,anything-you-synthesize_american-dollar,wheel_sohn,why-practice_auclair' | split: ',' %}
{% assign content = site.content | where_exp: "c", "cslugs contains c.slug" %}
<div class="narrow">{% include content_list.html contents=content %}</div>

Wishing you a peaceful and productive meditation practice,  
Than Khemarato  
The Librarian

