const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const { HtmlValidate } = require('html-validate');

const htmlValidate = new HtmlValidate({
  rules: {
    'void-style': 'off',
    'no-trailing-whitespace': 'off',
    'doctype-html': 'off',
    'document-structure': 'off',
    'missing-doctype': 'off',
    'element-required-content': 'off',
    'no-raw-characters': 'off',
  }
});

function assertValidHtml(html, label) {
  const report = htmlValidate.validateStringSync(`<div>${html}</div>`);
  assert.ok(report.valid, `${label}: invalid HTML — ${
    report.results.flatMap(r => r.messages.map(m => m.message)).join('; ')
  }`);
}

// Helper: bring vm-realm objects into the current realm for deepEqual
function toLocal(obj) { return JSON.parse(JSON.stringify(obj)); }

// Load utils.js (search_functions.js depends on sortedInsert and Ranges)
const utilsSrc = fs.readFileSync(
  path.join(__dirname, '..', 'utils.js'),
  'utf-8'
);

// Load search_functions.js directly (no more extractFunction parser needed)
const searchFnSrc = fs.readFileSync(
  path.join(__dirname, '..', 'search_functions.js'),
  'utf-8'
);

// vm.createContext() creates a bare sandbox with no built-in globals.
// Unlike the main Node.js runtime, Math, Array, etc. must be provided explicitly.
const sandbox = { Set, Math, RegExp, Array, String, Number, console };
vm.createContext(sandbox);
vm.runInContext(
  utilsSrc + '\nthis.utils = utils;\nthis.Ranges = Ranges;\n' +
  'this.UpdateQueryString = UpdateQueryString;\n' +
  'this.locationOf = locationOf;\nthis.sortedInsert = sortedInsert;\n',
  sandbox
);

// Provide a minimal lunr stub for handleSearchMessage
vm.runInContext(
  'var lunr = { stopWordFilter: function(s) { ' +
  '  var stops = ["the","a","an","and","is","in","it","of","to"];' +
  '  return stops.indexOf(s.toLowerCase()) < 0 ? s : undefined;' +
  '} };\n',
  sandbox
);

// Provide an empty store so displaySearchResults can run
vm.runInContext('var store = {};\n', sandbox);

vm.runInContext(
  searchFnSrc +
  '\nthis.categoryName = categoryName;\n' +
  'this.getPositions = getPositions;\n' +
  'this.resultMatched = resultMatched;\n' +
  'this.addMatchHighlights = addMatchHighlights;\n' +
  'this.getBlurbForResult = getBlurbForResult;\n' +
  'this.normalizeSuttaTitles = normalizeSuttaTitles;\n' +
  'this.findOneWordSuttaTitleMatches = findOneWordSuttaTitleMatches;\n' +
  'this.handleSearchMessage = handleSearchMessage;\n' +
  'this.displaySearchResults = displaySearchResults;\n',
  sandbox
);

const {
  categoryName, getPositions, resultMatched,
  addMatchHighlights, getBlurbForResult, oneWordToken, normalizeSuttaTitles, findOneWordSuttaTitleMatches, handleSearchMessage
} = sandbox;

// ── categoryName ────────────────────────────────────────────────────

describe('categoryName', () => {
  it('returns non-empty HTML containing an icon for known categories', () => {
    const knownCategories = [
      'av', 'articles', 'booklets', 'monographs',
      'papers', 'essays', 'canon', 'reference', 'excerpts'
    ];
    for (const cat of knownCategories) {
      const html = categoryName(cat);
      assert.ok(html.length > 0, `Expected non-empty HTML for "${cat}"`);
      assert.ok(html.includes('<i class='), `Expected icon element for "${cat}"`);
      assertValidHtml(html, `categoryName("${cat}")`);
    }
  });

  it('returns fallback HTML for unknown category', () => {
    const html = categoryName('unknown');
    assert.ok(html.includes('<i class='), 'Expected icon in fallback');
    assert.ok(html.length > 0);
  });

  it('returns fallback HTML for null/undefined', () => {
    assert.ok(categoryName(null).includes('<i class='));
    assert.ok(categoryName(undefined).includes('<i class='));
  });

  it('known categories produce different output than the fallback', () => {
    const fallback = categoryName('unknown');
    assert.notEqual(categoryName('av'), fallback);
    assert.notEqual(categoryName('articles'), fallback);
  });
});

// ── getPositions ────────────────────────────────────────────────────

describe('getPositions', () => {
  it('returns empty array when no match data for the field', () => {
    const result = {
      matchData: { metadata: { term: { otherfield: { position: [[0, 4]] } } } }
    };
    assert.deepEqual(toLocal(getPositions(result, 'content')), []);
  });

  it('returns sorted positions from match metadata', () => {
    const result = {
      matchData: {
        metadata: {
          foo: { content: { position: [[10, 3], [2, 4]] } },
          bar: { content: { position: [[5, 2]] } },
        }
      }
    };
    const positions = getPositions(result, 'content');
    assert.deepEqual(toLocal(positions), [2, 5, 10]);
  });

  it('returns empty array when metadata is empty', () => {
    const result = { matchData: { metadata: {} } };
    assert.deepEqual(toLocal(getPositions(result, 'content')), []);
  });
});

// ── resultMatched ───────────────────────────────────────────────────

describe('resultMatched', () => {
  it('returns true when field has match positions', () => {
    const result = {
      matchData: { metadata: { term: { title: { position: [[0, 5]] } } } }
    };
    assert.equal(resultMatched(result, 'title'), true);
  });

  it('returns false when field has no matches', () => {
    const result = {
      matchData: { metadata: { term: { content: { position: [[0, 5]] } } } }
    };
    assert.equal(resultMatched(result, 'title'), false);
  });

  it('returns false when metadata is empty', () => {
    const result = { matchData: { metadata: {} } };
    assert.equal(resultMatched(result, 'title'), false);
  });
});

// ── addMatchHighlights ──────────────────────────────────────────────

describe('addMatchHighlights', () => {
  it('wraps matched positions in <strong> tags', () => {
    const result = {
      matchData: { metadata: { term: { content: { position: [[0, 5]] } } } }
    };
    const highlighted = addMatchHighlights(result, 'hello world', 'content');
    assert.ok(highlighted.includes('<strong>hello</strong>'));
    assertValidHtml(highlighted, 'addMatchHighlights single match');
  });

  it('returns original text when no matches for the field', () => {
    const result = {
      matchData: { metadata: { term: { title: { position: [[0, 3]] } } } }
    };
    const highlighted = addMatchHighlights(result, 'hello world', 'content');
    assert.equal(highlighted, 'hello world');
  });

  it('handles multiple non-overlapping matches', () => {
    const result = {
      matchData: {
        metadata: {
          foo: { content: { position: [[0, 3]] } },
          bar: { content: { position: [[7, 3]] } },
        }
      }
    };
    const highlighted = addMatchHighlights(result, 'foo is bar!!', 'content');
    assert.ok(highlighted.includes('<strong>foo</strong>'));
    assert.ok(highlighted.includes('<strong>bar</strong>'));
    assertValidHtml(highlighted, 'addMatchHighlights multiple matches');
  });

  it('respects startindex and endindex parameters', () => {
    const result = {
      matchData: { metadata: { term: { content: { position: [[5, 3]] } } } }
    };
    // blurb is a slice of content from index 3 to 9: "lo wor"
    // match at position 5 length 3 => "wor" within the blurb
    const highlighted = addMatchHighlights(result, 'lo wor', 'content', 3, 9);
    assert.ok(highlighted.includes('<strong>'));
    assertValidHtml(highlighted, 'addMatchHighlights with startindex/endindex');
  });
});

// ── getBlurbForResult ───────────────────────────────────────────────

describe('getBlurbForResult', () => {
  it('returns highlighted description when title matches', () => {
    const result = {
      matchData: { metadata: { dharma: { title: { position: [[0, 6]] } } } }
    };
    const item = {
      title: 'Dharma Talk',
      description: 'A talk about dharma practice',
      content: 'Some long content here'
    };
    const blurb = getBlurbForResult(result, item, []);
    assert.ok(blurb.includes('talk about dharma'));
    assertValidHtml(blurb, 'getBlurbForResult title match');
  });

  it('returns description when no content positions', () => {
    const result = {
      matchData: { metadata: { term: { content: { position: [] } } } }
    };
    const item = {
      title: 'Test',
      description: 'A short description',
      content: 'content body'
    };
    const blurb = getBlurbForResult(result, item, []);
    assert.ok(blurb.includes('short description'));
    assertValidHtml(blurb, 'getBlurbForResult no content positions');
  });

  it('truncates long descriptions with ellipsis', () => {
    const result = {
      matchData: { metadata: { term: { title: { position: [[0, 4]] } } } }
    };
    const longDesc = 'word '.repeat(100);
    const item = { title: 'Test', description: longDesc, content: '' };
    const blurb = getBlurbForResult(result, item, []);
    assert.ok(blurb.endsWith('...'));
    assert.ok(blurb.length < longDesc.length);
    assertValidHtml(blurb, 'getBlurbForResult truncated description');
  });

  it('extracts content blurb around match positions', () => {
    // 'a '.repeat(50) produces 100 chars, so MATCH starts at index 100
    const result = {
      matchData: { metadata: { term: { content: { position: [[100, 5]] } } } }
    };
    const content = 'a '.repeat(50) + 'MATCH' + ' b'.repeat(200);
    const item = { title: 'Test', description: null, content: content };
    const blurb = getBlurbForResult(result, item, [100]);
    assert.ok(blurb.includes('<strong>MATCH</strong>'),
      'Expected MATCH to be wrapped in <strong> tags');
    assertValidHtml(blurb, 'getBlurbForResult content blurb');
  });

  it('finds the section with the most matches', () => {
    // Build content longer than BMAX (250) so the algorithm must choose a section.
    // Place a lone match (IGNORE) FIRST, then a cluster of 3 matches later.
    // A greedy algorithm that picks the first match would incorrectly select IGNORE.
    // Positions array (sorted): [10=IGNORE, 320=MATCH, 335=ME, 347=INSTEAD]
    const content = 'a'.repeat(10) + 'IGNORE' + 'b'.repeat(304) + 'MATCH' +
                    'c'.repeat(10) + 'ME' + 'c'.repeat(10) + 'INSTEAD' + 'e'.repeat(100);
    const ignorePos = 10;
    const matchPos = 10 + 6 + 304;    // 320
    const mePos = 320 + 5 + 10;       // 335
    const insteadPos = 335 + 2 + 10;  // 347
    const result = {
      matchData: { metadata: {
        kw: { content: { position: [
          [ignorePos, 6], [matchPos, 5], [mePos, 2], [insteadPos, 7]
        ] } },
      } }
    };
    const positions = [ignorePos, matchPos, mePos, insteadPos];
    const item = { title: 'Test', description: null, content: content };
    const blurb = getBlurbForResult(result, item, positions);
    // Should pick the cluster (MATCH, ME, INSTEAD) not the lone IGNORE
    assert.ok(!blurb.includes('IGNORE'), 'Expected blurb to NOT contain IGNORE');
    assert.ok(blurb.includes('MATCH'), 'Expected blurb to contain MATCH');
    assert.ok(blurb.includes('INSTEAD'), 'Expected blurb to contain INSTEAD');
  });
});

// ── normalizeSuttaTitles ─────────────────────────────────────────────
describe('normalizeSuttaTitles', () => {

  it('returns an array of database objects with a new normalized title', () => {
    const mockStore = {
      id1: {
        title: 'MN 35 Cūḷa Saccaka Sutta: The Shorter Discourse With Saccaka',
        type: 'content',
        category: 'canon'
      }
    };
    const result = normalizeSuttaTitles(mockStore);
    assert.equal(result.length, 1);
    assert.equal(result[0].ref, 'id1');
    assert.equal(result[0].title, 'culasaccakasutta');
  });

  it('remove words after sutta and sutra but using : as a reference', () => {
    const mockStore = {
      id1: {
        title: 'MA 128 Upasaka Sutra: Discourse on the White-Clad Disciple',
        type: 'content',
        category: 'canon'
      }
    };
    const result = normalizeSuttaTitles(mockStore);
    assert.equal(result.length, 1);
    assert.equal(result[0].ref, 'id1');
    assert.equal(result[0].title, 'upasakasutra');
  });

  it('integrated more nikaya indexes for parsing - lets test lal', () => {
    const mockStore = {
      id1: {
        title: 'Lal 26 Dharmacakrapravartana Sūtra: The Discourse that Set the Dharma-Wheel Rolling',
        type: 'content',
        category: 'canon'
      }
    };
    const result = normalizeSuttaTitles(mockStore);
    assert.equal(result.length, 1);
    assert.equal(result[0].ref, 'id1');
    assert.equal(result[0].title, 'dharmacakrapravartanasutra');
  });

  it('it returns a joined title from a thig nikaya leading discourse', () => {
    const mockStore = {
      id1: {
        title: "Thig 3.8 Somā Therīgāthā: Somā's Verses",
        type: 'content',
        category: 'canon'
      }
    };
    const result = normalizeSuttaTitles(mockStore);
    assert.equal(result.length, 1);
    assert.equal(result[0].ref, 'id1');
    assert.equal(result[0].title, 'somatherigatha');
  });

  it('it returns a joined title from a thag nikaya leading discourse', () => {
    const mockStore = {
      id1: {
        title: "Thag 1.7 Bhalliya Theragāthā: Bhalliya's Verse",
        type: 'content',
        category: 'canon'
      }
    };
    const result = normalizeSuttaTitles(mockStore);
    assert.equal(result.length, 1);
    assert.equal(result[0].ref, 'id1');
    assert.equal(result[0].title, 'bhalliyatheragatha');
  });

  it('handles "the" and removes it from a string if it appears at the beginning', () => {
    const mockStore = {
      id1: {
        title: 'DN 22 The Mahāsatipaṭṭhāna Sutta: The Long Discourse about the Ways of Attending to Mindfulness',
        type: 'content',
        category: 'canon'
      }
    };
    const result = normalizeSuttaTitles(mockStore);
    assert.equal(result.length, 1);
    assert.equal(result[0].ref, 'id1');
    assert.equal(result[0].title, 'mahasatipatthanasutta');
  });


});

// ── findOneWordSuttaTitleMatches ─────────────────────────────────────────────
describe('findOneWordSuttaTitleMatches', () => {
  it('returns matched item when query matches title exactly', () => {
    const mockStore = {
      'id1': { title: 'culasaccakasutta', type: 'content', category: 'canon' }
    };
    const result = findOneWordSuttaTitleMatches('culasaccakasutta', mockStore);
    assert.equal(toLocal(result).length, 1);
  });
});

// ── handleSearchMessage ─────────────────────────────────────────────

describe('handleSearchMessage', () => {
  it('returns result object with expected keys', () => {
    const mockSearch = () => [];
    const data = { q: 'dharma', filterquery: '', qt: 'test' };
    const result = toLocal(handleSearchMessage(data, mockSearch));
    assert.ok('warninghtml' in result);
    assert.ok('html' in result);
    assert.ok('count' in result);
    assert.ok('q' in result);
    assert.equal(result.q, 'dharma');
    assert.equal(result.qt, 'test');
  });

  it('returns no-results HTML when search yields nothing', () => {
    const mockSearch = () => [];
    const data = { q: 'xyz', filterquery: '', qt: '' };
    const result = toLocal(handleSearchMessage(data, mockSearch));
    assert.equal(result.count, 0);
    assert.ok(result.html.includes('No results found'));
  });

  it('prefixes non-stop words with + for required matching', () => {
    const queries = [];
    const mockSearch = (q) => { queries.push(q); return []; };
    const data = { q: 'dharma practice', filterquery: '', qt: '' };
    handleSearchMessage(data, mockSearch);
    // First call should have +dharma +practice (both non-stop words)
    assert.ok(queries[0].includes('+dharma'));
    assert.ok(queries[0].includes('+practice'));
  });

  it('does not prefix stop words with +', () => {
    const queries = [];
    const mockSearch = (q) => { queries.push(q); return []; };
    const data = { q: 'the dharma', filterquery: '', qt: '' };
    handleSearchMessage(data, mockSearch);
    // "the" is a stop word, should not get +
    assert.ok(!queries[0].includes('+the'));
    assert.ok(queries[0].includes('+dharma'));
  });

  it('preserves +- prefix combination', () => {
    const queries = [];
    const mockSearch = (q) => { queries.push(q); return []; };
    const data = { q: '+dharma -samsara', filterquery: '', qt: '' };
    handleSearchMessage(data, mockSearch);
    assert.ok(queries[0].includes('+dharma'));
    assert.ok(queries[0].includes('-samsara'));
    assert.ok(!queries[0].includes('++'));
  });

  it('preserves -- prefix combination', () => {
    const queries = [];
    const mockSearch = (q) => { queries.push(q); return []; };
    const data = { q: '-dharma -samsara', filterquery: '', qt: '' };
    handleSearchMessage(data, mockSearch);
    assert.ok(queries[0].includes('-dharma'));
    assert.ok(queries[0].includes('-samsara'));
  });

  it('preserves -+ prefix combination', () => {
    const queries = [];
    const mockSearch = (q) => { queries.push(q); return []; };
    const data = { q: '-dharma +samsara', filterquery: '', qt: '' };
    handleSearchMessage(data, mockSearch);
    assert.ok(queries[0].includes('-dharma'));
    assert.ok(queries[0].includes('+samsara'));
  });

  it('falls back to unprefixed query when required query returns nothing', () => {
    let callCount = 0;
    const mockSearch = () => { callCount++; return []; };
    const data = { q: 'dharma nibbana', filterquery: '', qt: '' };
    handleSearchMessage(data, mockSearch);
    // Should call at least twice: once with +prefixed, once with original
    assert.ok(callCount >= 2, `Expected at least 2 search calls, got ${callCount}`);
  });

  it('filters results by filterquery when provided', () => {
    const mockResults = [
      { ref: 'a', matchData: { metadata: {} } },
      { ref: 'b', matchData: { metadata: {} } },
    ];
    const filterResults = [{ ref: 'b' }];
    // Set up store entries so displaySearchResults can render
    vm.runInContext(
      'store["a"] = { type:"content", title:"A", description:"desc a", content:"", ' +
      '  tags:[], authors:[], category:"articles", formats:[], url:"/a" };\n' +
      'store["b"] = { type:"content", title:"B", description:"desc b", content:"", ' +
      '  tags:[], authors:[], category:"articles", formats:[], url:"/b" };\n',
      sandbox
    );
    const mockSearch = (q) => {
      if (q.includes('filter')) return filterResults;
      return mockResults;
    };
    const data = { q: 'test', filterquery: 'filter:tag', qt: '' };
    const result = toLocal(handleSearchMessage(data, mockSearch));
    assert.equal(result.count, 1);
    // Clean up store
    vm.runInContext('delete store["a"]; delete store["b"];', sandbox);
  });

  it('passes through q and filterquery in result', () => {
    const mockSearch = () => [];
    const data = { q: 'meditation', filterquery: 'tag:zen', qt: 'search' };
    const result = toLocal(handleSearchMessage(data, mockSearch));
    assert.equal(result.q, 'meditation');
    assert.equal(result.filterquery, 'tag:zen');
  });
});
