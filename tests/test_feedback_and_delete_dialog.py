"""Verify split dialog variables and changing form metadata without changing input."""
import unittest

from test_icon_repair import BROWSER, run_dom_check


FIXTURES = r"""
<div role="dialog">
  <p id="question">Are you sure you want to delete the <span>项目 </span><strong id="name" data-project="Antigravity_Work">Antigravity_Work</strong>?</p>
  <p id="count">This will permanently delete <span><b id="number">2</b></span> 个进行中的对话 within it.</p>
  <button id="confirm">Delete</button>
</div>
<textarea id="feedback" placeholder="Describe the bug you encountered…">Continue with Google</textarea>
<input id="shortcut" placeholder="Press keys…" value="Ctrl+K">
<span id="metadata" title="Remove Shortcut" aria-label="Add Shortcut"></span>
<pre><code id="code">Are you sure you want to delete the project Example?</code></pre>
<div contenteditable="true" id="editable">This will permanently delete 2 active conversations within it.</div>
<pre id="icon-repair-result"></pre>
"""

CHECKS = r"""
const ensure = (condition, message) => { if (!condition) throw new Error(message); };
const get = id => document.getElementById(id);
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
const allNodes = root => [root, ...Array.from(root.childNodes || []).flatMap(allNodes)];
const questionNodes = allNodes(get('question'));
const countNodes = allNodes(get('count'));
const name = get('name');
const number = get('number').firstChild;
const feedback = get('feedback');
const feedbackText = feedback.firstChild;
let confirms = 0;
get('confirm').addEventListener('click', () => { confirms++; });
document.addEventListener('DOMContentLoaded', async () => {
  const result = get('icon-repair-result');
  try {
    await tick();
    ensure(get('question').textContent === '确定要删除项目“Antigravity_Work”吗？', 'split project question incorrect');
    ensure(get('count').textContent === '这将永久删除其中的 2 个进行中的对话。', 'split count incorrect');
    ensure(feedback.placeholder === '描述您遇到的错误...', 'Unicode placeholder not translated');
    ensure(get('shortcut').placeholder === '请按下快捷键...', 'shortcut placeholder not translated');
    for (const [original, expected] of [
      ['Describe the feature you would like to see...', '描述您希望增加的功能...'],
      ['Describe your auth or billing issue…', '描述您遇到的身份验证或计费问题...'],
      ['Describe your Remote Control issue...', '描述您遇到的远程控制问题...'],
      ['Enter your feedback here…', '在此输入您的反馈...'],
      ['Describe the bug you encountered...', '描述您遇到的错误...']
    ]) {
      feedback.placeholder = original;
      await tick();
      ensure(feedback.placeholder === expected, 'changed feedback type not translated');
      ensure(feedback.value === 'Continue with Google' && feedback.firstChild === feedbackText, 'typed feedback changed');
    }
    get('metadata').title = 'Add Shortcut';
    get('metadata').setAttribute('aria-label', 'Remove Shortcut');
    get('shortcut').placeholder = 'Press keys...';
    name.firstChild.textContent = 'Settings';
    number.textContent = '57';
    await tick();
    ensure(get('question').textContent === '确定要删除项目“Settings”吗？', 'project name translated or update lost');
    ensure(get('count').textContent === '这将永久删除其中的 57 个进行中的对话。', 'count update lost');
    ensure(get('metadata').title === '添加快捷键' && get('metadata').getAttribute('aria-label') === '移除快捷键', 'metadata update not translated');
    ensure(get('shortcut').placeholder === '请按下快捷键...' && get('shortcut').value === 'Ctrl+K', 'shortcut input changed');
    name.firstChild.textContent = "Release $& $` $' $1";
    number.textContent = '0';
    await tick();
    ensure(get('question').textContent === "确定要删除项目“Release $& $` $' $1”吗？", 'special characters corrupted');
    ensure(get('count').textContent === '这将永久删除其中的 0 个进行中的对话。', 'zero count incorrect');
    for (const [root, before] of [[get('question'), questionNodes], [get('count'), countNodes]]) {
      const after = allNodes(root);
      ensure(after.length === before.length && before.every((node, index) => node === after[index]), 'original nodes replaced');
    }
    ensure(get('name') === name && name.tagName === 'STRONG' && name.dataset.project === 'Antigravity_Work', 'project formatting or action data changed');
    ensure(get('code').textContent === 'Are you sure you want to delete the project Example?', 'code translated');
    ensure(get('editable').textContent === 'This will permanently delete 2 active conversations within it.', 'editable text translated');
    get('confirm').click();
    ensure(confirms === 1, 'dialog action changed');
    result.textContent = JSON.stringify({ok: true, checks: 'split variables, names, quantities, changed placeholders, metadata, typed input, nodes, actions'});
  } catch (error) {
    result.textContent = JSON.stringify({ok: false, error: error.message});
  }
});
"""


@unittest.skipUnless(BROWSER, 'Chrome or Edge is required for the isolated DOM test')
class FeedbackAndDeleteDialogTests(unittest.TestCase):
    def test_dialog_variables_and_form_updates_keep_nodes_and_user_input(self):
        run_dom_check(self, FIXTURES, CHECKS)


if __name__ == '__main__':
    unittest.main()
