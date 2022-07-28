---
title: "Bibtex Tests"
---

{% assign testc = site.content | find: "url", "/content/monographs/architects-of-buddhist-leisure_mcdaniel" %}
```
{% capture bib %}{% include content.bibtex content=testc %}{% endcapture %}{{ bib }}
```

Test is valid (content has publisher but no address): {% if testc.address %}FAIL ❌{% else %}{% if testc.publisher %}Pass ✅{% else %}FAIL ❌{% endif %}{% endif %}  
Books pull address from publisher: {% if bib contains "Honolulu" %}Pass ✅{% else %}FAIL ❌{% endif %}  
Publisher pulls name from DB: {% if bib contains "University of Hawai'i Press" %}Pass ✅{% else %}FAIL ❌{% endif %}  

{% assign testc = site.content | find: "url", "/content/booklets/buddhist-wheel-symbol_karunaratne" %}
```
{% capture bib %}{% include content.bibtex content=testc %}{% endcapture %}{{ bib }}
```

Test is valid (content has series but no publisher or address): {% if testc.publisher or testc.address %}FAIL ❌{% else %}{% if testc.series %}Pass ✅{% else %}FAIL ❌{% endif %}{% endif %}  
Bibtex pulls publisher from series: {% if bib contains "publisher={" %}Pass ✅{% else %}FAIL ❌{% endif %}  
Bibtex makes this a book (due to having a publisher): {% if bib contains "@book{" %}Pass ✅{% else %}FAIL ❌{% endif %}  
Bibtex pulls the address from the publisher: {% if bib contains "address={" %}Pass ✅{% else %}FAIL ❌{% endif %}  
