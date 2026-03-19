function unaccent(e) { return e.update(utils.unaccented); }
lunr.Pipeline.registerFunction(unaccent, 'unaccent');

// IMPORTANT! Keep this up-to-date with the version in /_tests/tags.md
const OBU_STEMMER = function (token, i, tokens) {
  // Don't stem tags
  if (UNSTEMMED_WORDS.has(token.toString().toLowerCase())) {
    return token;
  }
  return lunr.stemmer(token, i, tokens);
};

function buildSearchIndex(store) {
  return lunr(function () {
    this.ref('id'); this.field('title', { boost: 10 });
    this.field('author', { boost: 2 }); this.field('content');
    this.field('translator'); this.field('format');
    this.field('tag', { boost: 4 }); this.field('description', { boost: 2 });
    this.field('in', { boost: 4 }); this.field('type', { boost: 0.3 });
    this.field('is', { boost: 4 });
    this.metadataWhitelist = ['position']
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
}

function initSearchWorker(store) {
  var idx = buildSearchIndex(store);
  self.onmessage = function(e) {
    self.postMessage(handleSearchMessage(e.data, idx.search.bind(idx)));
  }
}
