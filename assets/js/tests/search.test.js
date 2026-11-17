const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const read = (file) => fs.readFileSync(path.join(__dirname, '..', file), 'utf-8');

// Runs search.js against stub elements, timers and history, and a Worker that records its messages
function loadSearchPage(search = '') {
  const posted = [], pushed = [], replaced = [], searched = [], timers = [];
  const element = () => ({ value: '', style: {}, setAttribute(name, value) { this[name] = value; }, addEventListener(type, fn) { this[type] = fn; }, blur() {}, focus() {} });
  const elements = {};
  const sandbox = {
    document: { title: 'Search', getElementById: (id) => elements[id] ??= element() },
    location: { search, href: '' },
    history: { replaceState(state, unused, url) { replaced.push(url); }, pushState(state, unused, url) { pushed.push(url); } },
    gtag(type, name, params) { searched.push(params.search_term); },
    performance: { now: () => 0 },
    setTimeout(fn) { timers.push(fn); },
    clearTimeout() {},
    Worker: function () { this.postMessage = (message) => posted.push(message); },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(read('utils.js') + read('search.js'), sandbox);
  const box = elements['search-box'];
  return {
    posted,
    pushed,
    replaced,
    searched,
    box,
    title: () => sandbox.document.title,
    type(value) {
      box.value = value;
      box.input({ target: box });
    },
    reply(q, filterquery = '') {
      sandbox.search_worker.onmessage({ data: { q, filterquery, warninghtml: '', html: '' } });
    },
    back(q) {
      sandbox.onpopstate({ state: { q, html: '<li></li>' } });
    },
    runTimers() {
      timers.splice(0).forEach((fn) => fn());
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
    assert.equal(page.posted[0].q, '“noble truths”');
    assert.equal(page.box.value, '“noble truths”');
  });

  it('does not send a query that is too short once sanitized', () => {
    const page = loadSearchPage();
    page.type('"ab"');
    assert.equal(page.posted.length, 0);
    assert.equal(loadSearchPage('?q=%22ab%22').posted.length, 0);
  });

  it('registers a reply to the query as typed', () => {
    const page = loadSearchPage();
    page.type('"noble truths"');
    page.reply('"noble truths"');
    page.runTimers();
    assert.deepEqual(page.pushed, ['?q=%22noble%20truths%22']);
    assert.equal(page.title(), '"noble truths" | Search');
    assert.deepEqual(page.searched, ['noble truths']);
  });

  it('replaces the entry when only punctuation changes', () => {
    const page = loadSearchPage('?q=noble+truths');
    page.reply('noble truths');
    page.runTimers();
    page.type('"noble truths"');
    page.reply('"noble truths"');
    page.runTimers();
    assert.equal(page.replaced.at(-1), '?q=%22noble%20truths%22');
    assert.deepEqual(page.pushed, []);
    assert.deepEqual(page.searched, []);
  });

  it('ignores a reply for another filter', () => {
    const page = loadSearchPage();
    page.type('noble truths');
    page.reply('noble truths', '+in:canon');
    page.runTimers();
    assert.deepEqual(page.pushed, []);
  });

  it('ignores a reply once the box holds something else', () => {
    const page = loadSearchPage();
    page.type('noble truths');
    page.reply('noble truths');
    page.back('"noble truths"');
    page.runTimers();
    assert.equal(page.box.value, '"noble truths"');
    assert.equal(page.title(), '"noble truths" | Search');
    assert.deepEqual(page.pushed, []);
  });
});
