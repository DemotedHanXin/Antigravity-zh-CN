"""Verify cloud notice wording and preserve the original policy links in a real DOM."""
import html
import json
import unittest

from test_icon_repair import BROWSER, run_dom_check


SENTENCES = [
    'Avoid uploading highly sensitive data and verify actions taken by your agent.',
    'Make sure you have the necessary rights to any content or files that you upload, including content of minors.',
    "Don't generate content that infringes on others' rights, including content that deceives, harasses, or harms.",
    "When using Antigravity, you must comply with Google's Prohibited Use Policy.",
    'Your use is subject to the Google Antigravity Terms of Service and Google Privacy Policy.',
]
TRANSLATED = [
    '避免上传高度敏感的数据，并核实智能体执行的操作。',
    '确保您对上传的任何内容或文件（包括涉及未成年人的内容）拥有必要权利。',
    '请勿生成侵犯他人权利的内容，包括具有欺骗、骚扰或伤害性质的内容。',
    '使用 Antigravity 时，您必须遵守 Google 的《禁止使用政策》。',
    '您的使用行为受《Google Antigravity 服务条款》和《Google 隐私权政策》约束。',
]
LINKED = r"""
Avoid uploading highly sensitive data and verify actions taken by your agent. Make sure you have the
<a data-policy="rights" href="https://example.test/rights?ref=cloud&amp;mode=preview#read" target="_blank" rel="noopener"> <span>necessary</span> rights </a>
to any content or files that you upload, including content of minors. Don't generate content that infringes on others' rights, including content that deceives, harasses, or harms. When using Antigravity, you must comply with Google's
<a data-policy="prohibited" href="https://example.test/prohibited#policy" target="_blank">Prohibited Use Policy</a>.
Your use is subject to the <a data-policy="terms" href="https://example.test/terms?version=1" target="_blank">Google Antigravity Terms of Service</a>
and <a data-policy="privacy" href="https://example.test/privacy?hl=en" target="_blank">Google Privacy Policy</a>.
"""

CHECKS = r"""
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
const ensure = (condition, message) => { if (!condition) throw new Error(message); };
const allNodes = root => [root, ...Array.from(root.childNodes || []).flatMap(allNodes)];
const notice = document.getElementById('linked');
const sourceMarkup = notice.innerHTML;
const before = allNodes(notice);
const prefix = notice.firstChild;
const sourcePrefix = prefix.textContent;
const links = Array.from(notice.querySelectorAll('a'));
const attributes = links.map(link => ['href', 'target', 'rel', 'data-policy'].map(name => link.getAttribute(name)));
let clicks = 0;
links.forEach(link => link.addEventListener('click', event => { event.preventDefault(); clicks++; }));
document.addEventListener('DOMContentLoaded', async () => {
  const result = document.getElementById('icon-repair-result');
  try {
    await tick();
    for (const id of ['linked', 'plain', 'mixed']) {
      ensure(document.getElementById(id).textContent === EXPECTED, id + ': wrong translation');
    }
    const after = allNodes(notice);
    ensure(before.length === after.length && before.every((node, index) => node === after[index]), 'existing nodes replaced');
    const checkLinks = () => links.forEach((link, index) => {
      ensure(link === notice.querySelectorAll('a')[index], 'link replaced');
      ensure(JSON.stringify(['href', 'target', 'rel', 'data-policy'].map(name => link.getAttribute(name))) === JSON.stringify(attributes[index]), 'link attributes changed');
    });
    checkLinks();
    ensure(document.getElementById('code').textContent === ORIGINAL, 'code sample translated');
    ensure(document.getElementById('unrelated').textContent === 'and .', 'generic fragments modified');
    prefix.textContent = sourcePrefix;
    await tick();
    ensure(notice.textContent === EXPECTED, 'partial text update not repaired');
    links[0].firstChild.textContent = 'necessary rights';
    await tick();
    ensure(notice.textContent === EXPECTED, 'partial link update not repaired');
    checkLinks();
    const added = document.createElement('div');
    added.innerHTML = sourceMarkup;
    document.body.appendChild(added);
    await tick();
    ensure(added.textContent === EXPECTED && added.querySelectorAll('a').length === 4, 'new notice not translated');
    links.forEach(link => link.click());
    ensure(clicks === 4, 'link handlers changed');
    const finalNodes = allNodes(notice);
    ensure(before.length === finalNodes.length && before.every((node, index) => node === finalNodes[index]), 'nodes replaced on update');
    result.textContent = JSON.stringify({ok: true, checks: 'word order, links, attributes, handlers, nodes, updates, code'});
  } catch (error) {
    result.textContent = JSON.stringify({ok: false, error: error.message});
  }
});
"""


@unittest.skipUnless(BROWSER, 'Chrome or Edge is required for the isolated DOM test')
class CloudResourceNoticeTests(unittest.TestCase):
    def test_linked_notice_preserves_urls_handlers_and_text_nodes(self):
        original = ' '.join(SENTENCES)
        expected = ''.join(TRANSLATED)
        mixed = LINKED.replace('>Prohibited Use Policy<', '>禁止使用政策<').replace(
            '>Google Privacy Policy<', '>Google 隐私权政策<')
        fixtures = ('<div id="linked">' + LINKED + '</div>' +
                    '<div id="plain">' + html.escape(original) + '</div>' +
                    '<div id="mixed">' + mixed + '</div>' +
                    '<pre><code id="code">' + html.escape(original) + '</code></pre>' +
                    '<span id="unrelated">and .</span><pre id="icon-repair-result"></pre>')
        checks = ('const ORIGINAL = ' + json.dumps(original) + ';\n' +
                  'const EXPECTED = ' + json.dumps(expected) + ';\n' + CHECKS)
        run_dom_check(self, fixtures, checks)


if __name__ == '__main__':
    unittest.main()
