"""Execute the real Electron menu hook against nested native menu fixtures."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import unittest


NODE = shutil.which('node')
PATCHER = Path(__file__).resolve().parents[1] / 'src/Antigravity-Patcher.py'
RUNNER = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const script = JSON.parse(fs.readFileSync(0, 'utf8'));
const ensure = (condition, message) => { if (!condition) throw new Error(message); };
let builds = 0;
const Menu = {buildFromTemplate(template) {
  ensure(this === Menu, 'original receiver changed');
  builds++;
  return {items: template};
}};
const context = vm.createContext({require(name) {
  ensure(name === 'electron', 'unexpected dependency');
  return {Menu};
}, console});
vm.runInContext(script, context, {timeout: 1000});
const hooked = Menu.buildFromTemplate;
vm.runInContext(script, context, {timeout: 1000});
ensure(Menu.buildFromTemplate === hooked, 'menu hook installed twice');
let clicks = 0;
const click = () => { clicks++; };
const name = {id: 'conversation-name', label: 'Conversation Name', click};
const id = {id: 'conversation-id', label: 'Conversation ID', click};
const project = {id: 'project-name', label: 'Project Name', click};
const replace = {id: 'replace', label: 'Replace with New', accelerator: 'Ctrl+Shift+D', click};
const unknown = {id: 'custom', label: 'Custom plugin action', enabled: false};
const template = [{label: 'Copy', submenu: [name, id, project]},
                  {label: 'Split', submenu: {items: [replace, unknown]}}];
const built = Menu.buildFromTemplate(template);
ensure(built.items === template && builds === 1, 'original builder result changed');
ensure(name.label === '对话名称' && id.label === '对话 ID' && project.label === '项目名称' &&
       replace.label === '替换为新建', 'nested labels not translated');
ensure(template[0].submenu[0] === name && template[1].submenu.items[0] === replace, 'menu item replaced');
ensure(replace.accelerator === 'Ctrl+Shift+D' && replace.id === 'replace', 'action values changed');
ensure(unknown.label === 'Custom plugin action' && !unknown.enabled, 'unknown item changed');
for (const item of [name, id, project, replace]) {
  ensure(item.click === click, 'handler replaced');
  item.click();
}
ensure(clicks === 4, 'handlers no longer work');
Menu.buildFromTemplate(template);
ensure(builds === 2 && replace.label === '替换为新建', 'second build is unstable');
process.stdout.write('ok');
"""


@unittest.skipUnless(NODE, 'Node.js is required to execute the menu translator')
class MenuTranslationTests(unittest.TestCase):
    def test_native_submenus_keep_actions_and_builder_behavior(self):
        module = ast.parse(PATCHER.read_text(encoding='utf-8'))
        injection = next(ast.literal_eval(statement.value) for statement in module.body
                         if isinstance(statement, ast.Assign) and any(
                             isinstance(target, ast.Name) and target.id == 'MENU_TRANSLATOR_INJECTION'
                             for target in statement.targets))
        result = subprocess.run([NODE, '-e', RUNNER], input=json.dumps(injection),
                                capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'ok')


if __name__ == '__main__':
    unittest.main()
