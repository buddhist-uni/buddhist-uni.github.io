---
layout: nil
---
importScripts("/assets/js/lunr.min.js");
importScripts("/assets/js/utils.js");
function unaccent(e) { return e.update(utils.unaccented); }
lunr.Pipeline.registerFunction(unaccent, 'unaccent');

// IMPORTANT! Keep this up-to-date with the version in /_tests/tags.md
const OBU_STEMMER = function (token, i, tokens) {
  // Don't stem tags
  if (UNSTEMMED_WORDS.has(token.toString().toLowerCase())) {
    return token;
  }
  return lunr.stemmer(token, i, tokens);
}

// Parameters
var BMAX = 250; // Max blurb size in characters
var RMAX = 100;

{%- assign ccurly = "}" -%}
{%- assign ocurly = "{" -%}
{%- assign backtoback = ccurly | append: ocurly -%}
{%- assign doubleo = ocurly | append: ocurly -%}
{%- assign doublec = ccurly | append: ccurly -%}
{%- assign pagesWithoutContent = 'Authors,Highlights,Search,All Content' | split: ',' -%}
{%- assign emptylist = '' | split: '' -%}
var store = { {% assign all = site.documents | concat: site.pages %}
  {% for p in all %}
    {% unless p.title %}{% continue %}{% endunless %}
    {% if p.url contains "/tests/" or pagesWithoutContent contains p.title %}{% continue %}{% endif %}
    "{{ p.url | slugify }}": {
        "type": "{{ p.collection | default: 'pages' }}",
        "title": {{ p.title | markdownify | strip_html | normalize_whitespace | jsonify }},
        "description": {{ p.description | markdownify | strip_html | normalize_whitespace | jsonify }},
        "tags": {% assign tags = emptylist %}{% for t in p.tags %}{% assign tag = site.tags | find: "slug", t %}{% unless tag %}{% assign tag = site.courses | find: "slug", t %}{% endunless %}{% if tag.title %}{% assign tags = tags | push: tag.title %}{% assign tt = tag.title | slugify %}{% else %}{% assign tt = "" %}{% endif %}{% unless tt contains t %}{% assign tags = tags | push: t %}{% endunless %}{% endfor %}{% if p.course %}{% assign course = site.courses | find: "slug", p.course %}{% unless course %}{% assign course = site.tags | find: "slug", p.course %}{% endunless %}{% if course.title %}{% assign tags = tags | push: course.title %}{% assign tt = course.title | slugify %}{% else %}{% assign tt = "" %}{% endif %}{% unless tt contains p.course %}{% assign tags = tags | push: p.course %}{% endunless %}{% endif %}{{ tags | jsonify }},
        "category": {{ p.category | jsonify }},
        "subcategory": {{ p.subcat | jsonify }},
        "formats": {% assign formats = '' | split: '' %}{% for f in p.drive_links %}{% assign formats = formats | push: p.formats[forloop.index0] %}{% endfor %}{{ formats | jsonify}},
        "boost": {% if p.status == 'featured' %}1.6{% elsif p.status == 'rejected' %}0.3{% elsif p.status == "unpublished" %}1.45{% elsif p.layout == 'imagerycoursepart' %}1.3{% elsif p.course %}1.2{% elsif p.collection == 'courses' %}2{% elsif p.collection == 'tags' %}2{% else %}1{% endif %},
        "authors": {% capture a %}{% case p.collection %}{% when "courses" %}{% include_cached content_authors_string.html authors=p.lecturers %}{% when "content" %}{% if p.authors %}{% include_cached content_authors_string.html authors=p.authors %}{% else %}{% assign conts = p.reader | default: p.editor | split: ' and ' %}{% include_cached content_authors_string.html authors=conts %}{% endif %}{% else %}{{ p.author }}{% endcase %}{% endcapture %}{% assign a = a | strip | strip_html | normalize_whitespace | split: " and " %}{% assign authors = a | last | split: "unfindabletoken" %}{% if a.size > 1 %}{% assign authors = a | first | split: ", " %}{% assign sla = authors | last | replace: ",", "" %}{% assign authors = authors | pop | push: sla | push: a[1] %}{% endif %}{{ authors | jsonify }},
        "translator": {% assign conts = p.translator | split: ' and ' %}{% capture s %}{% include_cached content_authors_string.html authors=conts %}{% endcapture %}{{ s | strip_newlines | jsonify }},
        "content": {% assign cpieces = p.content | strip | replace: doubleo, ocurly | replace: doublec, ccurly | replace: backtoback, "" | split: ocurly %}{% assign content = "" %}{% for p in cpieces %}{% assign s = p | split: ccurly | last %}{% assign content = content | append: s %}{% endfor %}{{ content | markdownify | normalize_whitespace | replace: "</p", ' </p' | replace: "</div", " </div" | replace: "</li", " </li" | strip_html | normalize_whitespace | jsonify }},
        "url": "{{ p.url }}"
    }{% unless forloop.last %},{% endunless %}
  {% endfor %}
};

var idx = lunr(function () {
    this.ref('id'); this.field('title', { boost: 10 });
    this.field('author', { boost: 2 }); this.field('content');
    this.field('translator'); this.field('format');
    this.field('tag', { boost: 4 }); this.field('description', { boost: 2 });
    this.field('in', { boost: 4 }); this.field('type', { boost: 0.3 });
    this.field('is', { boost: 4 });
    this.metadataWhitelist = ['position']
    // this.pipeline.add(unaccent); // commented out as we're doing the unaccenting manually above
    this.pipeline.remove(lunr.stemmer);
    this.searchPipeline.remove(lunr.stemmer);
    this.pipeline.add(OBU_STEMMER);
    this.searchPipeline.add(OBU_STEMMER);
    for (var key in store) {
        var v = store[key];
        this.add({
            'id': key, 'title': utils.unaccented(v.title),
            'author': v.authors.map(utils.unaccented).join('  '), 'content': utils.unaccented(v.content),
            'translator': utils.unaccented(v.translator), 'format': v.formats.join('  '),
            'tag': v.tags.join(' '), 'description': utils.unaccented(v.description),
            'in': v.category, 'is': v.subcategory, 'type': v.type
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

function resultMatched(result, fromfield) {
    let md = result.matchData.metadata;
    for (var st in md) {
        if (!md[st][fromfield]) continue;
        for (var mi in md[st][fromfield]['position']) return true;
    }
    return false;
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
        case 'av': return '<i class="fas fa-volume-up"></i> Recording';
        case 'articles': return '<i class="far fa-newspaper"></i> Article';
        case 'booklets': return '<i class="fas fa-book-open"></i> Book';
        case 'monographs': return '<i class="fas fa-book"></i> Book';
        case 'papers': return '<i class="far fa-file-powerpoint"></i> Paper';
        case 'essays': return '<i class="far fa-file-word"></i> Essay';
        case 'canon': return '<i class="fas fa-dharmachakra"></i> Canonical Work';
        case 'reference': return '<i class="fas fa-atlas"></i> Reference Work';
        case 'excerpts': return '<i class="fas fa-book-reader"></i> Excerpt';
    }
    return '<i class="far fa-file"></i> Library Item';
}

function displaySearchResult(result, item) {
    var positions = getPositions(result, 'content');
    var blurb = getBlurbForResult(result, item, positions);
    var type = null;
    switch (item.type) {
        case 'courses': type = '<i class="fas fa-chalkboard"></i> Course'; break;
        case 'content': type = categoryName(item.category); break;
        case 'posts': type = '<i class="fas fa-rss"></i> Blog Post'; break;
        case 'journals': type = '<i class="fas fa-newspaper"></i> Journal'; break;
        case 'authors': type = '<i class="far fa-address-book"></i> Author'; break; 
        case 'publishers': type = '<i class="far fa-building"></i> Publisher'; break;
        case 'tags': type = '<i class="fas fa-tag"></i> Bibliography'; break;
        case 'series': type = '<i class="fas fa-list-ol"></i> Series'; break;
    }
    var ret = '<li><h3><a href="' + item.url + '">' + addMatchHighlights(result, item.title, 'title') + '</a></h3>';
    if (type) ret += '<span class="Counter">' + type + '</span>';
    var lc = 0;
    for (var i in item.authors) {
        ret += '<span class="Label ml-1">' +
            addMatchHighlights(result, item.authors[i], 'author', lc, lc + item.authors[i].length) +
            '</span>';
        lc += 2 + item.authors[i].length;
    }
    if (resultMatched(result, 'translator')) ret += '<span class="Label ml-1">Translator: ' +
        addMatchHighlights(result, item.translator, 'translator') +
        '</span>';
    if (resultMatched(result, 'tag')) {
        lc = 0;
        for (var i in item.tags) {
            if (!item.tags[i]) continue;
            let t = '<span class="Label ml-1 text-capitalize"><i class="fas fa-tag"></i> ' +
                addMatchHighlights(result, item.tags[i].replace('-',' '), 'tag', lc, lc + item.tags[i].length) + '</span>';
            if (t.includes('<strong>')) ret += t;
            lc += 1 + item.tags[i].length;
        }
    }
    if (resultMatched(result, 'format')) {
        lc = 0;
        for (var i in item.formats) {
            if (!item.formats[i]) continue;
            let t = '<span class="Label ml-1"><i class="fas fa-file-arrow-down"></i> ' +
                addMatchHighlights(result, item.formats[i], 'format', lc, lc + item.formats[i].length) + '</span>';
            if (t.includes('<strong>')) ret += t;
            lc += 2 + item.formats[i].length;
        }
    }
    return ret + '<p>' + blurb + '</p></li>';
}

function displaySearchResults(results) {
    if (results.length) {
      var ret = '';
      for (var i in results) {
        if (i >= RMAX) break;
        ret += displaySearchResult(results[i], store[results[i].ref]);
      }
      return ret;
    } else {
      return '<li>No results found</li>';
    }
}

self.onmessage = function(e) {
  var results = [];
  var warning = "";
  var words = e.data.q.trim().split(" ");
  for (var i = 0; i < words.length; i++) {
    const s = words[i].trim();
    if (!s.startsWith("+") && !s.startsWith("-") && s.length > 1 && lunr.stopWordFilter(s)) {
      words[i] = "+" + s;
    } else {
      words[i] = s;
    }
  }
  var query = words.join(' ').trim();
  try {
    results = idx.search(query);
    if (!results.length){
      warning = "<li><strong>No results</strong> found matching all of your terms. Results found matching <em>any</em> term:</li>";
      results = idx.search(e.data.q.trim());
    }
  } catch (err) {
    if (err.message.indexOf("unrecognised field") >= 0 && query.indexOf(":") >= 0) {
      results = idx.search(e.data.q.replaceAll(":"," "));
    } else { throw err; }
  }
  if (!results.length){
    words = e.data.q.trim().split(" ");
    if (words.find(function(w){ return w.length <= 2; }) == undefined) {
      results = idx.search(words.join("~1 ") + "~1");
      if (results.length)
        warning = "<li><strong>No results</strong> found for your query. Perhaps you meant:</li>";
      else
        warning = "";
    } else {
      warning = "";
    }
  }
  if (e.data.filterquery && e.data.filterquery !== "") {
    var filteredResults = idx.search(e.data.filterquery);
    results = results.filter(function(result) {
      return filteredResults.some(function(filteredResult) {
        return filteredResult.ref === result.ref;
      });
    });
  }
  self.postMessage({
    "warninghtml": warning,
    "html": displaySearchResults(results),
    "count": results ? results.length : 0,
    "q": e.data.q,
    "filterquery": e.data.filterquery,
    "qt": e.data.qt
  });
}


