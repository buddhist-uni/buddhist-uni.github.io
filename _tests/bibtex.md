---
title: "Bibtex Rendering Tests"
---
{% assign testc = site.content | find: "url", "/content/excerpts/buddhist-thought_williams-paul" %}
```
{% capture bib %}{% include content.bibtex content=testc %}{% endcapture %}{{ bib }}
```

Bibtex contains opener: {% unless bib contains "@incollection{" %}FAIL ❌{% else %}Pass ✅{% endunless %}  
Bibtex wraps title caps: {% unless bib contains "{S}elections" %}FAIL ❌{% else %}Pass ✅{% endunless %}  
Bibtex properly italicizes within a title: {% unless bib contains "\textit{Buddhist Thought}" %}FAIL ❌{% else %}Pass ✅{% endunless %}  
Bibtex contains unwrapped year: {% if bib contains "year={" %}FAIL ❌{% elsif bib contains "year=2000," %}Pass ✅{% else %}FAIL ❌{% endif %}  

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

{% assign testc = site.content | find: "url", "/content/articles/anagarika-munindra-and-vipassana_pryor" %}
```
{% capture bib %}{% include content.bibtex content=testc %}{% endcapture %}{{ bib }}
```

Test is valid (piece has doi source): {% if testc.source_url contains "doi.org" %}Pass ✅{% else %}FAIL ❌{% endif %}  
Bibtex pulls doi from source: {% if bib contains "doi={" %}Pass ✅{% else %}FAIL ❌{% endif %}  
