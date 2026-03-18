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
  path.join(__dirname, '..', 'assets', 'js', 'utils.js'),
  'utf-8'
);

// Extract pure JS functions from the Liquid template
const searchSrc = fs.readFileSync(
  path.join(__dirname, '..', 'assets', 'js', 'search_index.js'),
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

const fnSrcs = ['categoryName', 'getPositions', 'resultMatched'].map(
  name => extractFunction(searchSrc, name)
);

const sandbox = { Set, Math, RegExp, Array, console };
vm.createContext(sandbox);
vm.runInContext(
  utilsSrc + '\nthis.utils = utils;\nthis.Ranges = Ranges;\n' +
  'this.UpdateQueryString = UpdateQueryString;\n' +
  'this.locationOf = locationOf;\nthis.sortedInsert = sortedInsert;\n',
  sandbox
);
vm.runInContext(
  fnSrcs.join('\n') +
  '\nthis.categoryName = categoryName;\n' +
  'this.getPositions = getPositions;\n' +
  'this.resultMatched = resultMatched;\n',
  sandbox
);

const { categoryName, getPositions, resultMatched } = sandbox;

// ── categoryName ────────────────────────────────────────────────────

describe('categoryName', () => {
  it('returns correct HTML for known categories', () => {
    assert.ok(categoryName('av').includes('Recording'));
    assert.ok(categoryName('articles').includes('Article'));
    assert.ok(categoryName('booklets').includes('Book'));
    assert.ok(categoryName('monographs').includes('Book'));
    assert.ok(categoryName('papers').includes('Paper'));
    assert.ok(categoryName('essays').includes('Essay'));
    assert.ok(categoryName('canon').includes('Canonical Work'));
    assert.ok(categoryName('reference').includes('Reference Work'));
    assert.ok(categoryName('excerpts').includes('Excerpt'));
  });

  it('returns fallback for unknown category', () => {
    assert.ok(categoryName('unknown').includes('Library Item'));
    assert.ok(categoryName(null).includes('Library Item'));
    assert.ok(categoryName(undefined).includes('Library Item'));
  });

  it('returns HTML with an icon element', () => {
    assert.ok(categoryName('av').includes('<i class='));
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
