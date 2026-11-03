'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const ROOT = path.resolve(__dirname, '../..');
// Generate actual production preload bytes, not a hand-maintained copy.
const generated = JSON.parse(execFileSync(process.env.PYTHON || 'python', ['-X', 'utf8', '-B', '-c', `
import copy, importlib.util, json
from translation_integration import preload_extension
spec = importlib.util.spec_from_file_location('patcher', 'Antigravity-Patcher.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
profile = {'policy': {'verified': True, 'rules': [{'selector': '.fixture-static-label', 'contextKind': 'button', 'text': True, 'attributes': ['title']}]}}
restricted = copy.deepcopy(profile)
restricted['windowBinding'] = {'kind': 'antigravity-local-hub-v1', 'paths': ['/onboarding']}
restricted['policy']['paths'] = ['/onboarding']
restricted['policy']['rules'][0]['sourceTexts'] = ['Save', 'Wonderful fixture action']
root_restricted = copy.deepcopy(restricted)
root_restricted['windowBinding']['paths'] = ['/']
root_restricted['policy']['paths'] = ['/']
print(json.dumps({'static': p.build_dom_injection(profile), 'dynamic': p.build_dom_injection(restricted),
                 'dynamicRoot': p.build_dom_injection(root_restricted)}))
`], { cwd: path.join(ROOT, 'src', 'localization'), encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } }));
class Element {
  constructor(tag, classes = []) { this.nodeType = 1; this.tagName = tag.toUpperCase(); this.classes = classes; this.childNodes = []; this.attrs = {}; this.isConnected = true; this.textContent = ''; }
  append(node) { node.parentElement = this; node.doc = this.doc; this.childNodes.push(node); return node; }
  getRootNode() { return this.doc; }
  matches(selector) {
    return selector.split(',').some(s => {
      s = s.trim();
      if (s.startsWith('.')) return this.classes.includes(s.slice(1));
      if (s.startsWith('[')) { const m = s.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/); return m && Object.hasOwn(this.attrs, m[1]) && (m[2] === undefined || this.attrs[m[1]] === m[2]); }
      return s.toUpperCase() === this.tagName;
    });
  }
  closest(selector) { for (let p = this; p; p = p.parentElement) if (p.matches(selector)) return p; return null; }
  getAttribute(k) { return this.attrs[k] || null; }
  setAttribute(k, value) { this.attrs[k] = value; }
  querySelector() { return null; }
}
class Text {
  constructor(text) { this.nodeType = 3; this.textContent = text; this.isConnected = true; }
  getRootNode() { return this.doc; }
}
async function tick() { await new Promise(resolve => setImmediate(resolve)); }
function setup(initial = {}, options = {}) {
  const documentEvents = new Map(), windowEvents = new Map();
  const document = { readyState: 'loading', location: options.location || {pathname: '/', search: '', hash: ''}, addEventListener(name, callback) { const list = documentEvents.get(name) || []; list.push(callback); documentEvents.set(name, list); } };
  document.body = new Element('body'); document.body.doc = document;
  const add = value => document.body.append(new Element('button', ['fixture-static-label'])).append(new Text(value));
  const builtin = add('Save'), unknown = add(options.unknownText || 'Wonderful fixture action');
  const outside = document.body.append(new Element('button')).append(new Text('Save'));
  const privateText = document.body.append(new Element('section', ['chat']))
    .append(new Element('button', ['fixture-static-label'])).append(new Text('Save'));
  const calls = [], intervals = new Map(), timeouts = new Map(), observers = new Set(); let id = 0;
  let snapshot = { version: 1, enabled: true, configRevision: 1, dictionaryRevision: 0, cacheEpoch: 0, pageEpoch: 1, entries: {}, ...initial };
  const context = {
    document, Node: { TEXT_NODE: 3, ELEMENT_NODE: 1 }, AbortController,
    window: { addEventListener(name, callback) { windowEvents.set(name, callback); } },
    MutationObserver: class {
      constructor(callback) { this.callback = callback; }
      observe() { observers.add(this); }
      disconnect() { observers.delete(this); }
    },
    setInterval(fn) { intervals.set(++id, fn); return id; }, clearInterval(key) { intervals.delete(key); },
    setTimeout(fn) {
      if (options.strictTimers && this && this !== context) throw new TypeError('Illegal invocation');
      timeouts.set(++id, fn); return id;
    }, clearTimeout(key) {
      if (options.strictTimers && this && this !== context) throw new TypeError('Illegal invocation');
      timeouts.delete(key);
    },
    require(name) { assert.equal(name, 'electron'); return { ipcRenderer: { async invoke(channel, request) {
      calls.push({ channel, request });
      if (channel === 'dragongirl:v1:snapshot') return snapshot;
      assert.equal(channel, 'dragongirl:v1:translate');
      return { version: 1, configRevision: request.configRevision, dictionaryRevision: request.dictionaryRevision, cacheEpoch: request.cacheEpoch, status: 'ok', translations: request.items.map(item => ({ id: item.id, text: '精彩测试操作' })) };
    } } }; },
  };
  const keys = Object.keys(context).sort();
  vm.runInNewContext(options.dynamicRoot ? generated.dynamicRoot : options.dynamic ? generated.dynamic : generated.static, context, { filename: 'generated-verified-preload.js', timeout: 2000 });
  for (const callback of documentEvents.get('DOMContentLoaded') || []) callback();
  async function drain() { await tick(); for (const [key, callback] of [...timeouts]) { timeouts.delete(key); callback(); } await tick(); }
  async function refresh(next) { snapshot = next; for (const callback of intervals.values()) callback(); await drain(); }
  function mutations(records) { for (const observer of [...observers]) observer.callback(records); }
  return { context, builtin, unknown, outside, privateText, calls, drain, refresh, mutations, keys, intervals, windowEvents, get snapshot() { return snapshot; } };
}

test('generated full verified preload parses, translates static first, and stays private', async () => {
  const f = setup(); await f.drain();
  assert.equal(f.builtin.textContent, '保存'); assert.equal(f.unknown.textContent, '精彩测试操作');
  assert.deepEqual(Object.keys(f.context).sort(), f.keys);
  assert.equal(Object.hasOwn(f.context.window, 'ipcRenderer'), false);
  const snapshots = f.calls.filter(c => c.channel.endsWith(':snapshot')); assert.equal(snapshots[0].request.version, 1);
  const requests = f.calls.filter(c => c.channel.endsWith(':translate')); assert.equal(requests.length, 1);
  assert.equal(requests[0].request.items.length, 1); assert.equal(requests[0].request.items[0].text, 'Wonderful fixture action');
  assert.deepEqual(Object.keys(requests[0].request).sort(), ['cacheEpoch', 'configRevision', 'dictionaryRevision', 'items', 'version']);
});

test('generated preload supports browser timers that reject foreign receivers', async () => {
  const f = setup({}, {strictTimers: true}); await f.drain();
  assert.equal(f.unknown.textContent, '精彩测试操作');
  assert.equal(f.calls.filter(c => c.channel.endsWith(':translate')).length, 1);
  await f.refresh({...f.snapshot, enabled: false});
  assert.equal(f.unknown.textContent, 'Wonderful fixture action');
});
test('polling snapshot refresh updates personal dictionary with AI disabled', async () => {
  const f = setup({ enabled: false, entries: { 'Wonderful fixture action': '个人翻译' } }); await f.drain();
  assert.equal(f.unknown.textContent, '个人翻译'); assert.equal(f.calls.filter(c => c.channel.endsWith(':translate')).length, 0);
  await f.refresh({ ...f.snapshot, dictionaryRevision: 1, entries: { 'Wonderful fixture action': '新个人翻译' } }); assert.equal(f.unknown.textContent, '新个人翻译');
  await f.refresh({ ...f.snapshot, dictionaryRevision: 2, entries: {} }); assert.equal(f.unknown.textContent, 'Wonderful fixture action');
});
test('verified preload leaves builtin-looking text outside approved UI and inside chat untouched', async () => {
  const f = setup(); await f.drain();
  assert.equal(f.builtin.textContent, '保存');
  assert.equal(f.outside.textContent, 'Save');
  assert.equal(f.privateText.textContent, 'Save');
  const requested = f.calls.filter(c => c.channel.endsWith(':translate')).flatMap(c => c.request.items.map(i => i.text));
  assert.deepEqual(requested, ['Wonderful fixture action']);
});
test('pagehide disposes polling and prevents further work', async () => {
  const f = setup(); await f.drain(); f.windowEvents.get('pagehide')(); assert.equal(f.intervals.size, 0);
});
test('wrong snapshot protocol fails closed without remote translation', async () => {
  const f = setup({ version: 99 }); await f.drain();
  assert.equal(f.builtin.textContent, '保存'); assert.equal(f.unknown.textContent, 'Wonderful fixture action');
  assert.equal(f.calls.filter(c => c.channel.endsWith(':translate')).length, 0);
});

test('missing or invalid snapshot page epoch fails closed without remote translation', async () => {
  for (const pageEpoch of [undefined, null, 0, -1, 1.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1, '1']) {
    const f = setup({pageEpoch}); await f.drain();
    assert.equal(f.unknown.textContent, 'Wonderful fixture action', String(pageEpoch));
    assert.equal(f.calls.filter(call => call.channel.endsWith(':translate')).length, 0, String(pageEpoch));
  }
});

test('dynamic generated preload never translates builtin or personal entries on unreviewed routes', async () => {
  for (const location of [{pathname:'/'}, {pathname:'/workspace'},
    {pathname:'/onboarding',search:'?token=private'}, {pathname:'/onboarding',hash:'#other'}]) {
    const f = setup({entries:{'Wonderful fixture action':'个人译文'}}, {dynamic:true, location});
    await f.drain();
    assert.equal(f.builtin.textContent, 'Save');
    assert.equal(f.unknown.textContent, 'Wonderful fixture action');
    assert.equal(f.calls.filter(call => call.channel.endsWith(':translate')).length, 0);
  }
});

test('dynamic generated preload translates only reviewed source labels on the approved route', async () => {
  const options = {dynamic:true, location:{pathname:'/onboarding',search:'',hash:''}};
  const f = setup({}, options); await f.drain();
  assert.equal(f.builtin.textContent, '保存');
  assert.equal(f.unknown.textContent, '精彩测试操作');
  assert.equal(f.privateText.textContent, 'Save');
  assert.equal(f.outside.textContent, 'Save');
  const other = setup({}, {...options, unknownText:'User supplied label'}); await other.drain();
  assert.equal(other.builtin.textContent, '保存');
  assert.equal(other.unknown.textContent, 'User supplied label');
  assert.equal(other.calls.filter(call => call.channel.endsWith(':translate')).length, 0);
});

test('dynamic preload restores translation after a query route denies snapshots and returns at the same revision', async () => {
  const location = {pathname:'/', search:'', hash:''};
  const f = setup({}, {dynamicRoot:true, location}); await f.drain();
  const homeSnapshot = f.snapshot;
  const translations = () => f.calls.filter(call => call.channel.endsWith(':translate'));
  assert.equal(f.builtin.textContent, '保存');
  assert.equal(f.unknown.textContent, '精彩测试操作');
  assert.equal(translations().length, 1);

  // Model the actual main-process denial shape, without changing user settings.
  location.search = '?fixtureSettings=open';
  await f.refresh({version:1, status:'unauthorized', translations:[]});
  assert.equal(f.builtin.textContent, 'Save');
  assert.equal(f.unknown.textContent, 'Wonderful fixture action');
  assert.equal(translations().length, 1);

  location.search = '';
  await f.refresh({...homeSnapshot, pageEpoch:2});
  assert.equal(f.builtin.textContent, '保存');
  assert.equal(f.unknown.textContent, '精彩测试操作');
  assert.equal(translations().length, 2);
  assert.equal(f.outside.textContent, 'Save');
  assert.equal(f.privateText.textContent, 'Save');
  assert.deepEqual(translations().flatMap(call => call.request.items.map(item => item.text)),
    ['Wonderful fixture action', 'Wonderful fixture action']);
});

test('dynamic preload rescans labels rebuilt during a query route when closing its modal before the next snapshot poll', async () => {
  const location = {pathname:'/', search:'', hash:''};
  const f = setup({}, {dynamicRoot:true, location}); await f.drain();
  const homeSnapshot = f.snapshot;
  const translations = () => f.calls.filter(call => call.channel.endsWith(':translate'));
  assert.equal(f.builtin.textContent, '保存');
  assert.equal(f.unknown.textContent, '精彩测试操作');
  assert.equal(translations().length, 1);

  // React rebuilds these labels while the modal route is outside the policy.
  // Deliver actual childList records; this is not an unobserved text edit.
  location.search = '?fixtureSettings=open';
  const records = [];
  function replaceLabel(previous, text) {
    const parent = previous.parentElement;
    parent.childNodes.splice(parent.childNodes.indexOf(previous), 1);
    previous.isConnected = false; previous.parentElement = null;
    const next = parent.append(new Text(text));
    records.push({type:'childList', target:parent, addedNodes:[next], removedNodes:[previous]});
    return next;
  }
  const rebuiltBuiltin = replaceLabel(f.builtin, 'Save');
  const rebuiltUnknown = replaceLabel(f.unknown, 'Wonderful fixture action');
  const body = f.context.document.body;
  const modal = body.append(new Element('section'));
  records.push({type:'childList', target:body, addedNodes:[modal], removedNodes:[]});
  f.mutations(records); await f.drain();
  assert.equal(rebuiltBuiltin.textContent, 'Save');
  assert.equal(rebuiltUnknown.textContent, 'Wonderful fixture action');
  assert.equal(translations().length, 1);

  // Closing the modal changes the URL and removes a subtree. No label is added
  // now, and the 1500ms snapshot poll never observed the intervening denial.
  location.search = '';
  body.childNodes.splice(body.childNodes.indexOf(modal), 1);
  modal.isConnected = false; modal.parentElement = null;
  f.mutations([{type:'childList', target:body, addedNodes:[], removedNodes:[modal]}]);
  await f.refresh({...homeSnapshot, pageEpoch:2});
  assert.equal(rebuiltBuiltin.textContent, '保存');
  assert.equal(rebuiltUnknown.textContent, '精彩测试操作');
  assert.equal(translations().length, 2);
  assert.equal(f.outside.textContent, 'Save');
  assert.equal(f.privateText.textContent, 'Save');
});
