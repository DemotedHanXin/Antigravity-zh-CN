'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const ROOT = path.resolve(__dirname, '../..');
// Generate actual production preload bytes, not a hand-maintained copy.
const source = execFileSync(process.env.PYTHON || 'python', ['-X', 'utf8', '-B', '-c', `
import importlib.util
from translation_integration import preload_extension
spec = importlib.util.spec_from_file_location('patcher', 'Antigravity-Patcher.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
profile = {'policy': {'verified': True, 'rules': [{'selector': '.fixture-static-label', 'contextKind': 'button', 'text': True, 'attributes': ['title']}]}}
print(p.DOM_TRANSLATOR_INJECTION.replace('  const observer = new MutationObserver', preload_extension(profile) + '\\n  const observer = new MutationObserver', 1))
`], { cwd: ROOT, encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
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
function setup(initial = {}) {
  const documentEvents = new Map(), windowEvents = new Map();
  const document = { readyState: 'loading', addEventListener(name, callback) { const list = documentEvents.get(name) || []; list.push(callback); documentEvents.set(name, list); } };
  document.body = new Element('body'); document.body.doc = document;
  const add = value => document.body.append(new Element('button', ['fixture-static-label'])).append(new Text(value));
  const builtin = add('Save'), unknown = add('Wonderful fixture action');
  const calls = [], intervals = new Map(), timeouts = new Map(); let id = 0;
  let snapshot = { version: 1, enabled: true, configRevision: 1, dictionaryRevision: 0, cacheEpoch: 0, entries: {}, ...initial };
  const context = {
    document, Node: { TEXT_NODE: 3, ELEMENT_NODE: 1 }, AbortController,
    window: { addEventListener(name, callback) { windowEvents.set(name, callback); } },
    MutationObserver: class { observe() {} disconnect() {} },
    setInterval(fn) { intervals.set(++id, fn); return id; }, clearInterval(key) { intervals.delete(key); },
    setTimeout(fn) { timeouts.set(++id, fn); return id; }, clearTimeout(key) { timeouts.delete(key); },
    require(name) { assert.equal(name, 'electron'); return { ipcRenderer: { async invoke(channel, request) {
      calls.push({ channel, request });
      if (channel === 'dragongirl:v1:snapshot') return snapshot;
      assert.equal(channel, 'dragongirl:v1:translate');
      return { version: 1, configRevision: request.configRevision, dictionaryRevision: request.dictionaryRevision, cacheEpoch: request.cacheEpoch, status: 'ok', translations: request.items.map(item => ({ id: item.id, text: '精彩测试操作' })) };
    } } }; },
  };
  const keys = Object.keys(context).sort();
  vm.runInNewContext(source, context, { filename: 'generated-verified-preload.js', timeout: 2000 });
  for (const callback of documentEvents.get('DOMContentLoaded') || []) callback();
  async function drain() { await tick(); for (const [key, callback] of [...timeouts]) { timeouts.delete(key); callback(); } await tick(); }
  async function refresh(next) { snapshot = next; for (const callback of intervals.values()) callback(); await drain(); }
  return { context, builtin, unknown, calls, drain, refresh, keys, intervals, windowEvents, get snapshot() { return snapshot; } };
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
test('polling snapshot refresh updates personal dictionary with AI disabled', async () => {
  const f = setup({ enabled: false, entries: { 'Wonderful fixture action': '个人翻译' } }); await f.drain();
  assert.equal(f.unknown.textContent, '个人翻译'); assert.equal(f.calls.filter(c => c.channel.endsWith(':translate')).length, 0);
  await f.refresh({ ...f.snapshot, dictionaryRevision: 1, entries: { 'Wonderful fixture action': '新个人翻译' } }); assert.equal(f.unknown.textContent, '新个人翻译');
  await f.refresh({ ...f.snapshot, dictionaryRevision: 2, entries: {} }); assert.equal(f.unknown.textContent, 'Wonderful fixture action');
});
test('pagehide disposes polling and prevents further work', async () => {
  const f = setup(); await f.drain(); f.windowEvents.get('pagehide')(); assert.equal(f.intervals.size, 0);
});
test('wrong snapshot protocol fails closed without remote translation', async () => {
  const f = setup({ version: 99 }); await f.drain();
  assert.equal(f.builtin.textContent, '保存'); assert.equal(f.unknown.textContent, 'Wonderful fixture action');
  assert.equal(f.calls.filter(c => c.channel.endsWith(':translate')).length, 0);
});
