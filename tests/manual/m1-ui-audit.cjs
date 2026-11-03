'use strict';
// Development-only, user-triggered structural evidence. Never exports page HTML.
const vocabulary = Object.freeze({
  labels: ['New Conversation', 'Automations', 'Customizations', 'Projects', 'Settings',
    'Continue with Google', 'Use Business Account', 'Having trouble signing in?',
    '新建对话', '自动化', '自动化（测试译文）', '自定义', '设置'],
  paths: ['/', '/onboarding', '/settings', '/automations', '/customizations',
    '/new', '/new-conversation', '/chat', '/conversations'],
  // Diagnostic vocabulary only; none of these authorize a production route.
  queryKeys: ['view', 'tab', 'page', 'panel', 'section', 'settings', 'showSettings',
    'isSettingsOpen', 'conversationId', 'conversation', 'workspaceId', 'projectId', 'windowId'],
  queryValues: ['', 'true', 'false', '0', '1', 'settings', 'general', 'home', 'chat',
    'new', 'appearance', 'account'],
  tags: ['div', 'span', 'button', 'a', 'nav', 'aside', 'section', 'main', 'header',
    'footer', 'ul', 'li', 'p', 'h1', 'h2', 'h3', 'label'],
  roles: ['button', 'link', 'navigation', 'menu', 'menuitem', 'tab', 'tablist',
    'heading', 'complementary', 'region', 'main', 'presentation', 'none']
});

// Self-contained because its source is evaluated in the target page.
function collectUiEvidence(doc, words) {
  const route = {path: words.paths.includes(doc.location.pathname) ? doc.location.pathname : null,
    hasQuery: !!doc.location.search, hasHash: !!doc.location.hash};
  const report = {schemaVersion: 1, route, rootFound: false, truncated: false, matches: []};
  // Never export raw URLs, unknown keys, identifiers or arbitrary parameter values.
  // Query metadata does not grant permission to inspect the DOM below.
  route.query = {known: [], unknownKeys: 0, truncated: false};
  if (route.hasQuery) {
    if (doc.location.search.length > 2048) route.query.truncated = true;
    else {
      let count = 0;
      for (const [key, value] of new URLSearchParams(doc.location.search)) {
        if (count++ >= 16) { route.query.truncated = true; break; }
        if (!words.queryKeys.includes(key)) { route.query.unknownKeys++; continue; }
        route.query.known.push({key, value: words.queryValues.includes(value) ? value : null});
      }
    }
  }
  // Never inspect an unknown route, or a route carrying query/hash state.
  if (route.path === null || route.hasQuery || route.hasHash) return report;
  const root = doc.querySelector('#root');
  if (!root) return report;
  report.rootFound = true;
  const excluded = 'script,style,pre,code,input,textarea,select,option,iframe,webview,' +
    '[contenteditable],[role="textbox"],[role="log"],.monaco-editor,.cm-editor,.CodeMirror,' +
    '.terminal,.xterm,.diff,.chat,.conversation,.message,.thinking,.reasoning,.logs,' +
    '[data-user-content],[data-user-name],[data-artifact-content],[data-no-translate]';
  function structure(element) {
    const chain = [];
    for (let node = element; node && node !== root; node = node.parentElement) {
      if (chain.length >= 16) return null;
      const tag = node.tagName.toLowerCase();
      if (!words.tags.includes(tag) || !node.parentElement) return null;
      const siblings = Array.from(node.parentElement.children).filter(p => p.tagName === node.tagName);
      const index = siblings.indexOf(node) + 1;
      if (index < 1 || index > 10000) return null;
      const role = node.getAttribute('role');
      chain.unshift({tag, index, role: words.roles.includes(role) ? role : null});
    }
    return chain.length ? {selector: '#root' + chain.map(p => ` > ${p.tag}:nth-of-type(${p.index})`).join(''), chain} : null;
  }
  const elements = root.querySelectorAll(words.tags.join(','));
  if (elements.length > 10000) report.truncated = true;
  for (let i = 0; i < Math.min(elements.length, 10000); i++) {
    const element = elements[i];
    // Check ancestry before reading any text. Input values are never accessed.
    if (element.closest(excluded) || element.getRootNode() !== doc) continue;
    const values = [];
    for (const child of element.childNodes) {
      if (child.nodeType !== 3) continue;
      const value = child.textContent;
      if (typeof value === 'string' && value.length <= 160 && words.labels.includes(value.trim())) {
        values.push({source: value.trim(), attribute: null});
      }
    }
    for (const attribute of ['title', 'aria-label']) {
      const value = element.getAttribute(attribute);
      if (typeof value === 'string' && value.length <= 160 && words.labels.includes(value.trim())) {
        values.push({source: value.trim(), attribute});
      }
    }
    if (!values.length) continue;
    const location = structure(element);
    if (!location) continue;
    for (const value of values) {
      if (report.matches.length >= 64) { report.truncated = true; return report; }
      report.matches.push({...value, ...location});
    }
  }
  return report;
}

function captureScript() {
  return `(${collectUiEvidence.toString()})(document, ${JSON.stringify(vocabulary)})`;
}

// Treat renderer results as untrusted; reconstruct only the allowed fields.
function sanitizeUiEvidence(value) {
  if (!value || value.schemaVersion !== 1 || !value.route || !Array.isArray(value.matches) || value.matches.length > 64 ||
      typeof value.rootFound !== 'boolean' || typeof value.truncated !== 'boolean' ||
      typeof value.route.hasQuery !== 'boolean' || typeof value.route.hasHash !== 'boolean' ||
      (value.route.path !== null && !vocabulary.paths.includes(value.route.path))) throw new Error('Invalid UI evidence');
  if ((value.route.path === null || value.route.hasQuery || value.route.hasHash) && value.matches.length) throw new Error('Unexpected route evidence');
  const query = value.route.query;
  if (!query || !Array.isArray(query.known) || !Number.isInteger(query.unknownKeys) ||
      query.unknownKeys < 0 || query.known.length + query.unknownKeys > 16 ||
      typeof query.truncated !== 'boolean' ||
      (!value.route.hasQuery && (query.known.length || query.unknownKeys || query.truncated))) throw new Error('Invalid query evidence');
  const known = query.known.map(item => {
    if (!item || !vocabulary.queryKeys.includes(item.key) ||
        (item.value !== null && !vocabulary.queryValues.includes(item.value))) throw new Error('Invalid query evidence');
    return {key: item.key, value: item.value};
  });
  const matches = value.matches.map(item => {
    if (!item || !vocabulary.labels.includes(item.source) || ![null, 'title', 'aria-label'].includes(item.attribute) ||
        !Array.isArray(item.chain) || !item.chain.length || item.chain.length > 16) throw new Error('Invalid label evidence');
    const chain = item.chain.map(p => {
      if (!p || !vocabulary.tags.includes(p.tag) || !Number.isInteger(p.index) || p.index < 1 || p.index > 10000 ||
          (p.role !== null && !vocabulary.roles.includes(p.role))) throw new Error('Invalid structure evidence');
      return {tag: p.tag, index: p.index, role: p.role};
    });
    const selector = '#root' + chain.map(p => ` > ${p.tag}:nth-of-type(${p.index})`).join('');
    if (item.selector !== selector) throw new Error('Invalid selector evidence');
    return {source: item.source, attribute: item.attribute, selector, chain};
  });
  return {schemaVersion: 1, route: {path: value.route.path, hasQuery: value.route.hasQuery,
    hasHash: value.route.hasHash, query: {known, unknownKeys: query.unknownKeys, truncated: query.truncated}},
    rootFound: value.rootFound, truncated: value.truncated, matches};
}

module.exports = {collectUiEvidence, captureScript, sanitizeUiEvidence, vocabulary};
