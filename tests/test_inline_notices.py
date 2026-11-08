"""Verify linked UI wording while keeping original actions and text nodes."""
import unittest

from test_icon_repair import BROWSER, run_dom_check


FIXTURES = r"""
<div id="voice">Powered by Gemini Live · You can change this in <button data-action="settings"><span>Settings</span></button> later.</div>
<div id="mixed">Powered by Gemini Live · You can change this in <a href="#settings">设置</a> later.</div>
<div id="role">Powered by Gemini Live · You can change this in <span role="link" tabindex="0">Settings</span> later.</div>
<div id="span">Powered by Gemini Live · You can change this in <span class="settings"><span>Settings</span></span> later.</div>
<div id="terms"><span>By using this app, you agree to its </span><a href="https://example.test/terms?v=1#read" target="_blank" rel="noopener"><span>Terms of Service</span></a></div>
<div id="partial-terms">By using this app, you agree to its <a href="#terms">服务条款</a></div>
<div id="unknown">Powered by Gemini Live · You can change this in <a href="#custom">Settings</a> tomorrow.</div>
<pre><code id="code">Powered by Gemini Live · You can change this in <a href="#code">Settings</a> later.</code></pre>
<div contenteditable="true" id="editable">By using this app, you agree to its <a href="#editable">Terms of Service</a></div>
<div id="unrelated">later.</div>
<pre id="icon-repair-result"></pre>
"""

CHECKS = r"""
const voiceExpected = '由 Gemini Live 提供支持 · 您可以稍后在设置中更改。';
const termsExpected = '使用本应用即表示您同意其服务条款';
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
const ensure = (condition, message) => { if (!condition) throw new Error(message); };
const allNodes = root => [root, ...Array.from(root.childNodes || []).flatMap(allNodes)];
const ids = ['voice', 'mixed', 'role', 'span', 'terms', 'partial-terms'];
const notices = ids.map(id => document.getElementById(id));
const originalNodes = notices.map(allNodes);
const voice = notices[0];
const sourceMarkup = voice.innerHTML;
const controls = [voice.querySelector('button'), notices[1].querySelector('a'),
                  notices[2].querySelector('[role="link"]'), notices[3].querySelector('.settings'),
                  notices[4].querySelector('a'), notices[5].querySelector('a')];
const attributes = controls.map(control => control.getAttributeNames().map(name => [name, control.getAttribute(name)]));
const originals = ['code', 'editable'].map(id => document.getElementById(id).textContent);
let clicks = 0;
controls.forEach(control => control.addEventListener('click', event => { event.preventDefault(); clicks++; }));
document.addEventListener('DOMContentLoaded', async () => {
  const result = document.getElementById('icon-repair-result');
  try {
    await tick();
    const check = () => notices.forEach((notice, index) => {
      ensure(notice.textContent === (index < 4 ? voiceExpected : termsExpected), ids[index] + ': wording incorrect');
      const current = allNodes(notice);
      ensure(current.length === originalNodes[index].length &&
             current.every((node, nodeIndex) => node === originalNodes[index][nodeIndex]), ids[index] + ': nodes replaced');
      ensure(controls[index].isConnected, ids[index] + ': action removed');
      ensure(JSON.stringify(controls[index].getAttributeNames().map(name => [name, controls[index].getAttribute(name)])) ===
             JSON.stringify(attributes[index]), ids[index] + ': action attributes modified');
    });
    check();
    ['code', 'editable'].forEach((id, index) => ensure(document.getElementById(id).textContent === originals[index], id + ': protected text translated'));
    ensure(document.getElementById('unrelated').textContent === 'later.', 'generic suffix translated');
    ensure(document.getElementById('unknown').textContent.endsWith('tomorrow.'), 'unreviewed notice rewritten');
    voice.firstChild.textContent = 'Powered by Gemini Live · You can change this in ';
    controls[0].firstChild.firstChild.textContent = 'Settings';
    voice.lastChild.textContent = ' later.';
    notices[4].firstChild.firstChild.textContent = 'By using this app, you agree to its ';
    await tick();
    check();
    const added = document.createElement('div');
    added.innerHTML = sourceMarkup;
    document.body.appendChild(added);
    await tick();
    ensure(added.textContent === voiceExpected && added.querySelector('button'), 'new notice not translated');
    controls.forEach(control => control.click());
    ensure(clicks === controls.length, 'action handlers changed');
    check();
    result.textContent = JSON.stringify({ok: true, checks: 'split notices, mixed labels, links, spans, actions, nodes, updates, protected text'});
  } catch (error) {
    result.textContent = JSON.stringify({ok: false, error: error.message});
  }
});
"""


@unittest.skipUnless(BROWSER, 'Chrome or Edge is required for the isolated DOM test')
class InlineNoticeTests(unittest.TestCase):
    def test_inline_notices_preserve_links_actions_and_updates(self):
        run_dom_check(self, FIXTURES, CHECKS)


if __name__ == '__main__':
    unittest.main()
