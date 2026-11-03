'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {captureScript, sanitizeUiEvidence} = require('../manual/m1-ui-audit.cjs');

function fixture(pathname = '/') {
  const elements = [];
  const document = {location: {pathname, search: '', hash: ''}, querySelector: () => root};
  function element(tag, parent, text, attrs = {}, excluded = false) {
    const node = {tagName: tag.toUpperCase(), parentElement: parent, children: [],
      childNodes: text === undefined ? [] : [{nodeType: 3, textContent: text}],
      getAttribute: name => attrs[name] ?? null, getRootNode: () => document,
      closest() { for (let p = this; p; p = p.parentElement) if (p.excluded) return p; return null; }, excluded};
    if (parent) { parent.children.push(node); parent.childNodes.push(node); elements.push(node); }
    return node;
  }
  const root = element('div', null);
  root.querySelectorAll = () => elements;
  const nav = element('nav', root, undefined, {role: 'navigation'});
  const settings = element('button', nav, ' Settings ');
  const source = captureScript();
  return {document, root, nav, settings, element,
    collect: () => JSON.parse(JSON.stringify(vm.runInNewContext(source, {document, URLSearchParams})))};
}

test('serialized collector records fixed labels and generated structure only', () => {
  const f = fixture();
  f.element('button', f.nav, 'New Conversation', {title: 'New Conversation',
    'data-private': 'secret-user@example.com', id: 'private-project'});
  const report = sanitizeUiEvidence(f.collect());
  assert.equal(report.rootFound, true);
  assert.deepEqual(report.matches.map(p => p.source), ['Settings', 'New Conversation', 'New Conversation']);
  assert.equal(report.matches[0].selector, '#root > nav:nth-of-type(1) > button:nth-of-type(1)');
  assert.equal(report.matches[0].chain[0].role, 'navigation');
  assert.doesNotMatch(JSON.stringify(report), /private|secret-user/);
});

test('fixed translated labels distinguish builtin display from controlled output', () => {
  const f = fixture();
  f.element('span', f.nav, '自动化');
  f.element('span', f.nav, '自动化（测试译文）');
  f.element('span', f.nav, '用户的私人中文');
  const report = sanitizeUiEvidence(f.collect());
  assert.deepEqual(report.matches.map(p => p.source), ['Settings', '自动化', '自动化（测试译文）']);
  assert.doesNotMatch(JSON.stringify(report), /私人/);
});

test('unknown text and attribute values never leave the collector', () => {
  const f = fixture();
  f.element('div', f.root, 'Private business plan', {title: 'secret-user@example.com'});
  f.element('span', f.root, 'Settings for private-project');
  f.element('a', f.root, undefined, {'aria-label': 'Settings', href: 'https://example.com/private'});
  const report = sanitizeUiEvidence(f.collect());
  assert.equal(report.matches.length, 2);
  assert.doesNotMatch(JSON.stringify(report), /business|private|example/);
});

test('excluded content is rejected before text or attribute reads', () => {
  const f = fixture();
  const chat = f.element('section', f.root, undefined, {}, true);
  const privateNode = f.element('button', chat, 'Settings');
  Object.defineProperty(privateNode, 'childNodes', {get() { throw new Error('Read private content'); }});
  privateNode.getAttribute = () => { throw new Error('Read private attribute'); };
  const report = sanitizeUiEvidence(f.collect());
  assert.equal(report.matches.length, 1);
});

test('unknown route/query/hash state is not serialized or inspected', () => {
  for (const location of [{pathname: '/conversation/private-uuid', search: '', hash: ''},
    {pathname: '/', search: '?token=private', hash: ''}, {pathname: '/', search: '', hash: '#private'}]) {
    const f = fixture(); f.document.location = location;
    f.document.querySelector = () => { throw new Error('Unexpected document access'); };
    const report = sanitizeUiEvidence(f.collect());
    assert.equal(report.matches.length, 0);
    assert.doesNotMatch(JSON.stringify(report), /private|token/);
  }
});

test('shadow roots and overly deep structures are omitted', () => {
  const f = fixture();
  f.settings.getRootNode = () => ({});
  let parent = f.root;
  for (let i = 0; i < 17; i++) parent = f.element('div', parent);
  f.element('button', parent, 'Settings');
  assert.equal(f.collect().matches.length, 0);
});

test('query diagnosis emits only fixed vocabulary while refusing DOM access', () => {
  const f = fixture();
  f.document.location.search = '?view=settings&tab=private-secret&conversationId=private-id&secret-user=private-value&view=&view=home';
  f.document.querySelector = () => { throw new Error('Unexpected document access'); };
  const report = sanitizeUiEvidence(f.collect());
  assert.deepEqual(report.route.query, {known: [
    {key: 'view', value: 'settings'}, {key: 'tab', value: null},
    {key: 'conversationId', value: null}, {key: 'view', value: ''}, {key: 'view', value: 'home'}
  ], unknownKeys: 1, truncated: false});
  assert.equal(report.matches.length, 0);
  assert.equal(report.rootFound, false);
  assert.doesNotMatch(JSON.stringify(report), /private|secret-user/);
});

test('query diagnostics bound parameter count and raw input length', () => {
  const f = fixture();
  f.document.location.search = '?' + Array(17).fill('private-key=private-value').join('&');
  assert.deepEqual(sanitizeUiEvidence(f.collect()).route.query,
    {known: [], unknownKeys: 16, truncated: true});
  f.document.location.search = '?view=' + 'x'.repeat(2048);
  assert.deepEqual(sanitizeUiEvidence(f.collect()).route.query,
    {known: [], unknownKeys: 0, truncated: true});
});

test('query sanitizer rejects arbitrary values and counts and strips extra fields', () => {
  const f = fixture(); f.document.location.search = '?view=settings';
  const report = f.collect();
  report.route.query.url = 'private'; report.route.query.known[0].raw = 'private';
  assert.doesNotMatch(JSON.stringify(sanitizeUiEvidence(report)), /private/);
  for (const mutate of [p => { p.route.query.known[0].key = 'secret'; },
    p => { p.route.query.known[0].value = 'private'; },
    p => { p.route.query.unknownKeys = 17; }, p => { p.route.hasQuery = false; },
    p => { p.route.query.unknownKeys = -1; }, p => { p.route.query.truncated = 'private'; }]) {
    const changed = structuredClone(report); mutate(changed);
    assert.throws(() => sanitizeUiEvidence(changed), /query evidence/);
  }
});

test('renderer payloads cannot introduce arbitrary fields or values', () => {
  const report = fixture().collect();
  report.html = 'private'; report.matches[0].secret = 'private';
  assert.doesNotMatch(JSON.stringify(sanitizeUiEvidence(report)), /private/);
  for (const mutate of [p => { p.route.path = '/private'; },
    p => { p.matches[0].source = 'Private label'; }, p => { p.matches[0].attribute = 'value'; },
    p => { p.matches[0].chain[0].role = 'private'; },
    p => { p.matches[0].selector = '#private'; }, p => { p.route.hasQuery = true; }]) {
    const changed = structuredClone(report); mutate(changed);
    assert.throws(() => sanitizeUiEvidence(changed));
  }
});

test('large repeated labels produce a bounded report', () => {
  const f = fixture();
  for (let i = 0; i < 80; i++) f.element('button', f.nav, 'Settings');
  const report = sanitizeUiEvidence(f.collect());
  assert.equal(report.truncated, true); assert.equal(report.matches.length, 64);
});
