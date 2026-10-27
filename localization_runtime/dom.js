/* DragonGirl DOM extension. Bundled into a verified isolated preload, never exposed
 * as a main-world API. An empty/unverified policy deliberately translates nothing. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  // Browser integration embeds factory source in a private preload closure.
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const ATTRIBUTES = ['title', 'placeholder', 'aria-label'];
  const MAX_TRACKED_SLOTS = 2048, MAX_PENDING_TASKS = 256, MAX_SCAN_NODES = 10000;
  const EXCLUDED = 'script,style,pre,code,input,textarea,select,option,iframe,webview,' +
    '[contenteditable],[role="textbox"],[role="log"],.monaco-editor,.cm-editor,.CodeMirror,' +
    '.terminal,.xterm,.diff,.chat,.conversation,.message,.thinking,.reasoning,.logs,' +
    '[data-user-content],[data-user-name],[data-artifact-content],[data-no-translate]';
  function safeText(text) {
    if (typeof text !== 'string') return false;
    const value = text.trim();
    if (!value || value.length > 160 || !/[A-Za-z]/.test(value)) return false;
    if (/[^\x20-\x7e]/.test(value) || /[\r\n<>`\\]/.test(text)) return false;
    if (/https?:|www\.|@|(?:^|\s)(?:\/|~\/|[A-Za-z]:)|\b(?:sk-|AIza|ghp_|Bearer\s)/i.test(value)) return false;
    if (/[A-Za-z0-9_\-]{32,}|\b\w+[_=]\w+|\b[0-9a-f]{16,}\b/i.test(value)) return false;
    if (/\w+\/\w+|\b[\w-]+\.(?:js|ts|py|json|txt|md|log)\b/i.test(value)) return false;
    return true;
  }
  function validTranslation(value) {
    return typeof value === 'string' && value.trim().length > 0 && value.length <= 640 &&
      !/[<>`\r\n\x00-\x08]/.test(value) && /[\u3400-\u9fff]/.test(value);
  }
  function placeholders(text) {
    return (text.match(/\$?\{\{?[^{}]+\}\}?|%(?:\d+\$)?[sdif]/g) || []).sort().join('\u0000');
  }
  function createDOMTranslator(options) {
    const opts = options || {}, doc = opts.document;
    if (!doc) throw new TypeError('document required');
    const policy = opts.policy || {}, rules = Array.isArray(policy.rules) ? policy.rules : [];
    const bridge = opts.bridge || {}, getSnapshot = opts.getSnapshot || (() => ({}));
    const syncTranslate = opts.syncTranslate || (value => ({ matched: false, value }));
    const Observer = opts.MutationObserver;
    const timers = opts.timers || { setTimeout, clearTimeout };
    let stopped = false, observer = null, timer = null, epoch = 0, sequence = 0, active = 0;
    let signature = '', snapshot = {}, tracked = new Set(), slots = new WeakMap();
    const queued = new Map(), inflight = new Map(), cooldown = new Map();
    function readSnapshot() {
      try { return getSnapshot() || {}; } catch (_) { return {}; }
    }
    function stamp(s) {
      return JSON.stringify([!!s.enabled, s.configRevision, s.dictionaryRevision, s.cacheEpoch, s.pageEpoch]);
    }
    function elementFor(node) { return node.nodeType === 3 ? node.parentElement : node; }
    function safeContext(node, attribute) {
      if (policy.verified !== true || stopped || !node || !node.isConnected) return null;
      const element = elementFor(node);
      if (!element || typeof element.closest !== 'function') return null;
      if (node.getRootNode && node.getRootNode() !== doc) return null;
      try {
        if (element.closest(EXCLUDED)) return null;
        if (policy.excludeSelectors && policy.excludeSelectors.some(selector => element.closest(selector))) return null;
        for (const rule of rules) {
          if (!rule || typeof rule.selector !== 'string' || !['toolbar', 'settings', 'navigation', 'menu', 'button', 'label'].includes(rule.contextKind)) continue;
          if (attribute ? (!Array.isArray(rule.attributes) || !rule.attributes.includes(attribute)) : rule.text !== true) continue;
          if (element.matches(rule.selector)) return rule.contextKind;
        }
      } catch (_) { return null; } // Invalid or changed selector policy fails closed.
      return null;
    }
    function read(node, attribute) { return attribute ? node.getAttribute(attribute) : node.textContent; }
    function write(slot, value) {
      slot.displayed = value;
      if (slot.attribute) slot.node.setAttribute(slot.attribute, value);
      else slot.node.textContent = value;
    }
    function retainSpacing(original, translated) {
      return original.slice(0, original.length - original.trimStart().length) + translated.trim() +
        original.slice(original.trimEnd().length);
    }
    function clearPending() {
      epoch++;
      if (timer !== null) timers.clearTimeout(timer);
      timer = null;
      queued.clear();
      for (const task of inflight.values()) task.controller.abort();
      inflight.clear();
      cooldown.clear();
    }
    function refresh() {
      const next = readSnapshot(), nextSignature = stamp(next);
      if (nextSignature === signature) return false;
      clearPending(); snapshot = next; signature = nextSignature;
      for (const slot of tracked) {
        if (!slot.node.isConnected) { tracked.delete(slot); continue; }
        slot.generation++;
        if (slot.displayed !== null && read(slot.node, slot.attribute) === slot.displayed) write(slot, slot.original);
        slot.displayed = null;
      }
      return true;
    }
    function prune() {
      for (const slot of tracked) {
        if (slot.node.isConnected) continue;
        slot.generation++;
        tracked.delete(slot);
        const map = slots.get(slot.node);
        if (map) map.delete(slot.attribute || 'text');
      }
      for (const tasks of [queued, inflight]) for (const [key, task] of tasks) {
        task.waiters = task.waiters.filter(waiter => tracked.has(waiter.slot) && waiter.slot.node.isConnected && waiter.generation === waiter.slot.generation && read(waiter.slot.node, waiter.slot.attribute) === waiter.original);
        if (!task.waiters.length) { task.controller.abort(); tasks.delete(key); }
      }
    }
    function slotFor(node, attribute, original) {
      let map = slots.get(node);
      if (!map) { map = new Map(); slots.set(node, map); }
      let slot = map.get(attribute || 'text');
      if (!slot) {
        if (tracked.size >= MAX_TRACKED_SLOTS) return null;
        slot = { node, attribute, original, displayed: null, generation: 0 };
        map.set(attribute || 'text', slot); tracked.add(slot);
      } else if (slot.original !== original && slot.displayed !== original) {
        slot.original = original; slot.displayed = null; slot.generation++;
      }
      return slot;
    }
    function current(waiter, task) {
      const slot = waiter.slot;
      return !stopped && task.epoch === epoch && stamp(readSnapshot()) === task.signature &&
        readSnapshot().enabled === true && slot.generation === waiter.generation &&
        read(slot.node, slot.attribute) === waiter.original &&
        safeContext(slot.node, slot.attribute) === task.context;
    }
    function schedule() {
      if (timer === null && !stopped) timer = timers.setTimeout(() => { timer = null; flush(); }, 200);
    }
    function candidate(node, attribute) {
      const context = safeContext(node, attribute);
      if (!context) return;
      const original = read(node, attribute);
      if (!safeText(original)) return;
      const slot = slotFor(node, attribute, original);
      if (!slot) return;
      if (slot.displayed === original) return;
      let result;
      try { result = syncTranslate(original); } catch (_) { return; }
      if (!result || typeof result.value !== 'string') return;
      if (result.matched) { if (result.value !== original) write(slot, result.value); return; }
      const text = original.trim(), entries = snapshot.entries || {};
      const entry = Object.prototype.hasOwnProperty.call(entries, text) ? entries[text] : null;
      if (typeof entry === 'string' && validTranslation(entry) && placeholders(entry) === placeholders(text)) {
        write(slot, retainSpacing(original, entry)); return;
      }
      if (snapshot.enabled !== true || typeof bridge.translate !== 'function') return;
      const key = JSON.stringify([signature, context, text]);
      if (cooldown.has(key) && cooldown.get(key) > Date.now()) return;
      let task = queued.get(key) || inflight.get(key);
      if (!task) {
        if (queued.size + inflight.size >= MAX_PENDING_TASKS) return;
        task = { key, id: String(++sequence), text, context, epoch, signature, waiters: [], controller: new AbortController() };
        queued.set(key, task);
      }
      const prior = task.waiters.findIndex(w => w.slot === slot);
      const waiter = { slot, generation: slot.generation, original };
      if (prior >= 0) task.waiters[prior] = waiter;
      else {
        let total = 0;
        for (const pending of [...queued.values(), ...inflight.values()]) total += pending.waiters.length;
        if (total < MAX_TRACKED_SLOTS) task.waiters.push(waiter);
        else if (!task.waiters.length) queued.delete(key);
      }
      schedule();
    }
    function scan(node, sharedBudget) {
      if (stopped || !node) return;
      if (!sharedBudget) { prune(); if (refresh()) node = doc.body; }
      const budget = sharedBudget || { remaining: MAX_SCAN_NODES };
      const stack = [node];
      // Iterative and bounded: deeply nested or enormous DOMs cannot create an
      // unbounded traversal stack or monopolize this preload's observer callback.
      while (stack.length && budget.remaining > 0) {
        budget.remaining--;
        const currentNode = stack.pop();
        if (!currentNode) continue;
        if (currentNode.nodeType === 3) { candidate(currentNode, null); continue; }
        if (currentNode.nodeType !== 1) continue;
        try { if (currentNode.closest(EXCLUDED)) continue; } catch (_) { continue; }
        for (const attribute of ATTRIBUTES) if (currentNode.getAttribute(attribute)) candidate(currentNode, attribute);
        const children = currentNode.childNodes || [];
        const room = budget.remaining - stack.length;
        for (let i = Math.min(children.length, room) - 1; i >= 0; i--) stack.push(children[i]);
      }
    }
    async function flush() {
      if (stopped) return;
      prune();
      if (refresh()) scan(doc.body);
      if (snapshot.enabled !== true || active >= 2 || queued.size === 0) return;
      // A label may move into a chat/editor or change while waiting for the
      // batching timer. Revalidate immediately before any text crosses IPC.
      for (const [key, task] of queued) {
        task.waiters = task.waiters.filter(waiter => current(waiter, task));
        if (!task.waiters.length) { task.controller.abort(); queued.delete(key); }
      }
      if (queued.size === 0) return;
      const batch = Array.from(queued.values()).slice(0, 8);
      batch.forEach(task => { queued.delete(task.key); inflight.set(task.key, task); });
      active++;
      const controller = new AbortController();
      const cancel = () => controller.abort();
      batch.forEach(task => task.controller.signal.addEventListener('abort', cancel, { once: true }));
      try {
        const request = { version: 1, configRevision: snapshot.configRevision, dictionaryRevision: snapshot.dictionaryRevision, cacheEpoch: snapshot.cacheEpoch, items: batch.map(task => ({ id: task.id, text: task.text, safeContextKind: task.context })) };
        const response = await bridge.translate(request, { signal: controller.signal });
        if (!response || response.version !== 1 || response.configRevision !== request.configRevision || response.dictionaryRevision !== request.dictionaryRevision || response.cacheEpoch !== request.cacheEpoch) throw new Error('stale response');
        const rows = response.translations;
        if (!Array.isArray(rows) || rows.length > batch.length) throw new Error('invalid response');
        const results = new Map();
        for (const row of rows) {
          if (!row || typeof row.id !== 'string' || results.has(row.id) || !batch.some(t => t.id === row.id) || !validTranslation(row.text)) throw new Error('invalid response');
          const task = batch.find(t => t.id === row.id);
          if (placeholders(row.text) !== placeholders(task.text)) throw new Error('placeholder mismatch');
          results.set(row.id, row.text);
        }
        for (const task of batch) {
          if (!results.has(task.id)) { cooldown.set(task.key, Date.now() + 30000); continue; }
          for (const waiter of task.waiters) {
            if (current(waiter, task)) write(waiter.slot, retainSpacing(waiter.original, results.get(task.id)));
          }
        }
      } catch (_) {
        for (const task of batch) cooldown.set(task.key, Date.now() + 30000);
        while (cooldown.size > 512) cooldown.delete(cooldown.keys().next().value);
      } finally {
        while (cooldown.size > 512) cooldown.delete(cooldown.keys().next().value);
        active--;
        for (const task of batch) {
          task.controller.signal.removeEventListener('abort', cancel);
          if (inflight.get(task.key) === task) inflight.delete(task.key);
        }
        prune();
        if (queued.size) schedule();
      }
    }
    function markMutation(node, attribute) {
      const map = slots.get(node), slot = map && map.get(attribute || 'text');
      // Even a value changed away and back before observer delivery invalidates
      // pending work. Our own final writes do not create new requests.
      if (slot && (slot.displayed === null || read(node, attribute) !== slot.displayed)) slot.generation++;
    }
    function start() {
      if (observer || stopped) return;
      refresh(); scan(doc.body);
      if (Observer && doc.body) {
        observer = new Observer(mutations => {
          prune();
          if (refresh()) { scan(doc.body); return; }
          const budget = { remaining: MAX_SCAN_NODES };
          for (const mutation of mutations) {
            if (budget.remaining <= 0) break;
            if (mutation.type === 'childList') {
              for (const node of mutation.addedNodes) { if (budget.remaining <= 0) break; scan(node, budget); }
            } else if (mutation.type === 'characterData') { markMutation(mutation.target, null); scan(mutation.target, budget); }
            else if (mutation.type === 'attributes' && ATTRIBUTES.includes(mutation.attributeName)) { budget.remaining--; markMutation(mutation.target, mutation.attributeName); candidate(mutation.target, mutation.attributeName); }
          }
        });
        observer.observe(doc.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRIBUTES });
      }
    }
    function invalidate() { clearPending(); signature = ''; refresh(); scan(doc.body); }
    function stop() {
      stopped = true; clearPending();
      if (observer) observer.disconnect();
      observer = null; tracked.clear(); slots = new WeakMap();
    }
    return { start, stop, getStats: () => ({ trackedSlots: tracked.size, queuedTasks: queued.size, inflightTasks: inflight.size, pendingWaiters: [...queued.values(), ...inflight.values()].reduce((sum, task) => sum + task.waiters.length, 0) }), refresh: () => { const changed = refresh(); if (changed) scan(doc.body); return changed; }, invalidate, scan, flush };
  }
  return { createDOMTranslator, safeText, validTranslation, EXCLUDED };
});
