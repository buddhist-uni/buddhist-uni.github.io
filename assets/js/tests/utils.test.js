const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

// Helper: bring vm-realm objects into the current realm for deepEqual
function toLocal(obj) { return JSON.parse(JSON.stringify(obj)); }

// Load utils.js into a sandbox
const utilsSrc = fs.readFileSync(
  path.join(__dirname, '..', 'utils.js'),
  'utf-8'
);
// vm.createContext() creates a bare sandbox with no built-in globals.
// Unlike the main Node.js runtime, Math, Array, etc. must be provided explicitly.
const sandbox = { Set, Math, RegExp, Array, console };
vm.createContext(sandbox);
vm.runInContext(
  utilsSrc + '\nthis.utils = utils;\nthis.Ranges = Ranges;\n' +
  'this.UpdateQueryString = UpdateQueryString;\n' +
  'this.locationOf = locationOf;\nthis.sortedInsert = sortedInsert;\n',
  sandbox
);

const { utils, UpdateQueryString, locationOf, sortedInsert, Ranges } = sandbox;

// ── utils.unaccented ────────────────────────────────────────────────

describe('utils.unaccented', () => {
  it('strips Pali diacritics', () => {
    assert.equal(utils.unaccented('āgama'), 'agama');
    assert.equal(utils.unaccented('Ānanda'), 'Ananda');
    assert.equal(utils.unaccented('saṃsāra'), 'samsara');
    assert.equal(utils.unaccented('nibbāna'), 'nibbana');
  });

  it('strips accents from common European words', () => {
    assert.equal(utils.unaccented('café'), 'cafe');
    assert.equal(utils.unaccented('naïve'), 'naive');
    assert.equal(utils.unaccented('über'), 'uber');
  });

  it('returns empty string unchanged', () => {
    assert.equal(utils.unaccented(''), '');
  });

  it('returns plain ASCII unchanged', () => {
    assert.equal(utils.unaccented('hello world'), 'hello world');
  });

  it('returns falsy values as-is', () => {
    assert.equal(utils.unaccented(null), null);
    assert.equal(utils.unaccented(undefined), undefined);
  });
});

// ── UpdateQueryString ───────────────────────────────────────────────

describe('UpdateQueryString', () => {
  it('adds a new query parameter', () => {
    const result = UpdateQueryString('q', 'test', 'https://example.com/search');
    assert.equal(result, 'https://example.com/search?q=test');
  });

  it('replaces an existing query parameter', () => {
    const result = UpdateQueryString('q', 'new', 'https://example.com/search?q=old');
    assert.equal(result, 'https://example.com/search?q=new');
  });

  it('adds param to URL that already has other params', () => {
    const result = UpdateQueryString('page', '2', 'https://example.com/search?q=test');
    assert.equal(result, 'https://example.com/search?q=test&page=2');
  });

  it('preserves hash fragment when adding param', () => {
    const result = UpdateQueryString('q', 'test', 'https://example.com/page#section');
    assert.equal(result, 'https://example.com/page?q=test#section');
  });

  it('preserves hash fragment when replacing param', () => {
    const result = UpdateQueryString('q', 'new', 'https://example.com/page?q=old#section');
    assert.equal(result, 'https://example.com/page?q=new#section');
  });

  it('encodes special characters in the value', () => {
    const result = UpdateQueryString('q', 'hello world', 'https://example.com/');
    assert.equal(result, 'https://example.com/?q=hello%20world');
  });
});

// ── locationOf (binary search) ──────────────────────────────────────

describe('locationOf', () => {
  it('returns 0 for empty array', () => {
    assert.equal(locationOf([], 5), 0);
  });

  it('finds correct insertion point at start', () => {
    assert.equal(locationOf([10, 20, 30], 5), 0);
  });

  it('finds correct insertion point in middle', () => {
    assert.equal(locationOf([10, 20, 30], 15), 1);
  });

  it('finds correct insertion point at end', () => {
    assert.equal(locationOf([10, 20, 30], 35), 3);
  });

  it('handles single-element array', () => {
    assert.equal(locationOf([10], 5), 0);
    assert.equal(locationOf([10], 15), 1);
  });

  it('accepts a custom comparer', () => {
    const reverseComparer = (a, b) => a < b;
    const arr = [30, 20, 10];
    const pos = locationOf(arr, 25, reverseComparer);
    assert.equal(pos, 1);
  });
});

// ── sortedInsert ────────────────────────────────────────────────────

describe('sortedInsert', () => {
  it('inserts into empty array', () => {
    assert.deepEqual(toLocal(sortedInsert([], 5)), [5]);
  });

  it('maintains sorted order', () => {
    let arr = [];
    sortedInsert(arr, 30);
    sortedInsert(arr, 10);
    sortedInsert(arr, 20);
    assert.deepEqual(toLocal(arr), [10, 20, 30]);
  });

  it('handles duplicate values', () => {
    let arr = [10, 20, 30];
    sortedInsert(arr, 20);
    assert.equal(arr.length, 4);
    const idx = arr.indexOf(20);
    assert.equal(arr[idx + 1], 20);
  });
});

// ── Ranges ──────────────────────────────────────────────────────────

describe('Ranges', () => {
  it('accumulates non-overlapping ranges', () => {
    const r = new Ranges();
    r.add([0, 5]);
    r.add([10, 15]);
    assert.deepEqual(toLocal(r.array), [[0, 5], [10, 15]]);
  });

  it('merges overlapping ranges', () => {
    const r = new Ranges();
    r.add([0, 10]);
    r.add([5, 15]);
    assert.deepEqual(toLocal(r.array), [[0, 15]]);
  });

  it('merges adjacent ranges', () => {
    const r = new Ranges();
    r.add([0, 5]);
    r.add([6, 10]);
    assert.deepEqual(toLocal(r.array), [[0, 10]]);
  });

  it('inserts ranges in sorted order', () => {
    const r = new Ranges();
    r.add([10, 20]);
    r.add([0, 5]);
    assert.deepEqual(toLocal(r.array), [[0, 5], [10, 20]]);
  });

  it('merges a range that spans two existing ranges', () => {
    const r = new Ranges();
    r.add([0, 5]);
    r.add([10, 15]);
    r.add([3, 12]);
    assert.deepEqual(toLocal(r.array), [[0, 15]]);
  });
});
