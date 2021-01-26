---
layout: nil
---
importScripts("/assets/js/lunr.min.js");
importScripts("/assets/js/utils.js");

// Parameters
var BMAX = 250; // Max blurb size in characters
var RMAX = 100;

{%- assign ccurly = "}" -%}
{%- assign ocurly = "{" -%}
{%- assign backtoback = ccurly | append: ocurly -%}
{%- assign doubleo = ocurly | append: ocurly -%}
{%- assign doublec = ccurly | append: ccurly -%}
{%- assign pagesWithoutContent = 'Authors,Search' | split: ',' -%}
var store = { {% assign all = site.documents | concat: site.pages %}
  {% for p in all %}
    {% unless p.title %}{% continue %}{% endunless %}
    {% if p.url contains "/tests/" or pagesWithoutContent contains p.title %}{% continue %}{% endif %}
    "{{ p.url | slugify }}": {
        "type": "{{ p.collection | default: 'pages' }}",
        "title": {{ p.title | markdownify | strip_html | strip_newlines | jsonify }},
        "description": {{ p.description | markdownify | strip_html | strip_newlines | jsonify }},
        "tags": {{ p.tags | join: ' ' | replace: '-', ' ' | jsonify }},
        "category": {{ p.category | jsonify }},
        "boost": {% if p.status == 'featured' %}4{% elsif p.status == 'rejected' %}0.1{% elsif p.layout == 'imagerycoursepart' %}2{% elsif p.course %}2{% elsif p.collection == 'courses' %}8{% elsif p.collection == 'tags' %}5{% else %}1{% endif %},
        "authors": {% capture a %}{% case p.collection %}{% when "courses" %}{% include content_authors_string.html authors=p.lecturers %}{% when "content" %}{% include content_authors_string.html authors=p.authors %}{% else %}{{ p.author }}{% endcase %}{% endcapture %}"{{ a | strip | xml_escape }}",
        "content": {% assign cpieces = p.content | strip | replace: doubleo, ocurly | replace: doublec, ccurly | replace: backtoback, "" | split: ocurly %}{% assign content = "" %}{% for p in cpieces %}{% assign s = p | split: ccurly | last %}{% assign content = content | append: s %}{% endfor %}{{ content | markdownify | strip_newlines | replace: "</", ' </' | strip_html | jsonify }},
        "url": "{{ p.url }}"
    }{% unless forloop.last %},{% endunless %}
  {% endfor %}
};

var idx = lunr(function () {
    this.ref('id'); this.field('title', { boost: 10 });
    this.field('authors', { boost: 2 }); this.field('content');
    this.field('tags', { boost: 4 }); this.field('description', { boost: 2 });
    this.field('category', { boost: 0.5 }); this.field('type', { boost: 0.3 });
    this.metadataWhitelist = ['position']
    for (var key in store) {
        var v = store[key];
        this.add({
            'id': key, 'title': utils.unaccented(v.title),
            'authors': utils.unaccented(v.authors), 'content': utils.unaccented(v.content),
            'tags': v.tags, 'description': utils.unaccented(v.description),
            'category': v.category, 'type': v.type
      }, {boost: v.boost});
    }
});

function getPositions(result, field) {
    var positions = [];
    var md = result.matchData.metadata;
    for (var searchTerm in md) {
        var fieldResults = md[searchTerm][field];
        if (!fieldResults) continue;
        for (var p in fieldResults.position) sortedInsert(positions, fieldResults.position[p][0]);
    }
    return positions;
}

function addMatchHighlights(result, blurb, fromfield, startindex, endindex) {
    var startindex = startindex || 0;
    var endindex = endindex || blurb.length;
    var ranges = new Ranges();
    let md = result.matchData.metadata;
    var i = 0; var j = 0;
    for (var searchTerm in md) {
        if (!md[searchTerm][fromfield]) continue;
        for (var mi in md[searchTerm][fromfield].position) {
            let m = md[searchTerm][fromfield].position[mi];
            i = m[0]; j = i+m[1];
            if (i < endindex && j > startindex) {
                ranges.add([(startindex>i?startindex:i)-startindex, j-startindex]);
            }
        }
    }
    i = ranges.array.length - 1;
    var ret = blurb;
    while (i >= 0) {
        ret = ret.substring(0,ranges.array[i][0]) + 
            '<strong>' + ret.substring(ranges.array[i][0],ranges.array[i][1]) +
            '</strong>' + ret.substring(ranges.array[i][1], ret.length);
        i--;
    }
    return ret;
}

function getBlurbForResult(result, item, positions) {
    var titleMatch = false;
    let md = result.matchData.metadata;
    for (var searchTerm in md) {
        if (md[searchTerm]['title']) {
            titleMatch = true;
            break;
        }
    }
    if ((titleMatch || positions.length == 0) && item.description){
      var ret = item.description;
      if (item.description.length > BMAX)
        ret = item.description.substring(0, BMAX) + "...";
      return addMatchHighlights(result, ret, 'description');
    }
    // Calculate the best section of the content to blurb
    var best_i = -1;
    var best_n = 0;
    for (var i in positions) {
        var n = 1;
        var j = i+1;
        while (j < positions.length) {
            if (positions[j] > positions[i] + BMAX) break;
            n++; j++;
        }
        if (n > best_n) {
            best_n = n;
            best_i = i;
        }
    }
    i = positions[best_i];
    j = positions[best_i + best_n - 1];
    var m = (i+j)>>1;
    var startindex = m - (BMAX>>1);
    var pre = true;
    if (startindex <= 0){ startindex = 0; pre = false; }
    var endindex = startindex + BMAX;
    var ret = item.content.substring(startindex,endindex);
    ret = addMatchHighlights(result, ret, 'content', startindex, endindex);
    if (endindex >= item.content.length) return (pre?'...':'') + ret;
    return (pre?'...':'') + ret + "...";
}

function categoryName(c) {
    switch(c) {
        case 'av': return 'Recording';
        case 'articles': return "Article";
        case 'booklets': return "Book";
        case 'monographs': return "Book";
        case 'papers': return "Paper";
        case 'essays': return 'Essay';
        case 'canon': return 'Canonical Work';
        case 'reference': return 'Reference Work';
        case 'excerpts': return 'Excerpt';
    }
    return 'Library Item';
}

function displaySearchResult(result, item) {
    var positions = getPositions(result, 'content');
    var blurb = getBlurbForResult(result, item, positions);
    var type = null;
    switch (item.type) {
        case 'courses': type = 'Course'; break;
        case 'content': type = categoryName(item.category); break;
        case 'posts': type = 'Blog Post'; break;
        case 'journals': type = 'Journal'; break;
        case 'authors': type = 'Author'; break; 
        case 'publishers': type = 'Publisher'; break;
        case 'tags': type = 'Bibliography'; break;
        case 'series': type = 'Series'; break;
    }
    var ret = '<li><a href="' + item.url + '"><h3>' + addMatchHighlights(result, item.title, 'title') + '</h3>';
    if (type) ret += '<span class="Label Label--inline Label--large Label--gray-darker mr-1">' + type + '</span>';
    return ret + '</a><p>' + blurb + '</p></li>';
}

function displaySearchResults(results) {
    if (results.length) {
      var ret = '';
      for (var i in results) {
        if (i > RMAX) break;
        ret += displaySearchResult(results[i], store[results[i].ref]);
      }
      return ret;
    } else {
      return '<li>No results found</li>';
    }
}

self.onmessage = function(e) {
    var results = idx.search(e.data);
    if (!results.length){
      var words = e.data.split(" ");
      if (words.find(function(w){ return w.length <= 2; }) == undefined)
        results = idx.search(words.join("~1 ") + "~1");
    }
    self.postMessage({
      "html": displaySearchResults(results),
      "q": e.data
    });
}


