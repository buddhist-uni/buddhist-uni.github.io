const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

// Load only the cyrb53 function from buggytrack.js
// The file also creates a BuggyTracker that needs `document`, so we
// provide minimal DOM stubs to let the file evaluate without errors.
const src = fs.readFileSync(
  path.join(__dirname, '..', 'buggytrack.js'),
  'utf-8'
);

// vm.createContext() creates a bare sandbox with no built-in globals.
// Unlike the main Node.js runtime, Math, Array, etc. must be provided explicitly.
const sandbox = {
  Math,
  console,
  localStorage: {
    getItem() { return null; },
    setItem() {},
  },
  window: { WEBSITE_SECTION: 'test' },
  gtag() {},
  document: {
    createElement() {
      return { href: '', host: '', hostname: '', pathname: '' };
    },
    location: { host: 'example.com', hostname: 'example.com', pathname: '/', search: '', href: 'https://example.com/' },
    addEventListener() {},
    referrer: '',
    cookie: '',
  },
};
// BuggyTracker references `document` as a bare global
sandbox.self = sandbox;
vm.createContext(sandbox);
vm.runInContext(src + '\nthis.cyrb53 = cyrb53;\n', sandbox);

const { cyrb53 } = sandbox;

describe('cyrb53', () => {
  it('returns a number', () => {
    assert.equal(typeof cyrb53('hello'), 'number');
  });

  it('is deterministic (same input gives same output)', () => {
    const a = cyrb53('test string');
    const b = cyrb53('test string');
    assert.equal(a, b);
  });

  it('produces different hashes for different inputs', () => {
    const a = cyrb53('hello');
    const b = cyrb53('world');
    assert.notEqual(a, b);
  });

  it('handles empty string', () => {
    const h = cyrb53('');
    assert.equal(typeof h, 'number');
    assert.ok(Number.isFinite(h));
  });

  it('handles unicode strings', () => {
    const h = cyrb53('āgama nibbāna');
    assert.equal(typeof h, 'number');
    assert.ok(Number.isFinite(h));
  });

  it('returns non-negative values', () => {
    for (const s of ['a', 'bb', 'ccc', '', 'test123']) {
      assert.ok(cyrb53(s) >= 0, `Expected non-negative hash for "${s}"`);
    }
  });
});
