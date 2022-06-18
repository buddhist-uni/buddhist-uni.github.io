---
layout: nil
---
if("function" === typeof importScripts){
    importScripts('lunr.min.js', 'utils.js');
}else{
    // node.js
    fs=require('fs');
    vm=require('vm');
    vm.runInThisContext(fs.readFileSync("./lunr.min.js", 'utf-8'), "./lunr.min.js");
    vm.runInThisContext(fs.readFileSync("./utils.js", 'utf-8'), "./utils.js");
}

{%- assign ccurly = "}" -%}
{%- assign ocurly = "{" -%}
{%- assign backtoback = ccurly | append: ocurly -%}
{%- assign doubleo = ocurly | append: ocurly -%}
{%- assign doublec = ccurly | append: ccurly -%}
{%- assign pagesWithoutContent = 'Authors,Highlights,Search' | split: ',' -%}
const store = { {% assign all = site.documents | concat: site.pages %}
  {% for p in all %}
    {% unless p.title %}{% continue %}{% endunless %}
    {% if p.url contains "/tests/" or pagesWithoutContent contains p.title %}{% continue %}{% endif %}
    "{{ p.url | slugify }}": {
        "type": "{{ p.collection | default: 'pages' }}",
        "title": {{ p.title | markdownify | strip_html | normalize_whitespace | jsonify }},
        "description": {{ p.description | markdownify | strip_html | normalize_whitespace | jsonify }},
        "tags": {{ p.tags | unshift: p.course | join: ' ' | jsonify }},
        "category": {{ p.category | jsonify }},
        "subcategory": {{ p.subcat | jsonify }},
        "boost": {% if p.status == 'featured' %}1.6{% elsif p.status == 'rejected' %}0.3{% elsif p.layout == 'imagerycoursepart' %}1.5{% elsif p.course %}1.2{% elsif p.collection == 'courses' %}2{% elsif p.collection == 'tags' %}2{% else %}1{% endif %},
        "authors": {% capture a %}{% case p.collection %}{% when "courses" %}{% include_cached content_authors_string.html authors=p.lecturers %}{% when "content" %}{% if p.authors %}{% include_cached content_authors_string.html authors=p.authors %}{% else %}{% assign conts = p.reader | default: p.editor | split: ' and ' %}{% include_cached content_authors_string.html authors=conts %}{% endif %}{% else %}{{ p.author }}{% endcase %}{% endcapture %}{% assign a = a | strip | strip_html | normalize_whitespace | split: " and " %}{% assign authors = a | last | split: "unfindabletoken" %}{% if a.size > 1 %}{% assign authors = a | first | split: ", " %}{% assign sla = authors | last | replace: ",", "" %}{% assign authors = authors | pop | push: sla | push: a[1] %}{% endif %}{{ authors | jsonify }},
        "translator": {% assign conts = p.translator | split: ' and ' %}{% capture s %}{% include_cached content_authors_string.html authors=conts %}{% endcapture %}{{ s | strip_newlines | jsonify }},
        "content": {% assign cpieces = p.content | strip | replace: doubleo, ocurly | replace: doublec, ccurly | replace: backtoback, "" | split: ocurly %}{% assign content = "" %}{% for p in cpieces %}{% assign s = p | split: ccurly | last %}{% assign content = content | append: s %}{% endfor %}{{ content | markdownify | normalize_whitespace | replace: "</p", ' </p' | replace: "</div", " </div" | replace: "</li", " </li" | strip_html | normalize_whitespace | jsonify }},
        "url": "{{ p.url }}"
    }{% unless forloop.last %},{% endunless %}
  {% endfor %}
};

const idx = lunr(function () {
    this.ref('id'); this.field('title', { boost: 10 });
    this.field('author', { boost: 2 }); this.field('content');
    this.field('translator');
    this.field('tag', { boost: 4 }); this.field('description', { boost: 2 });
    this.field('in', { boost: 4 }); this.field('type', { boost: 0.3 });
    this.field('is', { boost: 4 });
    this.metadataWhitelist = ['position']
    for (var key in store) {
        var v = store[key];
        this.add({
            'id': key, 'title': utils.unaccented(v.title),
            'author': v.authors.map(utils.unaccented).join('  '), 'content': utils.unaccented(v.content),
            'translator': utils.unaccented(v.translator),
            'tag': v.tags, 'description': utils.unaccented(v.description),
            'in': v.category, 'is': v.subcategory, 'type': v.type
      }, {boost: v.boost});
    }
});

if("undefined" === typeof importScripts){
   module.exports = {idx: idx, store: store};
}
