---
title: "Tag Tests"
---

A series of tests to check the integrity of the tag configuration.

| Test Name | Status | Notes |
|-----------|--------|-------|
| All tags in _config.yml order | {% assign pivottags = site.tags | map: "name" | join: " " | split: " architecture.md " %}{% if pivottags.size == 1 %}Pass ✅{% else %}FAIL ❌{% endif %}  |  {% if pivottags.size > 1 %}These tags need to be added: `{{ pivottags | last }}`{% else %}All in!{% endif %} |
| If published, parent is | {% assign failures = "" | split: "" %}{% for tag in site.tags %}{% assign parent = site.tags | find: "slug", tag.parents[0] %}{% unless parent and tag.status == "published" %}{% continue %}{% endunless %}{% unless parent.status == "published" or tag.level == 1 %}{% assign failures = failures | push: tag.name %}{% endunless %}{% endfor %}{% if failures.size == 0 %}Pass ✅{% else %}FAIL ❌{% endif %}  |  {% if failures.size > 0 %}These tags have unpublished parents: `{{ failures | join: " " }}`{% else %}None dangling!{% endif %} |
| Parents appear before children in tag order (except for "-religion" tags, pairs across the Buddhism/secular divide and "modern") | {% assign pivottags = site.tags | map: "name" | join: " " | split: " world.md " %}{% assign buddhismtags = pivottags | first %}{% assign seculartags = pivottags | last %}{% assign failures = "" | split: "" %}{% assign seen = "modern" | split: "," %}{% for tag in site.tags %}{% if tag.slug contains "religion" %}{% continue %}{% endif %}{% for pslug in tag.parents %}{% assign parent = site.tags | find: "slug", pslug %}{% unless parent %}{% continue %}{% endunless %}{% if buddhismtags contains tag.name and seculartags contains parent.name %}{% continue %}{% endif %}{% unless seen contains pslug %}{% capture pair %}({{tag.slug}}, {{pslug}}){% endcapture %}{% assign failures = failures | push: pair %}{% endunless %}{% endfor %}{% assign seen = seen | push: tag.slug %}{% endfor %}{% if failures.size == 0 %}Pass ✅{% else %}FAIL ❌{% endif %}  |  {% if failures.size > 0 %}(child, parent) pairs that are out of order: `{{ failures | join: " " }}`{% else %}All partial orderings are respected.{% endif %} |

## JS Tests

The `_tags` folder contains <strong id="knowncount"></strong> tags and
there are <strong id="shadowcount"></strong> untracked, "shadow" tags.

Stemming means to reduce a word to its root form.  For example, "animals" stems to "<strong id="stemtest"></strong>".

### Stem Collisions

Stem collisions occur when two (unhyphenated) tags have the same stem according
to the `OBU_STEMMER`.
This can happen for two reasons:
 1. One of the two tags is in the incorrect form (e.g. "disaster" instead of "disasters").
 2. `utils.js` hasn't been told to avoid stemming the tag (e.g. "animism" being erroneously reduced to "anim").

To fix, either rename one of the colliding tags or tell `utils.js` to blacklist the term from stemming.

#### Collisions Found:

<ul id="collisions">
<li id="nocollisions">No collisions detected!</li>
</ul>

{% assign knownslugs = '' | split: '' %}
{% for tag in site.tags %}{% assign knownslugs = knownslugs | push: tag.slug %}{% endfor %}
<script src="/assets/js/utils.js"></script>
<script src="/assets/js/lunr.min.js"></script>
<script>
  // IMPORTANT!  Keep this up-to-date with the stemmer in search_index.js!
  const OBU_STEMMER = function (token, i, tokens) {
    // Don't stem tags
    if (UNSTEMMED_WORDS.has(token.toString().toLowerCase())) {
      return token;
    }
    return lunr.stemmer(token, i, tokens);
  };
  const KNOWN_TAGS = new Set([{% for tag in site.tags%}"{{ tag.slug }}", {% endfor %}]);
  const SHADOW_TAGS = new Set([{% for c in site.content %}{% if c.course %}{% unless knownslugs contains c.course %}"{{ c.course }}", {% endunless %}{% endif %}{% for tag in c.tags %}{% unless knownslugs contains tag %}"{{ tag }}", {% endunless %}{% endfor %}{% endfor %}]);
  var shadow_list = document.getElementById("shadows");
  document.getElementById("knowncount").textContent = KNOWN_TAGS.size;
  document.getElementById("shadowcount").textContent = SHADOW_TAGS.size;
  document.getElementById("stemtest").textContent = lunr.stemmer(new lunr.Token("animals"));
  var stemmed_slugs = new Map();
  var all_unhyphenated_tags = new Set();
  for (const tag of KNOWN_TAGS) {
    if (!tag.includes("-")) {
      all_unhyphenated_tags.add(tag);
    }
  }
  for (const tag of SHADOW_TAGS) {
    if (!tag.includes("-")) {
      all_unhyphenated_tags.add(tag);
    }
  }
  const collisions_list = document.getElementById("collisions");
  for (const tag of all_unhyphenated_tags) {
    const stemmed_tag = OBU_STEMMER(new lunr.Token(tag)).toString();
    if (stemmed_slugs.has(stemmed_tag)) {
      const existing_tag = stemmed_slugs.get(stemmed_tag);
      const li = document.createElement("li");
      li.textContent = `${tag} collides with ${existing_tag}`;
      collisions_list.appendChild(li);
      document.getElementById("nocollisions").style.display = 'none';
    } else {
      stemmed_slugs.set(stemmed_tag, tag);
    }
  }
</script>
