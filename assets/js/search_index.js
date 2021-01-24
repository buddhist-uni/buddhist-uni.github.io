---
layout: nil
---
importScripts("/assets/js/lunr.min.js");
importScripts("/assets/js/utils.js");

// Parameters
var BMAX = 250; // Max blurb size in characters
var RMAX = 100;

var defaultComparer = function (a, b) { return (a > b); };
function locationOf(array, element, comparer, start, end) {
    if (array.length === 0)
        return -1;
    if (!comparer)
        comparer = defaultComparer;
    start = start || 0;
    if (end === null || end === undefined)
      end = array.length-1;
    var pivot = (start + end) >> 1;  // should be faster than dividing by 2
    if (comparer(element, array[pivot])) {
        return (start==end)? pivot+1: locationOf(array, element, comparer, pivot+1, end);
    }
    if (start==end) return pivot;
    return locationOf(array, element, comparer, start, pivot);
 };

function sortedInsert(array, element) {
    array.splice(locationOf(array, element), 0, element);
    return array;
}

{%- assign ccurly = "}" -%}
{%- assign ocurly = "{" -%}
{%- assign backtoback = ccurly | append: ocurly -%}
var store = { {% assign all = site.documents | concat: site.pages %}
  {% for p in all %}
    {% unless p.title %}{% continue %}{% endunless %}
    "{{ p.url | slugify }}": {
        "type": "{{ p.collection }}",
        "title": {{ p.title | markdownify | strip_html | strip_newlines | jsonify }},
        "description": {{ p.description | jsonify }},
        "tags": {{ p.tags | jsonify | replace: '-', ' ' }},
        "category": {{ p.category | jsonify }},
        "boost": {% if p.status == 'featured' %}4{% elsif p.layout == 'imagerycoursepart' %}2{% elsif p.course %}2{% elsif p.collection == 'courses' %}8{% elsif p.collection == 'tags' %}5{% else %}1{% endif %},
        "authors": {% capture a %}{% case p.collection %}{% when "courses" %}{% include content_authors_string.html authors=p.lecturers %}{% when "content" %}{% include content_authors_string.html authors=p.authors %}{% else %}{{ p.author }}{% endcase %}{% endcapture %}"{{ a | strip | xml_escape }}",
        "content": {% assign cpieces = p.content | strip | markdownify | strip_newlines | replace: "</", ' </' | strip_html | replace: backtoback, "" | split: ocurly %}{% assign content = "" %}{% for p in cpieces %}{% assign s = p | split: ccurly | last %}{% assign content = content | append: s %}{% endfor %}{{ content | jsonify }},
        "url": "{{ p.url }}"
    }{% unless forloop.last %},{% endunless %}
  {% endfor %}
};

var idx = lunr(function () {
    this.ref('id'); this.field('title', { boost: 10 });
    this.field('authors', { boost: 2 }); this.field('content');
    this.field('tags', { boost: 3 }); this.field('description', { boost: 2 });
    this.field('category');
    this.metadataWhitelist = ['position']
    for (var key in store) {
        var v = store[key];
        this.add({
            'id': key, 'title': utils.unaccented(v.title),
            'authors': utils.unaccented(v.authors), 'content': utils.unaccented(v.content),
            'tags': v.tags, 'description': utils.unaccented(v.description),
            'category': v.category
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

function getBlurbForResult(result, item, positions) {
    var titleMatch = false;
    for (var searchTerm in result.matchData.metadata) {
        if (result.matchData.metadata[searchTerm]['title']) {
            titleMatch = true;
            break;
        }
    }
    if ((titleMatch || positions.length == 0) && item.description){
      if (item.description.length < BMAX) return item.description;
      return item.description.substring(0, BMAX) + "...";
    }
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
    i = m - (BMAX>>1);
    var pre = true;
    if (i <= 0){ i = 0; pre = false; }
    j = i + BMAX;
    if (j >= item.content.length) return (pre?'...':'') + item.content.substring(i, item.content.length-1);
    return (pre?'...':'') + item.content.substring(i,j) + "...";
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
    }
    var ret = '<li><a href="' + item.url + '"><h3>' + item.title + '</h3>';
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
    if (!results.length) results = idx.search(e.data.split(" ").join("~1 ") + "~1");
    self.postMessage(displaySearchResults(results));
}


