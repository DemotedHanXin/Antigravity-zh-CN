"""Static catalog extraction parity and source/frozen resource checks."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from source_paths import LOCALIZATION, ROOT
import builtin_dictionary as builtin
import translation_integration as bridge


BASELINE = json.loads((ROOT / 'tests/fixtures/builtin-baseline.json').read_text(encoding='utf-8'))
NODE = shutil.which('node')


def load_patcher():
    spec = importlib.util.spec_from_file_location('builtin_test_patcher', LOCALIZATION / 'Antigravity-Patcher.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_digest(value):
    data = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


class BuiltinCatalogTests(unittest.TestCase):
    def test_static_groups_match_recorded_m1_javascript_values(self):
        catalog = builtin.load_builtin_catalog()
        for group, record in BASELINE['groups'].items():
            with self.subTest(group=group):
                self.assertEqual(len(catalog[group]), record['effectiveCount'])
                self.assertEqual(canonical_digest(catalog[group]), record['sha256'])

    def test_original_duplicate_definitions_keep_the_last_value(self):
        entries = builtin.load_builtin_dictionary()
        record = BASELINE['groups']['dictionary']
        repeated = record['duplicateDefinitions']
        self.assertEqual(len(repeated), 7)
        self.assertEqual(record['definitionCount'], 683)
        self.assertEqual(len(entries), 676)
        self.assertEqual(sum(len(values) - 1 for values in repeated.values()), 7)
        for key, values in repeated.items():
            self.assertEqual(entries[key], values[-1])

    def test_loader_returns_fresh_data_without_mutating_bundled_entries(self):
        entries = builtin.load_builtin_dictionary()
        entries['Save'] = 'changed by a prospective dictionary view'
        self.assertEqual(builtin.load_builtin_dictionary()['Save'], '保存')
        first = builtin.load_builtin_catalog()
        first['textPrefixRules'][0][1] = 'changed'
        self.assertNotEqual(builtin.load_builtin_catalog()['textPrefixRules'][0][1], 'changed')

    def test_loader_rejects_invalid_schema_and_non_string_data(self):
        original = builtin.load_builtin_catalog()
        invalid = []
        for version in (True, 2):
            value = copy.deepcopy(original)
            value['schemaVersion'] = version
            invalid.append(value)
        value = copy.deepcopy(original)
        del value['dictionary']
        invalid.append(value)
        value = copy.deepcopy(original)
        value['unknown'] = {}
        invalid.append(value)
        for group in builtin.MAPPING_GROUPS:
            value = copy.deepcopy(original)
            value[group] = {'Save': 42}
            invalid.append(value)
        for rules in ({}, [], [['only one']], [['source', 'target', 'extra']], [['source', None]]):
            value = copy.deepcopy(original)
            value['textPrefixRules'] = rules
            invalid.append(value)
        with tempfile.TemporaryDirectory(prefix='builtin-catalog-') as directory:
            path = Path(directory) / 'invalid.json'
            for index, value in enumerate(invalid):
                with self.subTest(case=index):
                    path.write_text(json.dumps(value), encoding='utf-8')
                    with self.assertRaises(ValueError):
                        builtin.load_builtin_catalog(path)

    def test_catalog_rejects_new_duplicate_keys_instead_of_shadowing(self):
        small = {'schemaVersion': 1, 'dictionary': {'Save': '保存'},
                 'coreWords': {'save': '保存'}, 'textPrefixRules': [['prefix', '前缀']],
                 'menuTranslationMap': {'File': '文件'}}
        encoded = json.dumps(small, ensure_ascii=False)
        duplicate = encoded.replace('"dictionary": {', '"dictionary": {"Save": "旧值",', 1)
        with tempfile.TemporaryDirectory(prefix='builtin-catalog-') as directory:
            path = Path(directory) / 'duplicate.json'
            path.write_text(duplicate, encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '重复键'):
                builtin.load_builtin_catalog(path)

    def test_source_catalog_does_not_depend_on_working_directory(self):
        script = """
import json, sys
sys.path.insert(0, sys.argv[1])
from builtin_dictionary import load_builtin_dictionary
entries = load_builtin_dictionary()
print(json.dumps([len(entries), entries['Save']]))
"""
        with tempfile.TemporaryDirectory(prefix='builtin-cwd-') as directory:
            result = subprocess.run([sys.executable, '-B', '-c', script, str(LOCALIZATION)],
                                    cwd=directory, capture_output=True, text=True,
                                    encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [676, '保存'])

    def test_frozen_catalog_is_embedded_and_missing_bundle_never_uses_source(self):
        catalog = builtin.load_builtin_catalog()
        catalog['dictionary']['Save'] = '来自包内资源'
        with tempfile.TemporaryDirectory(prefix='builtin-frozen-') as directory:
            resources = Path(directory) / 'localization_runtime'
            resources.mkdir()
            bundled = resources / builtin.BUILTIN_FILENAME
            bundled.write_text(json.dumps(catalog), encoding='utf-8')
            with mock.patch.object(bridge.sys, '_MEIPASS', directory, create=True):
                self.assertEqual(builtin.load_builtin_dictionary()['Save'], '来自包内资源')
                patcher = load_patcher()
                self.assertIn(json.dumps('来自包内资源', ensure_ascii=False), patcher.DOM_TRANSLATOR_INJECTION)
                bundled.unlink()
                with self.assertRaises(FileNotFoundError):
                    builtin.load_builtin_catalog()
                with self.assertRaises(FileNotFoundError):
                    load_patcher()

    def test_legacy_and_verified_injections_retain_dictionary_and_rule_hooks(self):
        patcher = load_patcher()
        profile = json.loads((ROOT / 'src' / 'localization_runtime/compatibility.json').read_text(encoding='utf-8'))['profiles'][0]
        legacy = patcher.build_dom_injection()
        reviewed = patcher.build_dom_injection(profile)
        for source in (legacy, reviewed):
            self.assertIn('const dictionary = {', source)
            self.assertIn('function translateText(text)', source)
            self.assertNotIn('__BUILTIN_', source)
        self.assertIn('const observer = new MutationObserver', legacy)
        self.assertNotIn('const observer = new MutationObserver', reviewed)
        self.assertNotIn('__BUILTIN_', patcher.MENU_TRANSLATOR_INJECTION)


@unittest.skipUnless(NODE, 'Node required for JavaScript parity checks')
class BuiltinJavascriptParityTests(unittest.TestCase):
    def run_javascript(self, script, payload):
        result = subprocess.run([NODE, '-e', script], input=json.dumps(payload),
                                capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_generated_javascript_data_matches_the_original_literal_hashes(self):
        patcher = load_patcher()
        result = self.run_javascript("""
const vm = require('node:vm');
const payload = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const dom = {};
vm.runInNewContext(payload.dom.split('  function translateText', 1)[0] +
  'globalThis.result = {dictionary, coreWords, textPrefixRules};})();', dom, {timeout:1000});
const menu = {};
vm.runInNewContext(payload.menu.split('  function translateMenu', 1)[0] +
  'globalThis.result = menuTranslationMap;})();', menu, {timeout:1000});
process.stdout.write(JSON.stringify({...dom.result, menuTranslationMap: menu.result}));
""", {'dom': patcher.DOM_TRANSLATOR_INJECTION, 'menu': patcher.MENU_TRANSLATOR_INJECTION})
        for name, record in BASELINE['groups'].items():
            self.assertEqual(canonical_digest(result[name]), record['sha256'], name)

    def test_embedded_quotes_line_separators_and_marker_text_remain_data(self):
        patcher = load_patcher()
        catalog = builtin.load_builtin_catalog()
        unusual = '\"; globalThis.executed = true; //\u2028\u2029__BUILTIN_coreWords__'
        catalog['dictionary']['Save'] = unusual
        source = patcher._render_builtin_data('globalThis.value = __BUILTIN_dictionary__;', catalog)
        self.assertNotIn('\u2028', source)
        self.assertNotIn('\u2029', source)
        result = self.run_javascript("""
const vm = require('node:vm');
const source = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const context = {};
vm.runInNewContext(source, context, {timeout:1000});
process.stdout.write(JSON.stringify({value:context.value.Save, executed:context.executed === true}));
""", source)
        self.assertEqual(result, {'value': unusual, 'executed': False})

    def test_exact_prefix_regex_and_coreword_results_match_m1(self):
        patcher = load_patcher()
        result = self.run_javascript("""
const vm = require('node:vm');
const payload = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const context = {};
vm.runInNewContext(payload.source.split('  const observer = new MutationObserver', 1)[0] +
  'globalThis.translate = translateText;})();', context, {timeout:1000});
process.stdout.write(JSON.stringify(payload.cases.map(text => ({text, value: context.translate(text)}))));
""", {'source': patcher.DOM_TRANSLATOR_INJECTION,
       'cases': [case['text'] for case in BASELINE['translationCases']]})
        self.assertEqual(result, BASELINE['translationCases'])

    def test_native_menu_recursion_retains_static_translations(self):
        patcher = load_patcher()
        result = self.run_javascript("""
const vm = require('node:vm');
const payload = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const Menu = {buildFromTemplate(template) { return template; }};
vm.runInNewContext(payload, {require: () => ({Menu})}, {timeout:1000});
const template = [{label:'File', submenu:[{label:'New Conversation'}]},
  {label:'Edit', submenu:{items:[{label:'Copy'},{label:'Unknown entry'}]}}];
process.stdout.write(JSON.stringify(Menu.buildFromTemplate(template)));
""", patcher.MENU_TRANSLATOR_INJECTION)
        self.assertEqual(result, [
            {'label': '文件', 'submenu': [{'label': '新建对话'}]},
            {'label': '编辑', 'submenu': {'items': [{'label': '复制'}, {'label': 'Unknown entry'}]}},
        ])


if __name__ == '__main__':
    unittest.main()
