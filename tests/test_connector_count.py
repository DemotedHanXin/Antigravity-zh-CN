"""Verify live connector counts without replacing React-owned nodes or user input."""
import unittest

from test_icon_repair import BROWSER, run_dom_check


FIXTURES = r"""
<div id="counts">
  <h3>Connectors</h3>
  <span id="split"><span id="number">0</span> on for this conversation</span>
  <span id="full">1 on for this conversation</span>
  <span id="nested"> <span><span id="nested-number">12</span></span><span> on for this conversation</span></span>
  <span id="mixed">2 开 for this conversation</span>
  <span id="remount"><span>4</span><span> on for this conversation</span></span>
  <span id="reused"><span>4</span> on for this conversation</span>
</div>
<pre><code id="code">3 on for this conversation</code></pre>
<div contenteditable="true" id="editable">3 on for this conversation</div>
<textarea id="textarea" placeholder="Enter project name...">3 on for this conversation</textarea>
<input id="input" placeholder="Enter project name..." value="3 on for this conversation">
<span id="unrelated">3 on for this conversation tomorrow</span>
<pre id="icon-repair-result"></pre>
"""

CHECKS = r"""
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
const ensure = (condition, message) => { if (!condition) throw new Error(message); };
const allNodes = root => [root, ...Array.from(root.childNodes || []).flatMap(allNodes)];
const split = document.getElementById('split');
const nested = document.getElementById('nested');
const original = allNodes(split);
const originalNested = allNodes(nested);
const number = document.getElementById('number').firstChild;
const nestedNumber = document.getElementById('nested-number').firstChild;
const suffix = split.lastChild;
const sourceSuffix = suffix.textContent;
document.addEventListener('DOMContentLoaded', async () => {
  const result = document.getElementById('icon-repair-result');
  try {
    await tick();
    for (const [id, count] of [['split', 0], ['full', 1], ['nested', 12], ['mixed', 2]]) {
      ensure(document.getElementById(id).textContent === '本次对话已启用 ' + count + ' 个', id + ': wrong initial count');
    }
    for (const count of [1, 27, 0]) {
      number.textContent = String(count);
      await tick();
      ensure(split.textContent === '本次对话已启用 ' + count + ' 个', 'count update lost');
    }
    suffix.textContent = sourceSuffix;
    await tick();
    ensure(split.textContent === '本次对话已启用 0 个', 'suffix update duplicated the label');
    nestedNumber.textContent = '57';
    await tick();
    ensure(nested.textContent === '本次对话已启用 57 个', 'deeply nested counter update lost');
    document.getElementById('full').firstChild.textContent = '18 on for this conversation';
    await tick();
    ensure(document.getElementById('full').textContent === '本次对话已启用 18 个', 'full-label update lost');
    const remount = document.getElementById('remount');
    remount.innerHTML = '<span>7</span><span> on for this conversation</span>';
    await tick();
    ensure(remount.textContent === '本次对话已启用 7 个', 'remounted label not translated');
    remount.firstChild.firstChild.textContent = '9';
    await tick();
    ensure(remount.textContent === '本次对话已启用 9 个', 'remounted counter not rebound');
    const reused = document.getElementById('reused');
    reused.firstChild.firstChild.textContent = '8';
    reused.lastChild.textContent = ' seconds elapsed';
    await tick();
    ensure(reused.textContent === '8 seconds elapsed', 'unrelated reused label overwritten');
    reused.firstChild.firstChild.textContent = '12';
    await tick();
    ensure(reused.textContent === '12 seconds elapsed', 'stale count binding retained');
    for (const id of ['code', 'editable', 'textarea']) {
      ensure(document.getElementById(id).textContent === '3 on for this conversation', id + ': user content changed');
    }
    for (const id of ['input', 'textarea']) {
      const field = document.getElementById(id);
      ensure(field.value === '3 on for this conversation', id + ': value changed');
      ensure(field.placeholder === '输入项目名称...', id + ': placeholder not translated');
    }
    ensure(document.getElementById('unrelated').textContent === '3 on for this conversation tomorrow', 'unrelated prose changed');
    const after = allNodes(split);
    const afterNested = allNodes(nested);
    ensure(original.length === after.length && original.every((node, index) => node === after[index]), 'original nodes replaced');
    ensure(originalNested.length === afterNested.length && originalNested.every((node, index) => node === afterNested[index]), 'nested nodes replaced');
    result.textContent = JSON.stringify({ok: true, checks: 'count values, nested updates, remounts, stale state, nodes, editable fields'});
  } catch (error) {
    result.textContent = JSON.stringify({ok: false, error: error.message});
  }
});
"""


@unittest.skipUnless(BROWSER, 'Chrome or Edge is required for the isolated DOM test')
class ConnectorCountTests(unittest.TestCase):
    def test_connector_count_survives_updates_and_preserves_user_content(self):
        run_dom_check(self, FIXTURES, CHECKS)


if __name__ == '__main__':
    unittest.main()
