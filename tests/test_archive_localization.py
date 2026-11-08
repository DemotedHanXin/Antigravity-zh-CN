"""Check archive controls, inline filter icons, and split voice durations."""
import unittest

from test_icon_repair import BROWSER, run_dom_check


FIXTURES = r"""
<div id="toast"><span id="toast-prefix">View archived in the sidebar (</span><svg id="filter" aria-hidden="true" viewBox="0 0 24 24"><path d="M4 6h16M7 12h10M10 18h4"/></svg><span id="toast-suffix"> menu).</span></div>
<div id="unknown">View archived in the sidebar (<svg><path d="M4 6h16"/></svg> menu tomorrow).</div>
<div role="menu"><div role="menuitem" id="menu-restore" aria-label="Restore"><svg viewBox="0 0 24 24"><path d="M4 4h16v16H4z"/></svg><span id="menu-label">Restore</span></div></div>
<div id="footer"><span id="footer-text">This chat is archived.</span><button id="footer-restore" title="Restore"><span id="footer-label">Restore</span></button></div>
<button id="unrelated-button">Restore</button><span id="plain">Restore</span>
<pre><code><div role="menuitem" id="code">Restore</div></code></pre>
<div contenteditable="true"><div role="menuitem" id="editable">Restore</div></div>
<div id="voice-whole">Voice chat · 17:00 · 9s</div>
<div id="voice-split"><span>Voice chat</span> · <span id="time">09:05</span> · <span id="duration">12s</span></div>
<div id="voice-numeric"><span>Voice chat</span> · 23:59 · <span id="seconds">9</span><span id="unit">s</span></div>
<span id="unrelated-duration">12s</span>
<pre id="icon-repair-result"></pre>
"""

CHECKS = r"""
const ensure = (condition, message) => { if (!condition) throw new Error(message); };
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
const get = id => document.getElementById(id);
const allNodes = root => [root, ...Array.from(root.childNodes || []).flatMap(allNodes)];
const ids = ['toast', 'menu-restore', 'footer', 'voice-whole', 'voice-split', 'voice-numeric'];
const roots = ids.map(get);
const originalNodes = roots.map(allNodes);
const filter = get('filter');
const iconMarkup = filter.outerHTML;
let clicks = 0;
get('menu-restore').addEventListener('click', () => { clicks++; });
get('footer-restore').addEventListener('click', () => { clicks++; });
document.addEventListener('DOMContentLoaded', async () => {
  const result = get('icon-repair-result');
  try {
    await tick();
    const checkNodes = () => roots.forEach((root, index) => {
      const current = allNodes(root);
      ensure(current.length === originalNodes[index].length &&
             current.every((node, nodeIndex) => node === originalNodes[index][nodeIndex]), ids[index] + ': nodes replaced');
    });
    const checkArchive = () => {
      ensure(get('toast').textContent === '在侧边栏的筛选菜单中查看已归档对话。', 'toast translation incorrect');
      ensure(get('filter') === filter && filter.outerHTML === iconMarkup, 'filter icon changed');
      ensure(get('menu-label').textContent === '取消归档', 'menu restore not translated');
      ensure(get('footer-label').textContent === '取消归档', 'footer restore not translated');
      ensure(get('footer-text').textContent === '此对话已归档。', 'footer message incorrect');
      ensure(get('menu-restore').getAttribute('aria-label') === '取消归档' &&
             get('footer-restore').title === '取消归档', 'restore metadata incorrect');
    };
    checkArchive();
    checkNodes();
    for (const id of ['plain', 'unrelated-button', 'code', 'editable']) ensure(get(id).textContent === 'Restore', id + ': unrelated restore translated');
    ensure(get('unknown').textContent === 'View archived in the sidebar ( menu tomorrow).', 'unreviewed toast modified');
    ensure(get('unrelated-duration').textContent === '12秒前', 'existing relative-time behavior changed');
    ensure(get('voice-whole').textContent === '语音对话 · 17:00 · 9 秒', 'whole voice record incorrect');
    ensure(get('voice-split').textContent === '语音对话 · 09:05 · 12 秒', 'split voice record incorrect');
    ensure(get('voice-numeric').textContent === '语音对话 · 23:59 · 9 秒', 'numeric voice record incorrect');
    get('toast-prefix').firstChild.textContent = 'View archived in the sidebar (';
    get('toast-suffix').firstChild.textContent = ' menu).';
    get('menu-label').firstChild.textContent = 'Restore';
    get('footer-label').firstChild.textContent = 'Restore';
    get('voice-whole').firstChild.textContent = 'Voice chat · 18:01 · 0s';
    get('time').firstChild.textContent = '10:06';
    get('duration').firstChild.textContent = '23.5s';
    get('seconds').firstChild.textContent = '71';
    get('unit').firstChild.textContent = 's';
    await tick();
    checkArchive();
    checkNodes();
    ensure(get('voice-whole').textContent === '语音对话 · 18:01 · 0 秒', 'whole voice update incorrect');
    ensure(get('voice-split').textContent === '语音对话 · 10:06 · 23.5 秒', 'split voice update incorrect');
    ensure(get('voice-numeric').textContent === '语音对话 · 23:59 · 71 秒', 'numeric voice update incorrect');
    get('menu-restore').click();
    get('footer-restore').click();
    ensure(clicks === 2, 'restore actions changed');
    result.textContent = JSON.stringify({ok: true, checks: 'archive context, icons, controls, split durations, node identity, updates'});
  } catch (error) {
    result.textContent = JSON.stringify({ok: false, error: error.message});
  }
});
"""


@unittest.skipUnless(BROWSER, 'Chrome or Edge is required for the isolated DOM test')
class ArchiveLocalizationTests(unittest.TestCase):
    def test_archive_context_and_voice_updates_preserve_nodes_and_actions(self):
        run_dom_check(self, FIXTURES, CHECKS)


if __name__ == '__main__':
    unittest.main()
