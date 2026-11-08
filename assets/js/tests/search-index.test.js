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
    console: Object.assign({}, console, {
      warn: function (msg) { if (!/not registered with pipeline/.test(msg)) console.warn(msg); }
    }),
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

  // q as search.js sends it, i.e. unaccented. Returns the warning and each result's tag labels.
  return function search(q) {
    let reply = null;
    sandbox.self.postMessage = function (m) { reply = m; };
    sandbox.self.onmessage({ data: { q: q, filterquery: '', qt: 0 } });
    assert.ok(reply, 'the worker did not reply');
    const labels = {};
    for (const li of reply.html.split('<li><h3>').slice(1)) {
      labels[/href="([^"]+)"/.exec(li)[1]] = Array.from(li.matchAll(/Label[^"]*"><i class="fas fa-tag"><\/i> (.*?)<\/span>/g), m => m[1]);
    }
    return { warning: reply.warninghtml, labels: labels };
  };
}

function doc(fields) {
  return Object.assign({ type: 'content', title: '', tags: [], authors: [], formats: [], content: '', boost: 1 }, fields);
}

// From the built store: tags hold the documents' tag and course titles
const search = loadSearchWorker({
  'tags-an': doc({ type: 'tags', url: '/tags/an', title: 'Aṅguttara Nikāya' }),
  'content-canon-an1-11-20': doc({
    url: '/content/canon/an1.11-20',
    title: 'AN 1.11–20 Nīvaraṇappahāna Vagga: The Chapter on Giving Up the Hindrances',
    tags: ['Aṅguttara Nikāya', 'an', 'The Hindrances']
  }),
  'content-canon-ud1-3': doc({
    url: '/content/canon/ud1.3',
    title: 'Ud 1.3 Tatiya Bodhi Sutta: The Third Utterance Upon Awakening',
    tags: ['Nibbāna', 'Udāna', 'Dependent Origination']
  }),
  'content-av-after-nibbana-yuttadhammo': doc({
    url: '/content/av/after-nibbana_yuttadhammo',
    title: 'After Nibbana',
    tags: ['Arahants', 'Vipassanā', 'Nibbāna: The Goal of Buddhist Practice']
  }),
});

describe('search_index.js accented tags', () => {
  it('"anguttara" finds documents tagged "Aṅguttara Nikāya"', () => {
    const r = search('anguttara');
    assert.equal(r.warning, '');
    assert.deepEqual(r.labels['/content/canon/an1.11-20'], ['<strong>Aṅguttara</strong> Nikāya']);
  });

  it('"tag:anguttara" matches "Aṅguttara Nikāya" without the fuzzy fallback', () => {
    const r = search('tag:anguttara');
    assert.equal(r.warning, '');
    assert.deepEqual(r.labels, { '/content/canon/an1.11-20': ['<strong>Aṅguttara</strong> Nikāya'] });
  });

  it('"tag:nibbana" matches "Nibbāna" without the fuzzy fallback', () => {
    const r = search('tag:nibbana');
    assert.equal(r.warning, '');
    assert.deepEqual(r.labels, {
      '/content/canon/ud1.3': ['<strong>Nibbāna</strong>'],
      '/content/av/after-nibbana_yuttadhammo': ['<strong>Nibbāna:</strong> The Goal of Buddhist Practice'],
    });
  });

  it('copes with decomposed and non-string tags', () => {
    const r = loadSearchWorker({ d: doc({ url: '/d', tags: [1, 'Vipassana\u0304', 'Nibbāna'] }) })('tag:nibbana');
    assert.deepEqual(r.labels, { '/d': ['<strong>Nibbāna</strong>'] });
  });
});
