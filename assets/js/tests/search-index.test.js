const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const jsDir = path.join(__dirname, '..');

// Runs search_index.js with `store` in place of the store Liquid renders
function loadSearchWorker(store) {
  const template = fs.readFileSync(path.join(jsDir, 'search_index.js'), 'utf-8');
  // Just locating the line where the store is defined
  const liquidStore = /var store = \{[\s\S]*?\n\};/.exec(template);
  assert.ok(liquidStore, 'store not found in search_index.js');
  const sandbox = {
    self: {},
    console: { warn() { } },
    importScripts: function (src) {
      vm.runInContext(fs.readFileSync(path.join(jsDir, path.basename(src)), 'utf-8'), sandbox);
    }
  };
  vm.createContext(sandbox);
  vm.runInContext(
    // now we strip out all the liquid templating business
    template.slice(0, liquidStore.index).replace(/^---[\s\S]*?---/, '').replace(/\{%[\s\S]*?%\}/g, '') +
    // and replace the previously-found store line with our mock store
    'var store = ' + JSON.stringify(store) + ';' +
    template.slice(liquidStore.index + liquidStore[0].length).replace(/\{%[\s\S]*?%\}/g, ''),
    sandbox
  );

  // Sends q as search.js does. Returns the warning and each result's topic labels, in result order.
  return function search(q) {
    let reply = null;
    sandbox.self.postMessage = function (m) { reply = m; };
    sandbox.self.onmessage({ data: { q: sandbox.sanitizeQuery(q), filterquery: '', qt: 0 } });
    assert.ok(reply, 'the worker did not reply');
    const topic_labels = {};
    for (const li of reply.html.split('<li><h3>').slice(1)) {
      topic_labels[/href="([^"]+)"/.exec(li)[1]] = Array.from(li.matchAll(/Label[^"]*"><i class="fas fa-tag"><\/i> (.*?)<\/span>/g), m => m[1]);
    }
    return { warning: reply.warninghtml.replace(/<[^>]+>/g, ''), topic_labels: topic_labels };
  };
}

// A store entry with its [slug, title] pairs
function doc(url, tags, fields) {
  return [url, Object.assign({
    type: 'content', url: url, title: '', tags: tags.map(t => t[0]), tagtitles: tags.map(t => t[1]),
    authors: [], formats: [], content: '', boost: 1
  }, fields)];
}

const docs = [
  // tags and titles from the built store
  doc('/topics/an', [], { type: 'tags', title: 'Aṅguttara Nikāya' }),
  doc('/an1.11-20', [['an', 'Aṅguttara Nikāya'], ['hindrances', 'The Hindrances']], { title: 'AN 1.11–20 Nīvaraṇappahāna Vagga' }),
  doc('/ud1.3', [['nibbana', 'Nibbāna'], ['ud', 'Udāna']]),
  doc('/after-nibbana', [['arahant', 'Arahants'], ['nibbana', 'Nibbāna: The Goal of Buddhist Practice']]),
  doc('/mind-stilled', [['nibbana-mind-stilled', 'Nibbāna: The Mind Stilled']]),
  doc('/brahmas-invitation', [['ma', 'Madhyama Āgama'], ['sa', 'Saṃyukta Āgama']]),
  doc('/canon-studies', [['pali-canon', 'The Pāli Canon'], ['academic', 'Buddhism in Academia']]),
  doc('/pali-grammar', [['pali-grammar', 'Pāli Grammar']]),
  doc('/poems', [['canonical-poetry', 'Poetry of the Pāḷi Canon'], ['emptiness', 'Śūnyatā'], ['chan-lit', 'Chán Literature']]),
  doc('/gotamis-poem', [['tg', 'Thera/Therīgāthā'], ['setting', "Buddha's India"]]),
  doc('/vinaya', [['vinaya-pitaka', 'The Vinaya']]),
  doc('/daoism', [['chinese-religion', 'Sinitic Religion'], ['east-asian-religion', 'East Asian Religions']]),
  doc('/confucianism', [['chinese-religions', 'chinese-religions']]),
  doc('/spindle-whorls', [['prehistory', 'prehistory'], ['higher-ed', 'higher-ed']]),
  doc('/feelings', [['emotion', 'Emotions']]),
  doc('/moods', [['emotions', 'emotions']]),
  doc('/discourses', [['suttas', 'suttas']]),
  doc('/breath', [['breath_geoff', 'Breath Meditation']]),
  doc('/anicca', [['philosophy', 'An Introduction to Buddhist Philosophy']]),
  // made up, for hyphens the real tags don't have
  doc('/self-view', [['sakkaya-ditthi', 'Sakkāyadiṭṭhi - Self-View']]),
  doc('/zen', [['zen', 'Mind-to-Mind Transmission']]),
  doc('/hello-world', [['hello--world', 'hello--world']]),
  doc('/hello-good-world', [['hello-good-world', 'hello-good-world']]),
  doc('/edges', [['-left', '-left'], ['right--', 'right--']]),
];
const search = loadSearchWorker(Object.fromEntries(docs));

describe('search_index.js tags', () => {
  const nibbana_results = {
    '/ud1.3': ['<strong>Nibbāna</strong>'],
    '/after-nibbana': ['<strong>Nibbāna: The Goal of Buddhist Practice</strong>'],
  };
  const topic_nibbana_results = {
    '/ud1.3': ['<strong>Nibbāna</strong>'],
    '/after-nibbana': ['<strong>Nibbāna</strong>: The Goal of Buddhist Practice'],
    '/mind-stilled': ['<strong>Nibbāna</strong>: The Mind Stilled'],
  };
  const pali_canon_results = { '/canon-studies': ['<strong>The Pāli Canon</strong>'] };
  for (const [name, q, topic_labels] of [
    ['plain word of an accented title', 'anguttara', { '/topics/an': [], '/an1.11-20': ['<strong>Aṅguttara</strong> Nikāya'] }],
    ['plain words of a title', 'pali canon', {
      '/canon-studies': ['The <strong>Pāli Canon</strong>'],
      '/poems': ['Poetry of the <strong>Pāḷi Canon</strong>'],
    }],
    ['plain slug its title lacks', 'emptiness', { '/poems': ['<strong>Śūnyatā</strong>'] }],
    ['plain word, not whole slugs', 'nibbana', topic_nibbana_results],
    ['tag', 'tag:nibbana', nibbana_results],
    ['accented tag', 'tag:nibbāna', nibbana_results],
    ['capitalised tag', 'tag:Pali-Canon', pali_canon_results],
    ['tag missing from its title', 'tag:ma', { '/brahmas-invitation': ['<strong>Madhyama Āgama</strong>'] }],
    ['tag, not title words', 'tag:an', { '/an1.11-20': ['<strong>Aṅguttara Nikāya</strong>'] }],
    ['tag, not its words', 'tag:pitaka', {}],
    ['tag, not its stem', 'tag:emotions', { '/moods': ['<strong>emotions</strong>'] }],
    ['tag, not its plural', 'tag:sutta', {}],
    ['tag with an underscore', 'tag:breath_geoff', { '/breath': ['<strong>Breath Meditation</strong>'] }],
    ['misspelt tag, without fuzzy matches', 'tag:nibbna', {}],
    ['tag, not a title word', 'tag:anguttara', {}],
    ['hyphenated tag', 'tag:pali-canon', pali_canon_results],
    ['tag with 2 hyphens', 'tag:nibbana-mind-stilled', { '/mind-stilled': ['<strong>Nibbāna: The Mind Stilled</strong>'] }],
    ['tag without a page', 'tag:higher-ed', { '/spindle-whorls': ['<strong>higher ed</strong>'] }],
    ['unstemmed hyphenated tag', 'tag:chinese-religion', { '/daoism': ['<strong>Sinitic Religion</strong>'] }],
    ['no such tag', 'tag:pali-sutra', {}],
    ['tag still being typed', 'tag:-', {}],
    ['title word', 'topic:nibbana', topic_nibbana_results],
    ['accented title word', 'topic:aṅguttara', { '/an1.11-20': ['<strong>Aṅguttara</strong> Nikāya'] }],
    ['title word or slug', 'topic:an', {
      '/an1.11-20': ['<strong>Aṅguttara Nikāya</strong>'],
      '/anicca': ['<strong>An</strong> Introduction to Buddhist Philosophy'],
    }],
    ['word of a hyphenated tag', 'topic:pitaka', { '/vinaya': ['<strong>The Vinaya</strong>'] }],
    ['title word after punctuation', 'topic:therigatha', { '/gotamis-poem': ['Thera/<strong>Therīgāthā</strong>'] }],
    ['title word before punctuation', 'topic:buddha', { '/gotamis-poem': ["<strong>Buddha</strong>'s India"] }],
    ['typed apostrophe', "topic:buddha's", { '/gotamis-poem': ["<strong>Buddha</strong>'s India"] }],
    ['without a tag', 'topic:pali -tag:pali-canon', {
      '/pali-grammar': ['<strong>Pāli</strong> Grammar'],
      '/poems': ['Poetry of the <strong>Pāḷi</strong> Canon'],
    }],
    ['without a 2-hyphen tag', 'topic:religion -tag:east-asian-religion', { '/confucianism': ['chinese <strong>religions</strong>'] }],
  ]) {
    it(`${name}: ${q}`, () => {
      const r = search(q);
      assert.equal(r.warning, '');
      assert.deepEqual(r.topic_labels, topic_labels);
    });
  }

  for (const [name, q, topic_labels] of [
    ['hyphen runs in a tag', 'tag:hello--world', { '/hello-world': ['<strong>hello  world</strong>'] }],
    ['tag, not a tidied one', 'tag:hello-world', {}],
    ['a middle word', 'topic:good', { '/hello-good-world': ['hello <strong>good</strong> world'] }],
    ['tag edge hyphens', 'tag:-left topic:right', { '/edges': ['<strong> left</strong>', '<strong>right</strong>  '] }],
    ['word around title hyphens', 'topic:self', { '/self-view': ['Sakkāyadiṭṭhi - <strong>Self</strong>-View'] }],
    ['hyphenated title word', 'topic:self-view', { '/self-view': ['Sakkāyadiṭṭhi - <strong>Self-View</strong>'] }],
    ['2-hyphen title word', 'topic:mind-to-mind', {
      '/zen': ['<strong>Mind</strong>-to-<strong>Mind</strong> Transmission'],
      '/mind-stilled': ['Nibbāna: The <strong>Mind</strong> Stilled'],
    }],
    ['first word, then any', 'topic:pali-canon', {
      '/canon-studies': ['The <strong>Pāli Canon</strong>'],
      '/poems': ['Poetry of the <strong>Pāḷi Canon</strong>'],
      '/pali-grammar': ['<strong>Pāli</strong> Grammar'],
    }],
    ['hyphenated title word is no tag', 'tag:self-view', {}],
    ['word of a slug', 'topic:ditthi', { '/self-view': ['<strong>Sakkāyadiṭṭhi - Self-View</strong>'] }],
  ]) {
    it(`hyphens, ${name}: ${q}`, () => assert.deepEqual(search(q), { warning: '', topic_labels: topic_labels }));
  }

  it('labels every tag: and topic: result', () => {
    const tags = docs.flatMap(d => d[1].tags);
    const qs = tags.map(t => 'tag:' + t).concat(tags.flatMap(t => t.split('-')).map(w => 'topic:' + w));
    for (const q of new Set(qs)) {
      for (const [url, topic_labels] of Object.entries(search(q).topic_labels)) assert.ok(topic_labels.length, `${q} ${url}`);
    }
  });

  it('keeps highlights on decomposed titles', () => {
    const r = loadSearchWorker(Object.fromEntries([
      doc('/d', [['vipassana', 'Vipassana\u0304'], ['nibbana', 'Nibbāna: The Goal']]),
    ]))('topic:goal');
    assert.deepEqual(r.topic_labels, { '/d': ['Nibbāna: The <strong>Goal</strong>'] });
  });
});
