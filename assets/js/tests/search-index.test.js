const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const jsDir = path.join(__dirname, '..');

// Runs search_index.js with `store` in place of the store Liquid renders
function loadSearchWorker(store) {
  const template = fs.readFileSync(path.join(jsDir, 'search_index.js'), 'utf-8');
  const liquidStore = /var store = \{[\s\S]*?\n\};/.exec(template);
  assert.ok(liquidStore, 'store not found in search_index.js');
  const sandbox = {
    self: {},
    console: { warn() {} },
    importScripts: function (src) {
      vm.runInContext(fs.readFileSync(path.join(jsDir, path.basename(src)), 'utf-8'), sandbox);
    }
  };
  vm.createContext(sandbox);
  vm.runInContext(
    template.slice(0, liquidStore.index).replace(/^---[\s\S]*?---/, '').replace(/\{%[\s\S]*?%\}/g, '') +
    'var store = ' + JSON.stringify(store) + ';' +
    template.slice(liquidStore.index + liquidStore[0].length),
    sandbox
  );
  const searchJs = fs.readFileSync(path.join(jsDir, 'search.js'), 'utf-8');
  const sanitizeQuery = vm.runInContext(
    /const QMIN = .*/.exec(searchJs)[0] + /function sanitizeQuery[\s\S]*?\n  \}/.exec(searchJs)[0] + 'sanitizeQuery',
    sandbox
  );

  // Sends q as search.js does. Returns the warning and each result's tag labels, in result order.
  return function search(q) {
    let reply = null;
    sandbox.self.postMessage = function (m) { reply = m; };
    sandbox.self.onmessage({ data: { q: sanitizeQuery(q), filterquery: '', qt: 0 } });
    assert.ok(reply, 'the worker did not reply');
    const labels = {};
    for (const li of reply.html.split('<li><h3>').slice(1)) {
      labels[/href="([^"]+)"/.exec(li)[1]] = Array.from(li.matchAll(/Label[^"]*"><i class="fas fa-tag"><\/i> (.*?)<\/span>/g), m => m[1]);
    }
    return { warning: reply.warninghtml.replace(/<[^>]+>/g, ''), labels: labels };
  };
}

// A store entry with its [raw tag, title] pairs
function doc(url, tags, fields) {
  return [url, Object.assign({
    type: 'content', url: url, title: '', tags: tags.map(t => t[0]), tagtitles: tags.map(t => t[1]),
    authors: [], formats: [], content: '', boost: 1
  }, fields)];
}

const docs = [
  // tags and titles from the built store
  doc('/tags/an', [], { type: 'tags', title: 'Aṅguttara Nikāya' }),
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
  doc('/anicca', [['philosophy', 'An Introduction to Buddhist Philosophy']]),
  // made up, for hyphens the real tags don't have
  doc('/self-view', [['sakkaya-ditthi', 'Sakkāyadiṭṭhi - Self-View']]),
];
const search = loadSearchWorker(Object.fromEntries(docs));

describe('search_index.js tags', () => {
  const nibbana = {
    '/ud1.3': ['<strong>Nibbāna</strong>'],
    '/after-nibbana': ['<strong>Nibbāna</strong>: The Goal of Buddhist Practice'],
    '/mind-stilled': ['<strong>Nibbāna</strong>: The Mind Stilled'],
  };
  const paliCanon = { '/canon-studies': ['<strong>The Pāli Canon</strong>'] };
  for (const [name, q, labels] of [
    ['plain word of an accented title', 'anguttara', { '/tags/an': [], '/an1.11-20': ['<strong>Aṅguttara</strong> Nikāya'] }],
    ['plain words of a title', 'pali canon', {
      '/canon-studies': ['The <strong>Pāli Canon</strong>'],
      '/poems': ['Poetry of the <strong>Pāḷi Canon</strong>'],
    }],
    ['plain raw tag its title lacks', 'emptiness', { '/poems': ['<strong>Śūnyatā</strong>'] }],
    ['plain word, not whole raw tags', 'nibbana', nibbana],
    ['tag', 'tag:nibbana', nibbana],
    ['accented tag', 'tag:nibbāna', nibbana],
    ['capitalised tag', 'tag:Pali-Canon', paliCanon],
    ['tag missing from its title', 'tag:ma', { '/brahmas-invitation': ['<strong>Madhyama Āgama</strong>'] }],
    ['title word or raw tag', 'tag:an', {
      '/an1.11-20': ['<strong>Aṅguttara Nikāya</strong>'],
      '/anicca': ['<strong>An</strong> Introduction to Buddhist Philosophy'],
    }],
    ['word of a hyphenated tag', 'tag:pitaka', { '/vinaya': ['<strong>The Vinaya</strong>'] }],
    ['hyphenated tag', 'tag:pali-canon', paliCanon],
    ['raw tag', 'rawtag:pali-canon', paliCanon],
    ['raw tag, not title words', 'rawtag:an', { '/an1.11-20': ['<strong>Aṅguttara Nikāya</strong>'] }],
    ['tag with 2 hyphens', 'tag:nibbana-mind-stilled', { '/mind-stilled': ['<strong>Nibbāna: The Mind Stilled</strong>'] }],
    ['tag without a page', 'tag:higher-ed', { '/spindle-whorls': ['<strong>higher ed</strong>'] }],
    ['title word after punctuation', 'tag:therigatha', { '/gotamis-poem': ['Thera/<strong>Therīgāthā</strong>'] }],
    ['title word before punctuation', 'tag:buddha', { '/gotamis-poem': ["<strong>Buddha</strong>'s India"] }],
    ['typed apostrophe', "tag:buddha's", { '/gotamis-poem': ["<strong>Buddha</strong>'s India"] }],
    ['without a tag', 'tag:pali -tag:pali-canon', {
      '/pali-grammar': ['<strong>Pāli</strong> Grammar'],
      '/poems': ['Poetry of the <strong>Pāḷi</strong> Canon'],
    }],
    ['without a 2-hyphen tag', 'tag:religion -tag:east-asian-religion', { '/confucianism': ['chinese <strong>religions</strong>'] }],
    ['unstemmed hyphenated tag', 'rawtag:chinese-religion', { '/daoism': ['<strong>Sinitic Religion</strong>'] }],
    ['no such tag', 'tag:pali-sutra', {}],
  ]) {
    it(`${name}: ${q}`, () => {
      const r = search(q);
      assert.equal(r.warning, '');
      assert.deepEqual(r.labels, labels);
    });
  }

  it('misspelt tag: falls back to fuzzy matches', () => {
    const r = search('tag:nibbna');
    assert.match(r.warning, /Perhaps you meant/);
    assert.deepEqual(r.labels, nibbana);
  });

  for (const [name, q, labels] of [
    ['word around title hyphens', 'tag:self', { '/self-view': ['Sakkāyadiṭṭhi - <strong>Self</strong>-View'] }],
    ['hyphenated title word', 'tag:self-view', { '/self-view': ['Sakkāyadiṭṭhi - <strong>Self-View</strong>'] }],
    ['word of a raw tag', 'tag:ditthi', { '/self-view': ['<strong>Sakkāyadiṭṭhi - Self-View</strong>'] }],
  ]) {
    it(`hyphens, ${name}: ${q}`, () => assert.deepEqual(search(q), { warning: '', labels: labels }));
  }

  it('labels every tag: result', () => {
    for (const w of new Set(docs.flatMap(d => d[1].tags.flatMap(t => t.split('-'))).filter(w => w.length > 2))) {
      for (const [url, labels] of Object.entries(search('tag:' + w).labels)) assert.ok(labels.length, `tag:${w} ${url}`);
    }
  });

  it('keeps highlights on decomposed titles', () => {
    const r = loadSearchWorker(Object.fromEntries([
      doc('/d', [['vipassana', 'Vipassana\u0304'], ['nibbana', 'Nibbāna: The Goal']]),
    ]))('tag:goal');
    assert.deepEqual(r.labels, { '/d': ['Nibbāna: The <strong>Goal</strong>'] });
  });
});
