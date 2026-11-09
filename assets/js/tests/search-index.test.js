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
  const searchJs = fs.readFileSync(path.join(jsDir, 'search.js'), 'utf-8');
  const sanitizeQuery = vm.runInContext(
    /const QMIN = .*/.exec(searchJs)[0] + /function sanitizeQuery[\s\S]*?\n  \}/.exec(searchJs)[0] + 'sanitizeQuery',
    sandbox
  );

  // Sends q as search.js does. Returns the warning and each result's tag labels.
  return function search(q) {
    let reply = null;
    sandbox.self.postMessage = function (m) { reply = m; };
    sandbox.self.onmessage({ data: { q: sanitizeQuery(q), filterquery: '', qt: 0 } });
    assert.ok(reply, 'the worker did not reply');
    const labels = {};
    for (const li of reply.html.split('<li><h3>').slice(1)) {
      labels[/href="([^"]+)"/.exec(li)[1]] = Array.from(li.matchAll(/Label[^"]*"><i class="fas fa-tag"><\/i> (.*?)<\/span>/g), m => m[1]);
    }
    return { warning: reply.warninghtml, labels: labels };
  };
}

function doc(fields) {
  return Object.assign({ type: 'content', title: '', tags: [], tagtitles: [], authors: [], formats: [], content: '', boost: 1 }, fields);
}

// From the built store: tags are the raw tags then the course, tagtitles their titles
const search = loadSearchWorker({
  'tags-an': doc({ type: 'tags', url: '/tags/an', title: 'Aṅguttara Nikāya' }),
  'content-canon-an1-11-20': doc({
    url: '/an1.11-20', title: 'AN 1.11–20 Nīvaraṇappahāna Vagga',
    tags: ['an', 'hindrances'], tagtitles: ['Aṅguttara Nikāya', 'The Hindrances']
  }),
  'content-canon-ud1-3': doc({
    url: '/ud1.3', title: 'Ud 1.3 Tatiya Bodhi Sutta',
    tags: ['nibbana', 'ud', 'origination'], tagtitles: ['Nibbāna', 'Udāna', 'Dependent Origination']
  }),
  'content-av-after-nibbana': doc({
    url: '/after-nibbana', title: 'After Nibbana',
    tags: ['arahant', 'renunciation', 'nibbana'], tagtitles: ['Arahants', 'renunciation', 'Nibbāna: The Goal of Buddhist Practice']
  }),
  'content-av-mind-stilled': doc({
    url: '/mind-stilled', title: 'The Island',
    tags: ['nibbana-mind-stilled'], tagtitles: ['Nibbāna: The Mind Stilled']
  }),
  'content-articles-brahmas-invitation': doc({
    url: '/brahmas-invitation', title: "Brahmā's Invitation",
    tags: ['ma', 'sa'], tagtitles: ['Madhyama Āgama', 'Saṃyukta Āgama']
  }),
  'content-articles-canon-studies': doc({
    url: '/canon-studies', title: 'The Buddhist Canon',
    tags: ['pali-canon', 'academic'], tagtitles: ['The Pāli Canon', 'academic']
  }),
  'content-booklets-pali-grammar': doc({
    url: '/pali-grammar', title: 'A Practical Grammar',
    tags: ['pali-grammar'], tagtitles: ['Pāli Grammar']
  }),
  'content-articles-poems': doc({
    url: '/poems', title: 'Poems',
    tags: ['canonical-poetry', 'emptiness', 'chan-lit'], tagtitles: ['Poetry of the Pāḷi Canon', 'Śūnyatā', 'Chán Literature']
  }),
  'content-articles-gotamis-poem': doc({
    url: '/gotamis-poem', title: "Gotamī's Poem",
    tags: ['tg', 'setting', 'sakkayaditthi'], tagtitles: ['Thera/Therīgāthā', "Buddha's India", 'Sakkāyadiṭṭhi - Self View']
  }),
  'content-articles-spindle-whorls': doc({
    url: '/spindle-whorls', title: 'Spindle Whorls',
    tags: ['prehistory', 'higher-ed'], tagtitles: ['prehistory', 'higher-ed']
  }),
  'content-articles-daoism': doc({
    url: '/daoism', title: 'Daoism',
    tags: ['chinese-religion'], tagtitles: ['Chinese Religion']
  }),
  'content-articles-confucianism': doc({
    url: '/confucianism', title: 'Confucianism',
    tags: ['chinese-religions'], tagtitles: ['chinese-religions']
  }),
  'content-articles-anicca': doc({
    url: '/anicca', title: 'Anicca',
    tags: ['philosophy'], tagtitles: ['An Introduction to Buddhist Philosophy']
  }),
});

describe('search_index.js tags', () => {
  it('labels each tag once, by its title, highlighting the original accented words', () => {
    const r = search('anguttara');
    assert.equal(r.warning, '');
    assert.deepEqual(r.labels, {
      '/tags/an': [],
      '/an1.11-20': ['<strong>Aṅguttara</strong> Nikāya'],
    });
    assert.deepEqual(search('tag:nikaya').labels, { '/an1.11-20': ['Aṅguttara <strong>Nikāya</strong>'] });
  });

  for (const [q, url, label] of [
    ['tag:samyukta', '/brahmas-invitation', '<strong>Saṃyukta</strong> Āgama'],
    ['tag:sunyata', '/poems', '<strong>Śūnyatā</strong>'],
    ['tag:chan', '/poems', '<strong>Chán</strong> Literature'],
    ['tag:therigatha', '/gotamis-poem', 'Thera/<strong>Therīgāthā</strong>'],
    ['tag:buddha', '/gotamis-poem', "<strong>Buddha</strong>'s India"],
    ["tag:buddha's", '/gotamis-poem', "<strong>Buddha</strong>'s India"],
    ['tag:self', '/gotamis-poem', 'Sakkāyadiṭṭhi - <strong>Self</strong> View'],
    ['tag:stilled', '/mind-stilled', 'Nibbāna: The Mind <strong>Stilled</strong>'],
    ['tag:nibbāna', '/mind-stilled', '<strong>Nibbāna</strong>: The Mind Stilled'],
    ['tag:NIBBANA', '/mind-stilled', '<strong>Nibbāna</strong>: The Mind Stilled'],
  ]) {
    it(`"${q}" highlights ${label}`, () => {
      const r = search(q);
      assert.equal(r.warning, '');
      assert.deepEqual(r.labels[url], [label]);
    });
  }

  it('"tag:" matches raw tags whole, highlighting their titles', () => {
    assert.deepEqual(search('tag:nibbana').labels, {
      '/ud1.3': ['<strong>Nibbāna</strong>'],
      '/after-nibbana': ['<strong>Nibbāna: The Goal of Buddhist Practice</strong>'],
      '/mind-stilled': ['<strong>Nibbāna</strong>: The Mind Stilled'],
    });
    assert.deepEqual(search('tag:ma').labels, { '/brahmas-invitation': ['<strong>Madhyama Āgama</strong>'] });
    assert.deepEqual(search('tag:pali-grammar').labels, { '/pali-grammar': ['<strong>Pāli Grammar</strong>'] });
    assert.deepEqual(search('tag:prehistory').labels, { '/spindle-whorls': ['<strong>prehistory</strong>'] });
    assert.deepEqual(search('tag:higher-ed').labels, { '/spindle-whorls': ['<strong>higher ed</strong>'] });
  });

  it('"tag:" matches raw tags or title words', () => {
    assert.deepEqual(search('tag:an').labels, {
      '/an1.11-20': ['<strong>Aṅguttara Nikāya</strong>'],
      '/anicca': ['<strong>An</strong> Introduction to Buddhist Philosophy'],
    });
    assert.deepEqual(search('tag:pali').labels, {
      '/canon-studies': ['The <strong>Pāli</strong> Canon'],
      '/pali-grammar': ['<strong>Pāli</strong> Grammar'],
      '/poems': ['Poetry of the <strong>Pāḷi</strong> Canon'],
    });
  });

  for (const q of ['tag:pali-canon', 'rawtag:pali-canon', 'rawtag:Pali-Canon', '+rawtag:pali-canon']) {
    it(`"${q}" matches only items tagged pali-canon`, () => {
      const r = search(q);
      assert.equal(r.warning, '');
      assert.deepEqual(r.labels, { '/canon-studies': ['<strong>The Pāli Canon</strong>'] });
    });
  }

  it('does not stem hyphenated raw tags', () => {
    assert.deepEqual(search('rawtag:chinese-religion').labels, { '/daoism': ['<strong>Chinese Religion</strong>'] });
    assert.deepEqual(search('tag:chinese-religions').labels, { '/confucianism': ['<strong>chinese religions</strong>'] });
  });

  it('"rawtag:" ignores title words', () => {
    assert.deepEqual(search('rawtag:an').labels, { '/an1.11-20': ['<strong>Aṅguttara Nikāya</strong>'] });
    assert.deepEqual(search('rawtag:anguttara').labels, {});
    assert.deepEqual(search('rawtag:goal').labels, {});
  });

  it('"-tag:" excludes raw tags and title words', () => {
    assert.deepEqual(Object.keys(search('tag:nibbana -tag:ud').labels), ['/after-nibbana', '/mind-stilled']);
    assert.deepEqual(Object.keys(search('tag:nibbana -tag:udana').labels), ['/after-nibbana', '/mind-stilled']);
    assert.deepEqual(Object.keys(search('tag:nibbana -rawtag:nibbana').labels), ['/mind-stilled']);
    assert.deepEqual(Object.keys(search('tag:pali -tag:pali-canon').labels), ['/pali-grammar', '/poems']);
  });

  it('plain terms search tag titles and raw tags', () => {
    assert.deepEqual(search('setting').labels, { '/gotamis-poem': ["<strong>Buddha's India</strong>"] });
    assert.deepEqual(search('chan emptiness').labels, { '/poems': ['<strong>Śūnyatā</strong>', '<strong>Chán</strong> Literature'] });
    assert.deepEqual(search('pali canon').labels, {
      '/canon-studies': ['The <strong>Pāli Canon</strong>'],
      '/poems': ['Poetry of the <strong>Pāḷi Canon</strong>'],
    });
  });

  it('copes with decomposed and non-string tags', () => {
    const r = loadSearchWorker({
      d: doc({ url: '/d', tags: [1, 'vipassana', 'nibbana'], tagtitles: [1, 'Vipassana\u0304', 'Nibbāna: The Goal'] })
    })('tag:goal');
    assert.deepEqual(r.labels, { '/d': ['Nibbāna: The <strong>Goal</strong>'] });
  });
});
