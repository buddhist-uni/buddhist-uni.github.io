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
  // Don't stem tags, including hyphenated raw tags so they match exactly
  if (UNSTEMMED_WORDS.has(token.toString().toLowerCase()) || token.toString().includes('-')) {
    return token;
  }
  return lunr.stemmer(token, i, tokens);
};

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
        "tags": {% assign tags = p.tags | default: emptylist %}{% if p.course %}{% assign tags = tags | push: p.course %}{% endif %}{{ tags | jsonify }},
        "tagtitles": {% assign titles = emptylist %}{% for t in p.tags %}{% assign tag = site.tags | find: "slug", t %}{% unless tag %}{% assign tag = site.courses | find: "slug", t %}{% endunless %}{% assign title = tag.title | default: t %}{% assign titles = titles | push: title %}{% endfor %}{% if p.course %}{% assign course = site.courses | find: "slug", p.course %}{% unless course %}{% assign course = site.tags | find: "slug", p.course %}{% endunless %}{% assign title = course.title | default: p.course %}{% assign titles = titles | push: title %}{% endif %}{{ titles | jsonify }},
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
    this.field('tag', { boost: 4 }); this.field('rawtag', { boost: 4 });
    this.field('description', { boost: 2 });
    this.field('in', { boost: 4 }); this.field('type', { boost: 0.3 });
    this.field('is', { boost: 4 });
    this.metadataWhitelist = ['position']
    // Array fields hold [position in the tag titles, token] pairs
    this.tokenizer = function (obj, metadata) {
        if (!Array.isArray(obj)) return lunr.tokenizer(obj, metadata);
        return obj.map(function (p) { return new lunr.Token(p[1].toLowerCase(), { fields: metadata.fields, position: p[0] }); });
    };
    // this.pipeline.add(unaccent); // commented out as we're doing the unaccenting manually above
    this.pipeline.remove(lunr.stemmer);
    this.searchPipeline.remove(lunr.stemmer);
    this.pipeline.add(OBU_STEMMER);
    this.searchPipeline.add(OBU_STEMMER);
    var pipeline = this.pipeline;
    function terms(s) { return pipeline.run(lunr.tokenizer(s)).map(String); }
    // plain words, so "Buddha's" and "Thera/Therīgāthā" match "buddha" and "therigatha"
    function words(s) { return utils.unaccented(s).replace(/[^\p{L}\p{N}]/gu, ' '); }
    for (var key in store) {
        var v = store[key], at = 0, rawtag = [];
        // NFC keeps highlight offsets aligned
        v.tagtitles = v.tagtitles.map(function (t) { return t.normalize('NFC'); });
        var tag = lunr.tokenizer(words(v.tagtitles.join(' '))).map(function (t) { return [t.metadata.position, String(t)]; });
        // tag also gets the titles' hyphenated words and each raw tag's words that its title lacks
        v.tagtitles.forEach(function (title, i) {
            var whole = [at, title.length], raw = tidyHyphens(v.tags[i]), titleterms = terms(words(title));
            for (var m of utils.unaccented(title).matchAll(/[\p{L}\p{N}]+(-[\p{L}\p{N}]+)+/gu)) tag.push([[at + m.index, m[0].length], m[0]]);
            raw.split('-').forEach(function (w) { if (!titleterms.includes(terms(w)[0])) tag.push([whole, w]); });
            rawtag.push([whole, raw]);
            at += title.length + 1;
        });
        this.add({
            'id': key, 'title': utils.unaccented(v.title),
            'author': v.authors.map(utils.unaccented).join('  '), 'content': utils.unaccented(v.content),
            'translator': utils.unaccented(v.translator), 'format': v.formats.join('  '),
            'tag': tag, 'rawtag': rawtag,
            'description': utils.unaccented(v.description),
            'in': v.category, 'is': v.subcategory, 'type': v.type
      }, {boost: v.boost});
    }
});

joinedTitles = normalizeSuttaTitles(store);

self.onmessage = function(e) {
  self.postMessage(handleSearchMessage(e.data, searchIndex.bind(null, idx)));
}
