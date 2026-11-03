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
  let snapshot = { enabled: true, configRevision: 1, dictionaryRevision: 0, candidatesRevision: 0, cacheEpoch: 0, pageEpoch: 0, entries: {}, candidates: {}, rejected: {} };
  const calls = []; const resolvers = [];
  const bridge = { translate(request) { calls.push(request); return new Promise(resolve => resolvers.push(resolve)); } };
  const timers = { setTimeout() { return 1; }, clearTimeout() {} };
  const options = { document: doc, timers, bridge, getSnapshot: () => snapshot,
    policy: { verified: true, rules: [{ selector: '.verified-label', contextKind: 'button', text: true, attributes: ['title', 'aria-label'] }] }, ...extra };
  const translator = createDOMTranslator(options);
  function respond(index = 0, overrides = {}) { const request = calls[index]; const response = { ...request, translations: request.items.map(item => ({ id: item.id, text: '未知操作' })), ...overrides };
    if (Array.isArray(response.translations)) response.translations = response.translations.map(row => ({ source: 'candidate', expiresAt: (extra.clock || Date.now)() + 604800000, ...row }));
    resolvers[index](response); }
  return { doc, control, text, translator, calls, respond, get snapshot() { return snapshot; }, set snapshot(v) { snapshot = v; } };
}

function trapContent(f, { text = true, attributes = true } = {}) {
  const attempts = { text: 0, attributes: 0, writes: 0 };
  if (text) Object.defineProperty(f.text, 'textContent', {
    configurable: true,
    get() { attempts.text++; throw new Error('unauthorized text read'); },
    set() { attempts.writes++; }
  });
  if (attributes) for (const element of [f.doc.body, f.control]) {
    element.getAttribute = () => { attempts.attributes++; throw new Error('unauthorized attribute read'); };
    element.setAttribute = () => { attempts.writes++; };
  }
  return attempts;
}

function restrictedPolicy() {
  return { verified: true, paths: ['/'], rules: [{ selector: '.verified-label', contextKind: 'button',
    text: true, attributes: ['title'], sourceTexts: ['Unknown action'] }] };
}

test('safeText rejects private-looking, code, multiline, Chinese and long input', () => {
  for (const text of ['', '123', '你好', 'user@example.com', 'https://example.com', '/home/user', 'C:\\Users\\me', 'sk-secret', 'Bearer abc', 'some_variable', '<html>', 'foo\nbar', 'A'.repeat(161)]) assert.equal(safeText(text), false, text);
  assert.equal(safeText('  Unknown action  '), true);
});

test('reviewed route and exact source constraints reject unrelated page text', async () => {
  const policy = {verified:true, paths:['/onboarding'], rules:[{selector:'button',contextKind:'button',text:true,sourceTexts:['Unknown action']}]};
  for (const location of [{pathname:'/'},{pathname:'/onboarding',search:'?private=1'},{pathname:'/onboarding',hash:'#other'}]) {
    const f=fixture({policy}); f.doc.location=location; f.translator.start(); await f.translator.flush(); assert.equal(f.calls.length,0);
  }
  const f=fixture({policy}); f.doc.location={pathname:'/onboarding'}; f.text.textContent='User supplied label';
  f.translator.start(); await f.translator.flush(); assert.equal(f.calls.length,0);
  f.text.textContent='Unknown action'; f.translator.scan(f.doc.body); const pending=f.translator.flush();
  assert.equal(f.calls.length,1); f.respond(); await pending; assert.equal(f.text.textContent,'未知操作');
  f.translator.scan(f.doc.body); await f.translator.flush(); assert.equal(f.calls.length,1);
});
test('text source checks never read outside selectors, permitted routes or exclusion boundaries', async () => {
  for (const deny of [f => { f.control.classes = []; }, f => { f.doc.location.search = '?private=1'; },
    f => { f.doc.location.hash = '#private'; }, f => { f.doc.location.pathname = '/other'; },
    f => { f.control.classes.push('chat'); }, f => { f.doc.body.attrs['data-user-content'] = ''; }]) {
    const f = fixture({ policy: restrictedPolicy() }); f.doc.location = { pathname: '/' }; deny(f);
    const attempts = trapContent(f, { attributes: false });
    f.translator.start(); await f.translator.flush();
    assert.deepEqual(attempts, { text: 0, attributes: 0, writes: 0 }); assert.equal(f.calls.length, 0);
  }
});
test('scan never pre-reads attributes without an applicable attribute rule', async () => {
  for (const deny of [f => { f.control.classes = []; }, f => { f.doc.location.search = '?private=1'; },
    (_f, policy) => { delete policy.rules[0].attributes; }, (_f, policy) => { policy.rules.length = 0; },
    (_f, policy) => { policy.verified = false; }]) {
    const policy = restrictedPolicy(), f = fixture({ policy }); f.doc.location = { pathname: '/' };
    f.text.textContent = ''; deny(f, policy); const attempts = trapContent(f, { text: false });
    f.translator.start(); await f.translator.flush();
    assert.deepEqual(attempts, { text: 0, attributes: 0, writes: 0 }); assert.equal(f.calls.length, 0);
  }
});
test('exact source rules translate approved text and attributes without reading other attributes', async () => {
  const f = fixture({ policy: restrictedPolicy() }); f.doc.location = { pathname: '/' };
  f.control.attrs.title = 'Unknown action'; f.control.attrs.placeholder = 'Private placeholder';
  const readAttribute = f.control.getAttribute.bind(f.control), reads = [];
  f.control.getAttribute = name => { reads.push(name); assert.equal(name, 'title'); return readAttribute(name); };
  f.doc.body.getAttribute = () => assert.fail('body is outside the selector allowlist');
  f.translator.start(); const pending = f.translator.flush();
  assert.equal(f.calls[0].items.length, 1); f.respond(); await pending;
  assert.ok(reads.length > 0); assert.equal(f.text.textContent, '未知操作');
  assert.equal(f.control.attrs.title, '未知操作'); assert.equal(f.control.attrs.placeholder, 'Private placeholder');
});
test('queued and inflight text and attributes are not read after losing policy eligibility', async () => {
  for (const phase of ['queued', 'inflight']) for (const deny of [f => { f.control.classes = []; },
    f => { f.control.classes.push('chat'); }, f => { f.doc.location.search = '?private=1'; }]) {
    const f = fixture({ policy: restrictedPolicy() }); f.doc.location = { pathname: '/' };
    f.control.attrs.title = 'Unknown action'; f.translator.start();
    const pending = phase === 'inflight' ? f.translator.flush() : null;
    deny(f); const attempts = trapContent(f);
    if (pending) { f.respond(); await pending; } else await f.translator.flush();
    assert.deepEqual(attempts, { text: 0, attributes: 0, writes: 0 });
    assert.equal(f.calls.length, phase === 'inflight' ? 1 : 0); assert.equal(f.translator.getStats().pendingWaiters, 0);
  }
});
test('mutation bookkeeping does not read translated slots after they leave the policy boundary', async () => {
  let observer;
  class Observer { constructor(callback) { observer = this; this.callback = callback; } observe() {} disconnect() {} }
  const f = fixture({ policy: restrictedPolicy(), MutationObserver: Observer }); f.doc.location = { pathname: '/' };
  f.control.attrs.title = 'Unknown action'; f.translator.start(); const pending = f.translator.flush(); f.respond(); await pending;
  f.control.classes = []; const attempts = trapContent(f);
  observer.callback([{ type: 'characterData', target: f.text }, { type: 'attributes', target: f.control, attributeName: 'title' }]);
  assert.deepEqual(attempts, { text: 0, attributes: 0, writes: 0 }); assert.equal(f.calls.length, 1);
});
test('refresh restores only previously displayed slots even after the route becomes forbidden', async () => {
  const f = fixture({ policy: restrictedPolicy() }); f.doc.location = { pathname: '/' };
  f.control.attrs.title = 'Unknown action'; f.translator.start(); const pending = f.translator.flush(); f.respond(); await pending;
  f.doc.location.search = '?private=1'; f.snapshot = { ...f.snapshot, enabled: false };
  let reads = 0, displayed = f.text.textContent;
  Object.defineProperty(f.text, 'textContent', { get() { reads++; return displayed; }, set(value) { displayed = value; } });
  const readAttribute = f.control.getAttribute.bind(f.control);
  f.control.getAttribute = name => { reads++; assert.equal(name, 'title'); return readAttribute(name); };
  f.doc.body.getAttribute = () => assert.fail('restoration must not scan unrelated attributes');
  f.translator.refresh();
  assert.equal(reads, 2); assert.equal(displayed, 'Unknown action'); assert.equal(f.control.attrs.title, 'Unknown action');
  assert.equal(f.calls.length, 1);
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
test('personal dictionary works with AI off and overrides builtin', async () => {
  const f = fixture(); f.snapshot = { ...f.snapshot, enabled: false, entries: { 'Unknown action': '个人翻译' } };
  f.translator.start(); await f.translator.flush(); assert.equal(f.text.textContent, '个人翻译'); assert.equal(f.calls.length, 0);
  const g = fixture({ syncTranslate: () => ({ matched: true, value: '内置翻译' }) }); g.snapshot.entries = { 'Unknown action': '个人翻译' }; g.translator.start(); assert.equal(g.text.textContent, '个人翻译');
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
  for (const key of ['configRevision', 'dictionaryRevision', 'candidatesRevision', 'pageEpoch', 'cacheEpoch']) {
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

function pendingCandidate(translation = '候选译文', createdAt = 1000) {
  return { source: 'ai', translation, createdAt, expiresAt: createdAt + 604800000 };
}
test('candidate tier follows personal and builtin tiers and works with AI disabled', async () => {
  for (const level of ['personal', 'builtin', 'candidate']) {
    const f = fixture({ clock: () => 2000, syncTranslate: value => ({ matched: level !== 'candidate', value: '内置翻译' }) });
    f.snapshot = { ...f.snapshot, enabled: false, candidates: { 'Unknown action': pendingCandidate() }, entries: level === 'personal' ? { 'Unknown action': '个人翻译' } : {} };
    f.translator.start(); await f.translator.flush();
    assert.equal(f.text.textContent, {personal:'个人翻译', builtin:'内置翻译', candidate:'候选译文'}[level]); assert.equal(f.calls.length, 0);
  }
});
test('candidate expiry timer restores displayed text at the fixed deadline without snapshot polling', async () => {
  let now = 2000, id = 0; const scheduled = new Map();
  const timers = {setTimeout(callback, delay) { scheduled.set(++id, {callback, due: now + delay}); return id; }, clearTimeout(handle) { scheduled.delete(handle); }};
  const f = fixture({ clock: () => now, timers }); f.snapshot = { ...f.snapshot, enabled: false, candidates: { 'Unknown action': pendingCandidate() } };
  f.translator.start(); assert.equal(f.text.textContent, '候选译文');
  const deadline = 604801000; assert.equal([...scheduled.values()][0].due, deadline);
  now += 1000; f.translator.scan(f.doc.body); assert.equal([...scheduled.values()][0].due, deadline);
  now = deadline; for (const [key, timer] of [...scheduled]) if (timer.due <= now) { scheduled.delete(key); timer.callback(); }
  assert.equal(f.text.textContent, 'Unknown action'); assert.equal(scheduled.size, 0); assert.equal(f.calls.length, 0); f.translator.stop();
});
test('candidate revision immediately restores and applies adoption, edit, rejection and unblock', async () => {
  const f = fixture({ clock: () => 2000 }); f.snapshot = { ...f.snapshot, enabled: false, candidates: { 'Unknown action': pendingCandidate() } };
  f.translator.start(); assert.equal(f.text.textContent, '候选译文');
  f.snapshot = { ...f.snapshot, dictionaryRevision: 1, candidatesRevision: 1, candidates: {}, entries: { 'Unknown action': '采纳译文' } };
  f.translator.refresh(); assert.equal(f.text.textContent, '采纳译文');
  f.snapshot = { ...f.snapshot, dictionaryRevision: 2, entries: { 'Unknown action': '编辑译文' } };
  f.translator.refresh(); assert.equal(f.text.textContent, '编辑译文');
  f.snapshot = { ...f.snapshot, enabled: true, dictionaryRevision: 3, candidatesRevision: 2, entries: {}, rejected: { 'Unknown action': true } };
  f.translator.refresh(); await f.translator.flush(); assert.equal(f.text.textContent, 'Unknown action'); assert.equal(f.calls.length, 0);
  f.snapshot = { ...f.snapshot, candidatesRevision: 3, rejected: {} }; f.translator.refresh(); const pending = f.translator.flush();
  assert.equal(f.calls.length, 1); f.respond(); await pending; assert.equal(f.text.textContent, '未知操作');
});
test('invalid or expired candidates are never displayed and rejection suppresses new work', async () => {
  for (const row of [pendingCandidate('候选译文', 0), {...pendingCandidate(), expiresAt: 99999999999}, {...pendingCandidate(), source: 'manual'}]) {
    const f = fixture({clock:()=>604800000}); f.snapshot = {...f.snapshot, enabled:false, candidates:{'Unknown action':row}};
    f.translator.start(); assert.equal(f.text.textContent,'Unknown action'); assert.equal(f.calls.length,0);
  }
  const f=fixture({clock:()=>2000}); f.snapshot={...f.snapshot,candidates:{'Unknown action':pendingCandidate()},rejected:{'Unknown action':true}};
  f.translator.start(); await f.translator.flush(); assert.equal(f.text.textContent,'Unknown action'); assert.equal(f.calls.length,0);
});
test('expired, unknown-source and post-rejection replies cannot overwrite original text', async () => {
  for (const row of [{source:'candidate',expiresAt:1000},{source:'ai',expiresAt:999999},{source:'personal',expiresAt:999999}]) {
    const f=fixture({clock:()=>1000}); f.translator.start();const pending=f.translator.flush();f.respond(0,{translations:[{id:'1',text:'失效译文',...row}]});await pending;assert.equal(f.text.textContent,'Unknown action');
  }
  const f=fixture();f.translator.start();const pending=f.translator.flush();f.snapshot={...f.snapshot,candidatesRevision:1,rejected:{'Unknown action':true}};f.translator.refresh();f.respond();await pending;assert.equal(f.text.textContent,'Unknown action');
});
