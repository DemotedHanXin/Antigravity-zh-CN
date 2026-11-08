"""Run dynamic UI translations in Node without importing or launching the app."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import unittest


PATCHER = Path(__file__).resolve().parents[1] / 'src' / 'Antigravity-Patcher.py'
NODE = shutil.which('node')
RUNNER = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = vm.createContext({
  Node: { TEXT_NODE: 3, ELEMENT_NODE: 1 },
  MutationObserver: class { observe() {} },
  document: { addEventListener() {} }
});
vm.runInContext(input.script, context, { timeout: 1000 });
if (input.extraRules) context.marketplaceDescriptionRules.push(...input.extraRules);
function makeElement(children, protectedContent = false) {
  const element = {
    nodeType: 1, tagName: 'DIV',
    childNodes: children.map(child => Array.isArray(child) ? makeElement(child, protectedContent) :
      { nodeType: 3, textContent: child }),
    closest() { return protectedContent ? element : null; },
    querySelector() { return null; }
  };
  element.childNodes.forEach(child => { child.parentElement = element; });
  Object.defineProperty(element, 'textContent', {
    get() { return element.childNodes.map(child => child.textContent).join(''); }
  });
  return element;
}
function allNodes(root) {
  return [root, ...Array.from(root.childNodes || []).flatMap(allNodes)];
}
const results = input.domTrees ? input.domTrees.map(fixture => {
  const root = makeElement(fixture.children, fixture.protectedContent);
  const before = allNodes(root);
  context.processNode(root);
  const firstText = root.textContent;
  context.processNode(root);
  const after = allNodes(root);
  return {
    text: root.textContent,
    stable: root.textContent === firstText,
    sameNodes: before.length === after.length && before.every((node, index) => node === after[index])
  };
}) : input.texts.map(text => context.translateText(text));
process.stdout.write(JSON.stringify(results));
"""


@unittest.skipUnless(NODE, 'Node.js is required to execute the injected translator')
class TranslationEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module = ast.parse(PATCHER.read_text(encoding='utf-8'))
        injection = next(ast.literal_eval(statement.value) for statement in module.body
                         if isinstance(statement, ast.Assign) and any(
                             isinstance(target, ast.Name) and target.id == 'DOM_TRANSLATOR_INJECTION'
                             for target in statement.targets))
        # Export the real function only in this isolated VM, leaving the shipped code intact.
        before, after = injection.rsplit('})();', 1)
        cls.script = before + ('\nglobalThis.translateText = translateText;'
                               '\nglobalThis.processNode = processNode;'
                               '\nglobalThis.marketplaceDescriptionRules = marketplaceDescriptionRules;\n})();') + after

    def translate(self, *texts, extra_rules=()):
        result = subprocess.run(
            [NODE, '-e', RUNNER],
            input=json.dumps({'script': self.script, 'texts': texts, 'extraRules': extra_rules},
                             ensure_ascii=False),
            capture_output=True, text=True, encoding='utf-8', timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_remaining_percentage_values_and_surrounding_whitespace(self):
        self.assertEqual(
            self.translate('100% left', '0% left', '7.5% left', '  99.25% left\n'),
            ['剩余 100%', '剩余 0%', '剩余 7.5%', '  剩余 99.25%\n'],
        )

    def test_connector_count_values_and_partial_translation(self):
        results = self.translate('0 on for this conversation', '1 on for this conversation',
                                 '27 on for this conversation', '  12 on for this conversation\n',
                                 '3 开 for this conversation')
        self.assertEqual(results, ['本次对话已启用 0 个', '本次对话已启用 1 个', '本次对话已启用 27 个',
                                   '  本次对话已启用 12 个\n', '本次对话已启用 3 个'])
        self.assertEqual(self.translate(*results), results)
        unrelated = ['on for this conversation', '0 on for this conversation tomorrow',
                     '-1 on for this conversation']
        self.assertEqual(self.translate(*unrelated), unrelated)

    def test_voice_and_model_templates_preserve_names_and_wrapped_dictionary_text(self):
        voices = ['Fola', 'Arlo', 'Cleo', 'Finn', 'Gero', 'Lora', 'Neno', 'Olin', 'Tari']
        lists = ['Claude Opus, Claude Sonnet, GPT-OSS', 'Gemini Flash, Gemini Pro',
                 "Custom $& $` $' $1,\n  Other Model"]
        originals = ['  Use ' + voice + '\n' for voice in voices]
        originals += ['Models within this group: ' + names for names in lists]
        originals += [' \nThe voice used in Voice mode.\n  Powered by Gemini Live.\t']
        expected = ['  使用 ' + voice + '\n' for voice in voices]
        expected += ['本组包含的模型：' + names for names in lists]
        expected += [' \n语音模式使用的音色。由 Gemini Live 提供支持。\t']
        self.assertEqual(self.translate(*originals), expected)
        self.assertEqual(self.translate(*expected), expected)
        unchanged = voices + ['Use Custom', 'Use Fola for another task', 'Use',
                              'Models within this group without a colon',
                              'The voice used in Voice mode. Powered by a custom service.']
        self.assertEqual(self.translate(*unchanged), unchanged)

    def test_shortcut_tooltips_preserve_bindings_without_translating_prose(self):
        cases = [
            ('Select Project', '选择项目', ' Ctrl+;'),
            ('Select Project', '选择项目', ' Ctrl+:'),
            ('Select Project', '选择项目', ' (Ctrl+Shift+;)'),
            ('Select Project', '选择项目', ' ⌘;'),
            ('Search Conversations', '搜索对话', ' Ctrl+K'),
            ('Search Conversations', '搜索对话', ' Ctrl + Shift + K'),
            ('Send Message', '发送消息', ' Enter'),
            ('Send Message', '发送消息', ' Ctrl+Enter'),
            ('Send message', '发送消息', ' Alt+Enter'),
            ('Quote', '引用', ' Ctrl+L'),
            ('Quote', '引用', ' (Ctrl+Shift+L)'),
            ('Stop Recording', '停止录音', ' Ctrl+M'),
            ('Stop Recording', '停止录音', ' ⌘M'),
            ('Mute mic', '将麦克风静音', ' (Alt+M)'),
            ('Mute Antigravity', '将 Antigravity 静音', ' (Alt+Shift+M)'),
        ]
        results = self.translate(*(label + shortcut for label, _, shortcut in cases))
        self.assertEqual(results, [translated + shortcut for _, translated, shortcut in cases])
        self.assertEqual(self.translate(*results), results)
        prose = ['Select Project from the list', 'Send Message Enter when ready',
                 'Search Conversations Ctrl+K in another window', 'Quote this message',
                 'Stop Recording Ctrl+M when finished', 'Mute mic for this task']
        self.assertEqual(self.translate(*prose), prose)

    def test_voice_speed_tooltips_preserve_dynamic_values(self):
        speeds = ['0.5', '1', '1.25', '1.5', '2', '10']
        originals = ['Voice speed, ' + speed + 'x' for speed in speeds]
        expected = ['语速，' + speed + 'x' for speed in speeds]
        self.assertEqual(self.translate(*originals), expected)
        self.assertEqual(self.translate(*expected), expected)
        self.assertEqual(self.translate(' \nVoice speed,\t1.5x\n'), [' \n语速，1.5x\n'])
        unchanged = ['Voice speed, fast', 'Voice speed, 1x today', 'Voice speed, -1x',
                     '1.5x', 'Voice speed in another app']
        self.assertEqual(self.translate(*unchanged), unchanged)

    def test_delete_description_preserves_names_counts_and_replacement_metacharacters(self):
        names_and_counts = [
            ('Antigravity_Work', 1),
            ('中文 项目 including release.2', 23),
            ("Release $& $` $' $1", 0),
        ]
        originals, expected = [], []
        for name, count in names_and_counts:
            noun = 'conversation' if count == 1 else 'conversations'
            originals.append(f'Permanently delete {name} including {count} active {noun}.')
            expected.append(f'永久删除{name}，包括 {count} 个进行中的对话。')
        self.assertEqual(self.translate(*originals), expected)

    def test_delete_description_handles_active_and_archived_counts(self):
        cases = [('Antigravity_Work', 1, 1), ('中文项目 including release.2', 0, 23),
                 ("Release $& $` $' $1", 17, 0)]
        originals, expected = [], []
        for name, active, archived in cases:
            active_noun = 'conversation' if active == 1 else 'conversations'
            archived_noun = 'conversation' if archived == 1 else 'conversations'
            counts = f'{active} active {active_noun} and {archived} archived {archived_noun}.'
            originals.extend([f'Permanently delete {name} including {counts}',
                              f'永久删除 {name} 包括{counts}'])
            expected.extend([f'永久删除 {name}，包括 {active} 个进行中的对话和 {archived} 个已归档对话。'] * 2)
        self.assertEqual(self.translate(*originals), expected)
        self.assertEqual(self.translate(*expected), expected)
        self.assertEqual(self.translate('1 active conversation and 12 archived conversations.',
                                       '0 archived conversations'),
                         ['1 个进行中的对话和 12 个已归档对话。', '0 个已归档对话'])

    def test_project_delete_dialog_preserves_names_counts_and_mixed_labels(self):
        names = ['Antigravity_Work', '中文 项目', "Release $& $` $' $1", 'Settings']
        originals, expected = [], []
        for name in names:
            originals.extend([f'Are you sure you want to delete the project {name}?',
                              f'Are you sure you want to delete the 项目 {name}?'])
            expected.extend([f'确定要删除项目“{name}”吗？'] * 2)
        for count in [0, 1, 2, 57]:
            noun = 'conversation' if count == 1 else 'conversations'
            originals.extend([f'This will permanently delete {count} active {noun} within it.',
                              f'This will permanently delete {count} 个进行中的对话 within it.'])
            expected.extend([f'这将永久删除其中的 {count} 个进行中的对话。'] * 2)
        self.assertEqual(self.translate(*originals), expected)
        self.assertEqual(self.translate(*expected), expected)
        unrelated = ['Are you sure you want to delete the file sample.txt?',
                     'This will permanently delete 2 files within it.',
                     'This will permanently delete -1 active conversations within it.']
        self.assertEqual(self.translate(*unrelated), unrelated)

    def test_voice_records_preserve_time_separators_and_duration_values(self):
        originals = ['Voice chat · 17:00 · 9s', 'Voice chat·9:05·0s',
                     '语音对话 · 23:59:01 · 91.5s', ' \nVoice chat · 08:15 · 120s\t']
        expected = ['语音对话 · 17:00 · 9 秒', '语音对话·9:05·0 秒',
                    '语音对话 · 23:59:01 · 91.5 秒', ' \n语音对话 · 08:15 · 120 秒\t']
        self.assertEqual(self.translate(*originals), expected)
        self.assertEqual(self.translate(*expected), expected)
        unrelated = ['17:00', 'Voice chat about a project', 'Voice chat · 17:00 · 9s later', 'Restore']
        self.assertEqual(self.translate(*unrelated), unrelated)
        self.assertEqual(self.translate('9s'), ['9秒前'])

    def test_split_and_partially_translated_delete_descriptions(self):
        fragments = ['Permanently delete ', 'Antigravity_Work', ' including ',
                     '1', ' active conversation.']
        self.assertEqual(''.join(self.translate(*fragments)),
                         '永久删除 Antigravity_Work 包括 1 个进行中的对话。')
        self.assertEqual(
            self.translate('Permanently delete 中文项目 包括2 active conversations.',
                           'Permanently delete Release $&', '2 active conversations',
                           '1 active conversation.'),
            ['永久删除中文项目，包括 2 个进行中的对话。',
             '永久删除Release $&', '2 个进行中的对话', '1 个进行中的对话。'],
        )

    def test_translations_are_stable_and_leave_unrelated_values_unchanged(self):
        originals = ['0% left', 'Permanently delete My Project including 2 active conversations.']
        translated = self.translate(*originals)
        self.assertEqual(self.translate(*translated), translated)
        unchanged = ['Gemini 4 Argon', 'Antigravity_Work', 'run-workflow', 'generative_ui',
                     '~/Downloads', 'Ctrl + Shift + T', 'left', '100% left today']
        self.assertEqual(self.translate(*unchanged), unchanged)

    def test_marketplace_descriptions_match_full_truncated_and_wrapped_text(self):
        source = ('Connect Antigravity to your Notion workspace with the Notion MCP server, '
                  'plus skills for research, documentation, meeting prep, specs, trackers, and project updates.')
        expected = ('通过 Notion MCP 服务器将 Antigravity 连接到您的 Notion 工作区，'
                    '并提供研究、文档编写、会议准备、规格说明、跟踪记录和项目动态更新等技能。')
        wrapped = '  \n' + source.replace(' ', ' \n ') + '\t'
        results = self.translate(source, source[:36] + '...', source[:48] + '…', wrapped)
        self.assertEqual(results, [expected, expected, expected, '  \n' + expected + '\t'])
        self.assertEqual(self.translate(*results), results)

    def test_marketplace_truncation_requires_a_specific_and_unique_match(self):
        prefix = 'Connect Antigravity to your Notion'
        ambiguous = prefix + '...'
        extra_rules = [[prefix + ' test extension with different behavior.', '测试说明']]
        self.assertEqual(self.translate(ambiguous, extra_rules=extra_rules), [ambiguous])
        unchanged = ['Build and deploy...', 'Connect Antigravity...', 'Notion', 'Context7',
                     'Search the web for my own question...',
                     'Connect Antigravity to your Notion workspace with custom access']
        self.assertEqual(self.translate(*unchanged), unchanged)

    def test_marketplace_privacy_preserves_links_and_handles_separate_sentences(self):
        sentences = [
            'Google does not control the availability or functionality of third party developer tools.',
            'Your data from third party developer tools connected to your Antigravity instance may be shared with Google.',
            'Google will protect any such data in accordance with the Google Privacy Policy, found here:',
        ]
        translated = [
            'Google 不控制第三方开发者工具的可用性或功能。',
            '您在与 Antigravity 实例连接的第三方开发者工具中的数据可能会与 Google 共享。',
            'Google 将依据 Google 隐私权政策保护此类数据，详见：',
        ]
        url = 'https://policies.google.com/privacy?hl=zh-CN'
        paragraph = ' '.join(sentences) + ' ' + url
        expected = ' '.join(translated) + ' ' + url
        results = self.translate(paragraph, *sentences, url)
        self.assertEqual(results, [expected, *translated, url])
        self.assertEqual(self.translate(*results), results)

    def test_automation_empty_label_handles_split_nodes_without_replacing_them(self):
        fixtures = [
            {'children': ['No automations yet']},
            {'children': ['No', ' automations', ' yet']},
            {'children': ['否 ', ['automations', ' yet']]},
            {'children': ['No ', ['automations'], ' yet']},
            {'children': ['No automations yesterday']},
            {'children': ['No', ' automations yet'], 'protectedContent': True},
        ]
        result = subprocess.run(
            [NODE, '-e', RUNNER],
            input=json.dumps({'script': self.script, 'domTrees': fixtures}, ensure_ascii=False),
            capture_output=True, text=True, encoding='utf-8', timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        results = json.loads(result.stdout)
        self.assertEqual([item['text'] for item in results],
                         ['暂无自动化任务'] * 4 + ['No automations yesterday', 'No automations yet'])
        self.assertTrue(all(item['sameNodes'] and item['stable'] for item in results))


if __name__ == '__main__':
    unittest.main()
