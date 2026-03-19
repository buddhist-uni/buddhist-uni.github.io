const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

// Helper: bring vm-realm objects into the current realm for deepEqual
function toLocal(obj) { return JSON.parse(JSON.stringify(obj)); }

// search_index.js is a Jekyll/Liquid template, so we cannot load it
// directly. Instead we extract the pure JavaScript functions that do
// not depend on Liquid-generated data and test them in isolation.

// First, load utils.js (search_index.js depends on sortedInsert and Ranges)
const utilsSrc = fs.readFileSync(
  path.join(__dirname, '..', 'utils.js'),
  'utf-8'
);

// Extract pure JS functions from the Liquid template
const searchSrc = fs.readFileSync(
  path.join(__dirname, '..', 'search_index.js'),
  'utf-8'
);

function extractFunction(src, funcName) {
  const startRe = new RegExp(`^function ${funcName}\\b`, 'm');
  const match = startRe.exec(src);
  if (!match) throw new Error(`Could not find function ${funcName}`);
  let depth = 0;
  let started = false;
  let end = match.index;
  for (let i = match.index; i < src.length; i++) {
    if (src[i] === '{') { depth++; started = true; }
    if (src[i] === '}') { depth--; }
    if (started && depth === 0) { end = i + 1; break; }
  }
  return src.substring(match.index, end);
}

const fnSrcs = [
  'categoryName', 'getPositions', 'resultMatched',
  'addMatchHighlights', 'getBlurbForResult'
].map(name => extractFunction(searchSrc, name));

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
// Provide BMAX constant used by getBlurbForResult
vm.runInContext('var BMAX = 250;\n', sandbox);
vm.runInContext(
  fnSrcs.join('\n') +
  '\nthis.categoryName = categoryName;\n' +
  'this.getPositions = getPositions;\n' +
  'this.resultMatched = resultMatched;\n' +
  'this.addMatchHighlights = addMatchHighlights;\n' +
  'this.getBlurbForResult = getBlurbForResult;\n',
  sandbox
);

const { categoryName, getPositions, resultMatched, addMatchHighlights, getBlurbForResult } = sandbox;

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
  });

  it('respects startindex and endindex parameters', () => {
    const result = {
      matchData: { metadata: { term: { content: { position: [[5, 3]] } } } }
    };
    // blurb is a slice of content from index 3 to 9: "lo wor"
    // match at position 5 length 3 => "wor" within the blurb
    const highlighted = addMatchHighlights(result, 'lo wor', 'content', 3, 9);
    assert.ok(highlighted.includes('<strong>'));
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
  });

  it('extracts content blurb around match positions', () => {
    const result = {
      matchData: { metadata: { term: { content: { position: [[50, 5]] } } } }
    };
    const content = 'a '.repeat(50) + 'MATCH' + ' b'.repeat(200);
    const item = { title: 'Test', description: null, content: content };
    const blurb = getBlurbForResult(result, item, [50]);
    assert.ok(blurb.includes('MATCH') || blurb.includes('<strong>'));
  });
});
