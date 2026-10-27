'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createDOMTranslator, safeText } = require('../../localization_runtime/dom.js');

class Element {
  constructor(tag, attrs = {}, classes = []) { this.nodeType = 1; this.tagName = tag; this.attrs = attrs; this.classes = classes; this.childNodes = []; this.parentElement = null; this.isConnected = true; }
  append(node) { node.parentElement = this; node.doc = this.doc; this.childNodes.push(node); return node; }
  getRootNode() { return this.doc; }
  matches(selector) {
    return selector.split(',').some(s => {
      s = s.trim();
      if (s.startsWith('.')) return this.classes.includes(s.slice(1));
      if (s.startsWith('[')) { const match = s.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/); return match && Object.hasOwn(this.attrs, match[1]) && (match[2] === undefined || this.attrs[match[1]] === match[2]); }
      return this.tagName.toLowerCase() === s.toLowerCase();
    });
  }
  closest(selector) { for (let node = this; node; node = node.parentElement) if (node.matches(selector)) return node; return null; }
  getAttribute(key) { return this.attrs[key] || null; }
  setAttribute(key, value) { this.attrs[key] = value; }
}
class Text {
  constructor(value) { this.nodeType = 3; this.textContent = value; this.isConnected = true; }
  getRootNode() { return this.doc; }
}
function fixture(extra = {}) {
  const doc = {}; doc.body = new Element('body'); doc.body.doc = doc;
  const control = doc.body.append(new Element('button', {}, ['verified-label']));
  const text = control.append(new Text('Unknown action'));
  let snapshot = { enabled: true, configRevision: 1, dictionaryRevision: 0, cacheEpoch: 0, pageEpoch: 0, entries: {} };
  const calls = []; const resolvers = [];
  const bridge = { translate(request) { calls.push(request); return new Promise(resolve => resolvers.push(resolve)); } };
  const timers = { setTimeout() { return 1; }, clearTimeout() {} };
  const options = { document: doc, timers, bridge, getSnapshot: () => snapshot,
    policy: { verified: true, rules: [{ selector: '.verified-label', contextKind: 'button', text: true, attributes: ['title', 'aria-label'] }] }, ...extra };
  const translator = createDOMTranslator(options);
  function respond(index = 0, overrides = {}) { const request = calls[index]; resolvers[index]({ ...request, translations: request.items.map(item => ({ id: item.id, text: '未知操作' })), ...overrides }); }
  return { doc, control, text, translator, calls, respond, get snapshot() { return snapshot; }, set snapshot(v) { snapshot = v; } };
}

test('safeText rejects private-looking, code, multiline, Chinese and long input', () => {
  for (const text of ['', '123', '你好', 'user@example.com', 'https://example.com', '/home/user', 'C:\\Users\\me', 'sk-secret', 'Bearer abc', 'some_variable', '<html>', 'foo\nbar', 'A'.repeat(161)]) assert.equal(safeText(text), false, text);
  assert.equal(safeText('  Unknown action  '), true);
});
test('empty or unverified policy sends nothing', async () => {
  for (const policy of [{}, { verified: false, rules: [{ selector: 'button', text: true }] }, { verified: true, rules: [] }]) {
    const f = fixture({ policy }); f.translator.start(); await f.translator.flush(); assert.equal(f.calls.length, 0);
  }
});
test('explicit verified label translates plain text and preserves whitespace', async () => {
  const f = fixture(); f.text.textContent = '  Unknown action  '; f.translator.start(); const pending = f.translator.flush();
  assert.equal(f.calls[0].items[0].text, 'Unknown action'); f.respond(); await pending;
  assert.equal(f.text.textContent, '  未知操作  ');
  f.translator.scan(f.doc.body); await f.translator.flush(); assert.equal(f.calls.length, 1);
});
test('existing dictionary or partial rule match prevents AI', async () => {
  const f = fixture({ syncTranslate: () => ({ matched: true, value: '已翻译 action' }) });
  f.translator.start(); await f.translator.flush(); assert.equal(f.text.textContent, '已翻译 action'); assert.equal(f.calls.length, 0);
});
test('personal dictionary works with AI off and never overrides builtin', async () => {
  const f = fixture(); f.snapshot = { ...f.snapshot, enabled: false, entries: { 'Unknown action': '个人翻译' } };
  f.translator.start(); await f.translator.flush(); assert.equal(f.text.textContent, '个人翻译'); assert.equal(f.calls.length, 0);
  const g = fixture({ syncTranslate: () => ({ matched: true, value: '内置翻译' }) }); g.snapshot.entries = { 'Unknown action': '个人翻译' }; g.translator.start(); assert.equal(g.text.textContent, '内置翻译');
});
test('excluded ancestor trees send no text including nested safe-looking buttons', async () => {
  for (const attrs of [{ contenteditable: 'true' }, { 'data-user-content': '' }, { 'data-user-name': '' }, { role: 'log' }, { 'data-artifact-content': '' }]) {
    const f = fixture(); f.doc.body.attrs = attrs; f.translator.start(); await f.translator.flush(); assert.equal(f.calls.length, 0);
  }
  for (const cls of ['monaco-editor', 'chat', 'conversation', 'thinking', 'terminal', 'diff', 'logs', 'reasoning', 'cm-editor']) {
    const f = fixture(); f.doc.body.classes = [cls]; f.translator.start(); await f.translator.flush(); assert.equal(f.calls.length, 0, cls);
  }
});
test('input values, placeholders and shadow roots are not collected', async () => {
  const f = fixture(); f.control.tagName = 'input'; f.control.attrs.placeholder = 'Sensitive name'; f.control.value = 'Secret'; f.translator.start(); await f.translator.flush(); assert.equal(f.calls.length, 0);
  const g = fixture(); g.text.doc = {}; g.translator.start(); await g.translator.flush(); assert.equal(g.calls.length, 0);
});
test('unapproved attributes and buttons are not eligible', async () => {
  const f = fixture(); f.control.classes = []; f.control.attrs.title = 'Unknown action'; f.translator.start(); await f.translator.flush(); assert.equal(f.calls.length, 0);
});
test('approved attributes translate while value remains untouched', async () => {
  const f = fixture(); f.text.textContent = ''; f.control.attrs.title = 'Unknown action'; f.control.value = 'Private text'; f.translator.start(); const pending = f.translator.flush(); f.respond(); await pending; assert.equal(f.control.attrs.title, '未知操作'); assert.equal(f.control.value, 'Private text');
});
test('same text/context deduplicates across nodes', async () => {
  const f = fixture(); const second = f.control.append(new Text('Unknown action')); f.translator.start(); const pending = f.translator.flush(); assert.equal(f.calls[0].items.length, 1); f.respond(); await pending; assert.equal(second.textContent, '未知操作');
});
test('node changed or removed while response pending is never overwritten', async () => {
  for (const change of [f => { f.text.textContent = 'New label'; }, f => { f.text.isConnected = false; }, f => { f.control.classes.push('chat'); }]) {
    const f = fixture(); f.translator.start(); const pending = f.translator.flush(); change(f); const before = f.text.textContent; f.respond(); await pending; assert.equal(f.text.textContent, before);
  }
});
test('config, dictionary, page and cache version changes discard stale replies', async () => {
  for (const key of ['configRevision', 'dictionaryRevision', 'pageEpoch', 'cacheEpoch']) {
    const f = fixture(); f.translator.start(); const pending = f.translator.flush(); f.snapshot = { ...f.snapshot, [key]: 2 }; f.respond(); await pending; assert.equal(f.text.textContent, 'Unknown action', key);
  }
});
test('disabling prevents old response and restores already translated text', async () => {
  const f = fixture(); f.translator.start(); const pending = f.translator.flush(); f.snapshot = { ...f.snapshot, enabled: false }; f.translator.refresh(); f.respond(); await pending; assert.equal(f.text.textContent, 'Unknown action');
  const g = fixture(); g.translator.start(); const p = g.translator.flush(); g.respond(); await p; g.snapshot = { ...g.snapshot, enabled: false }; g.translator.refresh(); assert.equal(g.text.textContent, 'Unknown action');
});
test('personal dictionary edit/deletion updates currently translated nodes', async () => {
  const f = fixture(); f.snapshot = { ...f.snapshot, enabled: false, entries: { 'Unknown action': '旧翻译' } }; f.translator.start();
  f.snapshot = { ...f.snapshot, dictionaryRevision: 1, entries: { 'Unknown action': '新翻译' } }; f.translator.refresh(); assert.equal(f.text.textContent, '新翻译');
  f.snapshot = { ...f.snapshot, dictionaryRevision: 2, entries: {} }; f.translator.refresh(); assert.equal(f.text.textContent, 'Unknown action');
});
test('malformed, HTML or mismatched revisions never write', async () => {
  for (const override of [{ translations: [] }, { configRevision: 9 }, { translations: [{ id: '1', text: '<b>翻译</b>' }] }, { translations: [{ id: 'wrong', text: '翻译' }] }]) {
    const f = fixture(); f.translator.start(); const p = f.translator.flush(); f.respond(0, override); await p; assert.equal(f.text.textContent, 'Unknown action'); f.translator.scan(f.doc.body); await f.translator.flush(); assert.equal(f.calls.length, 1);
  }
});
test('stop cancels pending work without DOM writes', async () => {
  const f = fixture(); f.translator.start(); const p = f.translator.flush(); f.translator.stop(); f.respond(); await p; assert.equal(f.text.textContent, 'Unknown action');
});
test('observer limits attribute monitoring and disconnects', () => {
  let observed, disconnected = false;
  class Observer { constructor(callback) { this.callback = callback; } observe(node, options) { observed = options; } disconnect() { disconnected = true; } }
  const f = fixture({ MutationObserver: Observer }); f.translator.start(); assert.deepEqual(observed.attributeFilter, ['title', 'placeholder', 'aria-label']); f.translator.stop(); assert.equal(disconnected, true);
});
test('placeholder loss is rejected and placeholders preserved are accepted', async () => {
  const f = fixture(); f.text.textContent = 'Open {count} items'; f.translator.start(); const pending = f.translator.flush(); f.respond(); await pending; assert.equal(f.text.textContent, 'Open {count} items');
  const g = fixture(); g.text.textContent = 'Open {count} items'; g.translator.start(); const p = g.translator.flush(); g.respond(0, { translations: [{ id: '1', text: '打开 {count} 个项目' }] }); await p; assert.equal(g.text.textContent, '打开 {count} 个项目');
});
test('observer invalidates ABA text mutation before delayed reply', async () => {
  let observer;
  class Observer { constructor(callback) { this.callback = callback; observer = this; } observe() {} disconnect() {} }
  const f = fixture({ MutationObserver: Observer }); f.translator.start(); const pending = f.translator.flush();
  observer.callback([{ type: 'characterData', target: f.text }]);
  // The original waiter is invalid, but the newly scanned identical label is
  // explicitly registered at the new generation and may use a shared request.
  f.text.textContent = 'A newer label'; f.respond(); await pending; assert.equal(f.text.textContent, 'A newer label');
});
test('responses with duplicate identifiers fail closed', async () => {
  const f = fixture(); f.control.append(new Text('Other action')); f.translator.start(); const p = f.translator.flush();
  f.respond(0, { translations: [{ id: '1', text: '翻译' }, { id: '1', text: '翻译' }] }); await p; assert.equal(f.text.textContent, 'Unknown action');
});
test('removed subtree prunes retained slots and queued requests without config changes', async () => {
  let observer;
  class Observer { constructor(callback) { observer = this; this.callback = callback; } observe() {} disconnect() {} }
  const f = fixture({ MutationObserver: Observer }); f.translator.start(); assert.equal(f.translator.getStats().trackedSlots, 1);
  f.text.isConnected = false; f.control.isConnected = false;
  observer.callback([{ type: 'childList', removedNodes: [f.control], addedNodes: [] }]);
  assert.deepEqual(f.translator.getStats(), { trackedSlots: 0, queuedTasks: 0, inflightTasks: 0, pendingWaiters: 0 });
  await f.translator.flush(); assert.equal(f.calls.length, 0);
});
test('many unique safe labels have bounded retained slots and queue', () => {
  const f = fixture();
  for (let i = 0; i < 3000; i++) f.control.append(new Text('Fixture label ' + i));
  f.translator.start(); const stats = f.translator.getStats();
  assert.equal(stats.trackedSlots, 2048); assert.equal(stats.queuedTasks, 256); assert.equal(stats.pendingWaiters, 256);
  f.translator.stop(); assert.equal(f.translator.getStats().trackedSlots, 0);
});
test('repeated mutations of one slot replace waiter instead of accumulating references', () => {
  let observer;
  class Observer { constructor(callback) { observer = this; this.callback = callback; } observe() {} disconnect() {} }
  const f = fixture({ MutationObserver: Observer }); f.translator.start();
  for (let i = 0; i < 1000; i++) observer.callback([{ type: 'characterData', target: f.text }]);
  assert.equal(f.translator.getStats().pendingWaiters, 1);
});
test('inflight removed nodes are detached from pending waiter records', async () => {
  let observer;
  class Observer { constructor(callback) { observer = this; this.callback = callback; } observe() {} disconnect() {} }
  const f = fixture({ MutationObserver: Observer }); f.translator.start(); const pending = f.translator.flush();
  f.text.isConnected = false; observer.callback([{ type: 'childList', removedNodes: [f.text], addedNodes: [] }]);
  assert.equal(f.translator.getStats().pendingWaiters, 0); assert.equal(f.translator.getStats().trackedSlots, 0);
  f.respond(); await pending; assert.equal(f.text.textContent, 'Unknown action');
});
test('valid partial successes apply while missing IDs retain English with cooldown', async () => {
  const f = fixture(); const second = f.control.append(new Text('Other action'));
  f.translator.start(); const pending = f.translator.flush();
  f.respond(0, { translations: [{ id: '1', text: '成功翻译' }] }); await pending;
  assert.equal(f.text.textContent, '成功翻译'); assert.equal(second.textContent, 'Other action');
  f.translator.scan(f.doc.body); await f.translator.flush(); assert.equal(f.calls.length, 1);
});
test('queued text moved into excluded content never crosses IPC', async () => {
  const f = fixture(); f.translator.start(); f.control.classes.push('chat'); await f.translator.flush();
  assert.equal(f.calls.length, 0); assert.equal(f.translator.getStats().queuedTasks, 0);
});
test('queued changed or stale-generation text never crosses IPC', async () => {
  const f = fixture(); f.translator.start(); f.text.textContent = 'Secret private user text'; await f.translator.flush(); assert.equal(f.calls.length, 0);
  const g = fixture(); g.translator.start(); g.control.classes = []; await g.translator.flush(); assert.equal(g.calls.length, 0);
});
