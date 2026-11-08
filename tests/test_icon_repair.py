"""Exercise icon repair in an isolated Chromium profile, without opening the user's app."""
import ast
import html
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BROWSER = next((path for path in (
    Path(os.environ.get('PROGRAMFILES', r'C:\Program Files')) / 'Google/Chrome/Application/chrome.exe',
    Path(os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe',
) if path.is_file()), None)

FIXTURES = r"""
<style>
  body { background: #293446; color: #dbe2ec; font: 16px Arial; }
  button { color: inherit; background: none; border: 0; font: inherit; }
  .material-symbols-outlined, .material-icons { font: inherit; }
</style>
<button role="menuitem" id="reopen">
  <span class="material-symbols-outlined" id="icon">restore_page</span>
  <span id="caption">Reopen Closed Tab</span>
</button>
<span class="material-icons" id="classic"><span>restore_page</span></span>
<div role="menuitem"><span id="fallback">restore_page</span> 重新打开已关闭的标签页</div>
<span data-icon="restore_page" id="data-icon">restore_page</span>
<div id="plain">restore_page</div>
<pre><code class="material-symbols-outlined" id="code">restore_page</code></pre>
<div contenteditable="true"><span class="material-icons" id="editable">restore_page</span></div>
<span class="material-symbols-outlined" id="different">restore</span>
<pre id="icon-repair-result"></pre>
"""

CHECKS = r"""
const icon = document.getElementById('icon');
const originalText = icon.firstChild;
const button = document.getElementById('reopen');
let clicks = 0;
button.addEventListener('click', () => { clicks++; });
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
const ensure = (condition, message) => { if (!condition) throw new Error(message); };
document.addEventListener('DOMContentLoaded', async () => {
  const result = document.getElementById('icon-repair-result');
  try {
    await tick();
    for (const id of ['icon', 'classic', 'fallback', 'data-icon']) {
      const element = document.getElementById(id);
      const svg = element.querySelector('svg[data-antigravity-icon="restore_page"]');
      ensure(svg && element.textContent.trim() === '', id + ': missing icon or leaked token');
      ensure(svg.namespaceURI === 'http://www.w3.org/2000/svg', id + ': wrong namespace');
      ensure(svg.getAttribute('aria-hidden') === 'true', id + ': decorative icon announced');
      const box = svg.getBoundingClientRect();
      ensure(box.width > 0 && box.height > 0, id + ': invisible icon');
      ensure(svg.querySelector('path').getTotalLength() > 0, id + ': invalid SVG path');
    }
    ensure(icon.firstChild === originalText, 'original text node replaced');
    ensure(document.getElementById('caption').textContent === '重新打开已关闭的标签页', 'caption changed');
    for (const id of ['plain', 'code', 'editable']) {
      const element = document.getElementById(id);
      ensure(element.textContent === 'restore_page' && !element.querySelector('svg'), id + ': protected token modified');
    }
    ensure(document.getElementById('different').textContent === 'restore', 'unrelated icon changed');
    const svg = icon.querySelector('svg');
    originalText.textContent = 'restore_page';
    await tick();
    ensure(icon.querySelectorAll('svg').length === 1 && icon.querySelector('svg') === svg, 'duplicate icon after text update');
    ensure(icon.textContent.trim() === '', 'token reappeared after text update');
    const classic = document.getElementById('classic');
    classic.textContent = 'restore_page';
    await tick();
    ensure(classic.querySelectorAll('svg').length === 1 && classic.textContent.trim() === '', 'rerender not repaired');
    const added = document.createElement('div');
    added.setAttribute('role', 'menuitem');
    added.innerHTML = '<span>restore_page</span><span>Reopen Closed Tab</span>';
    document.body.appendChild(added);
    await tick();
    ensure(added.querySelectorAll('svg').length === 1, 'new menu item not repaired');
    ensure(added.lastChild.textContent === '重新打开已关闭的标签页', 'new caption not translated');
    button.click();
    ensure(clicks === 1 && document.getElementById('reopen') === button, 'menu handler or node changed');
    result.textContent = JSON.stringify({ok: true, checks: 'icons, captions, nodes, updates, handlers, protected text'});
  } catch (error) {
    result.textContent = JSON.stringify({ok: false, error: error.message});
  }
});
"""


def run_dom_check(case, fixtures, checks):
    """Run renderer checks with a disposable profile and the actual injected engine."""
    module = ast.parse((ROOT / 'src/Antigravity-Patcher.py').read_text(encoding='utf-8'))
    injection = next(ast.literal_eval(statement.value) for statement in module.body
                     if isinstance(statement, ast.Assign) and any(
                         isinstance(target, ast.Name) and target.id == 'DOM_TRANSLATOR_INJECTION'
                         for target in statement.targets))
    with tempfile.TemporaryDirectory(prefix='.dom-translation-test-', dir=ROOT) as temporary:
        work = Path(temporary).resolve()
        case.assertEqual(work.parent, ROOT)
        page = work / 'test.html'
        page.write_text('<!doctype html><meta charset="utf-8"><body>' + fixtures +
                        '<script>' + injection + '</script><script>' + checks + '</script>',
                        encoding='utf-8')
        command = [str(BROWSER), '--headless=new', '--disable-gpu',
                   '--disable-crashpad-for-testing',
                   '--disable-background-networking', '--no-first-run', '--no-default-browser-check',
                   '--user-data-dir=' + str(work / 'profile'), '--virtual-time-budget=1500',
                   '--dump-dom', page.as_uri()]
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=30,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        case.assertEqual(result.returncode, 0, result.stderr[-2000:])
        match = re.search(r'<pre id="icon-repair-result">(.*?)</pre>', result.stdout, re.S)
        case.assertIsNotNone(match, 'Browser did not produce a test result')
        report = json.loads(html.unescape(match.group(1)))
        case.assertTrue(report.get('ok'), report)


@unittest.skipUnless(BROWSER, 'Chrome or Edge is required for the isolated DOM test')
class IconRepairTests(unittest.TestCase):
    def test_restore_page_icon_is_repaired_without_changing_menu_or_code(self):
        run_dom_check(self, FIXTURES, CHECKS)


if __name__ == '__main__':
    unittest.main()
