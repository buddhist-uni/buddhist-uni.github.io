---
layout: nil
---
importScripts("/assets/js/lunr.min.js");
importScripts("/assets/js/utils.js");
importScripts("/assets/js/search_functions.js");
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


