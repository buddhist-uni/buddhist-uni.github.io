const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const read = (file) => fs.readFileSync(path.join(__dirname, '..', file), 'utf-8');

// Runs search.js against stub elements and a Worker that records its messages
function loadSearchPage(search = '') {
  const posted = [];
  const element = () => ({ style: {}, setAttribute() {}, addEventListener(type, fn) { this[type] = fn; }, blur() {}, focus() {} });
  const elements = { 'search-box': Object.assign(element(), { value: '' }) };
  const sandbox = {
    document: { getElementById: (id) => elements[id] ??= element() },
    location: { search, href: '' },
    history: { replaceState() {} },
    performance: { now: () => 0 },
    setTimeout() {},
    clearTimeout() {},
    Worker: function () { this.postMessage = (message) => posted.push(message); },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(read('utils.js') + read('search.js'), sandbox);
  return {
    posted,
    type(value) {
      const box = elements['search-box'];
      box.value = value;
      box.input({ target: box });
    },
  };
}

describe('search page', () => {
  it('sends the worker the query as typed', () => {
    const page = loadSearchPage();
    page.type('"noble truths"');
    assert.deepEqual(Object.keys(page.posted[0]), ['q', 'filterquery', 'qt']);
    assert.equal(page.posted[0].q, '"noble truths"');
  });

  it('sends the worker the query from the URL as given', () => {
    const page = loadSearchPage('?q=%E2%80%9Cnoble+truths%E2%80%9D');
    assert.deepEqual(Object.keys(page.posted[0]), ['q', 'filterquery', 'qt']);
    assert.equal(page.posted[0].q, '“noble truths”');
  });

  it('does not send a query that is too short once sanitized', () => {
    const page = loadSearchPage();
    page.type('"ab"');
    assert.equal(page.posted.length, 0);
  });
});
