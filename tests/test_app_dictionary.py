"""Personal dictionaries are data, preserve originals, and reach real injection."""
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import sys
import unittest
from unittest import mock

from app.dictionary import DictionaryStore, load_builtin, validate_document
from app.storage import atomic_write_json
from app.storage import parse_json
from test_localization import PATCHER, make_archive
from test_icon_repair import BROWSER, run_dom_check


def document(*entries):
    return {'schemaVersion': 1, 'revision': 0, 'entries': list(entries)}


def entry(source, target='译文', scope='ui', enabled=True):
    return dict(source=source, target=target, scope=scope, enabled=enabled)


class DictionaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.dictionary-test-', dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = DictionaryStore(self.root)

    def test_builtin_catalog_matches_literal_cli_maps(self):
        for scope, name, script in [('ui', 'dictionary', PATCHER.DOM_TRANSLATOR_INJECTION),
                                    ('menu', 'menuTranslationMap', PATCHER.MENU_TRANSLATOR_INJECTION)]:
            body = script.split('const ' + name + ' = {', 1)[1].split('\n  };', 1)[0]
            pattern = r'''("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')\s*:\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')'''
            expected = {ast.literal_eval(a): ast.literal_eval(b) for a, b in re.findall(pattern, body)}
            self.assertEqual({e['source']: e['target'] for e in load_builtin() if e['scope'] == scope}, expected)

    def test_overlay_scope_revision_restore_and_snapshot_copy(self):
        self.store.set_entry('ui', 'Settings', '配置', False)
        self.store.set_entry('menu', 'Settings', '菜单配置')
        self.assertEqual(self.store.revision, 2)
        merged = {(e['scope'], e['source']): e for e in self.store.entries()}
        self.assertEqual(merged['ui', 'Settings']['origin'], 'override')
        self.assertFalse(merged['ui', 'Settings']['enabled'])
        self.assertEqual(merged['menu', 'Settings']['origin'], 'custom')
        copied = self.store.snapshot()
        copied['entries'].clear()
        self.assertEqual(len(self.store.snapshot()['entries']), 2)
        self.store.reset_entry('ui', 'Settings')
        merged = {(e['scope'], e['source']): e for e in DictionaryStore(self.root).entries()}
        self.assertEqual(merged['ui', 'Settings']['target'], '设置')
        self.assertEqual(merged['ui', 'Settings']['origin'], 'builtin')

    def test_failed_atomic_save_does_not_change_file_or_revision(self):
        self.store.set_entry('ui', 'A', '甲')
        before = self.store.path.read_bytes()
        with mock.patch('app.storage.os.replace', side_effect=PermissionError('locked')):
            with self.assertRaises(PermissionError):
                self.store.set_entry('ui', 'A', '乙')
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual(self.store.revision, 1)
        self.assertFalse(list(self.root.glob('*.tmp')))

    def test_corruption_preserved_and_explicit_recovery(self):
        self.store.path.write_text('{broken', encoding='utf-8')
        broken = DictionaryStore(self.root)
        self.assertTrue(broken.error)
        self.assertGreater(len(broken.entries()), 900)
        with self.assertRaises(ValueError):
            broken.set_entry('ui', 'A', '甲')
        with self.assertRaises(ValueError):
            broken.snapshot()
        self.assertEqual(broken.path.read_text(), '{broken')
        imported = self.root / 'valid.json'
        atomic_write_json(imported, document(entry('A', '甲')))
        broken.recover_from_import(imported)
        self.assertFalse(broken.error)
        preserved = list(self.root.glob('*.corrupt-*'))
        self.assertEqual(len(preserved), 1)
        self.assertEqual(preserved[0].read_text(), '{broken')
        self.assertEqual(broken.snapshot()['entries'][0]['source'], 'A')

    def test_oversized_corrupt_dictionary_can_be_recovered_without_discarding_original(self):
        content = b'x' * (4 * 1024 * 1024 + 1)
        self.store.path.write_bytes(content)
        broken = DictionaryStore(self.root)
        self.assertTrue(broken.error)
        imported = self.root / 'valid.json'
        atomic_write_json(imported, document(entry('A', '甲')))
        broken.recover_from_import(imported)
        self.assertEqual(next(self.root.glob('*.corrupt-*')).read_bytes(), content)
        self.assertFalse(broken.error)

    def test_stale_window_cannot_overwrite_newer_dictionary(self):
        other = DictionaryStore(self.root)
        self.store.set_entry('ui', 'A', '甲')
        with self.assertRaisesRegex(ValueError, '另一个窗口'):
            other.set_entry('ui', 'B', '乙')

    def test_load_uses_one_snapshot_even_when_file_changes_during_parse(self):
        self.store.set_entry('ui', 'A', '甲')
        newer = validate_document(document(entry('B', '乙')))
        def change_after_read(raw):
            atomic_write_json(self.store.path, newer)
            return parse_json(raw)
        with mock.patch('app.dictionary.parse_json', side_effect=change_after_read):
            loaded = DictionaryStore(self.root)
        self.assertEqual(loaded.snapshot()['entries'][0]['source'], 'A')
        with self.assertRaisesRegex(ValueError, '另一个窗口'):
            loaded.set_entry('ui', 'C', '丙')
        self.assertEqual(DictionaryStore(self.root).snapshot()['entries'][0]['source'], 'B')

    def test_other_process_lock_blocks_save_without_losing_data(self):
        script = "from app.storage import file_lock; import sys;\nwith file_lock(sys.argv[1]):\n print('locked',flush=True)\n sys.stdin.readline()"
        process = subprocess.Popen([sys.executable, '-B', '-c', script, str(self.store.path.with_suffix('.lock'))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
            cwd=Path(__file__).resolve().parents[1])
        try:
            self.assertEqual(process.stdout.readline().strip(), 'locked')
            with self.assertRaisesRegex(ValueError, '正在保存'):
                self.store.set_entry('ui', 'A', '甲')
            self.assertFalse(self.store.path.exists())
        finally:
            process.communicate('\n', timeout=10)
        self.store.set_entry('ui', 'A', '甲')
        self.assertEqual(self.store.revision, 1)

    def test_editor_save_preserves_imported_metadata(self):
        self.store.import_data(document(dict(entry('A', '甲'), category='自用', note='保留这个说明')))
        self.store.set_entry('ui', 'A', '新甲')
        saved = self.store.snapshot()['entries'][0]
        self.assertEqual((saved['category'], saved['note']), ('自用', '保留这个说明'))

    def test_import_preview_and_explicit_conflict_resolution(self):
        self.store.set_entry('ui', 'A', '甲')
        incoming = document(entry('A', '新甲'), entry('B', '乙'))
        path = self.root / 'import.json'
        atomic_write_json(path, incoming)
        preview = self.store.preview_import(path)
        self.assertEqual(preview['added'], 1)
        self.assertEqual(len(preview['conflicts']), 1)
        self.assertEqual(self.store.import_data(preview['data'], 'keep'), 1)
        self.assertEqual(self.store.snapshot()['entries'][0]['target'], '甲')
        self.assertEqual(self.store.import_data(incoming, 'overwrite'), 1)
        self.assertEqual(self.store.snapshot()['entries'][0]['target'], '新甲')
        exported = self.root / 'export.json'
        self.store.export(exported)
        self.assertEqual(json.loads(exported.read_text(encoding='utf-8')), self.store.snapshot())

    def test_invalid_documents_are_rejected(self):
        cases = [document(entry('A'), entry('A')), {'schemaVersion': 99, 'entries': []},
                 document(dict(entry('A'), script='alert(1)')), document(entry('A', scope='regex')),
                 document(entry('A', enabled='true')), document(entry(' A ')),
                 document(entry('A', '\ud800')), document(entry('A', 'x' * 8001)),
                 dict(document(), revision=True), document(dict(entry('A'), id='forged'))]
        for value in cases:
            with self.subTest(value=str(value)[:60]), self.assertRaises(ValueError):
                validate_document(value)
        bad = self.root / 'bad.json'
        bad.write_text('{"schemaVersion":1,"schemaVersion":1,"entries":[]}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '重复'):
            self.store.preview_import(bad)
        bad.write_bytes(b' ' * (4 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, '大小'):
            self.store.preview_import(bad)

    def test_invalid_snapshot_fails_before_install_discovery(self):
        with mock.patch.object(PATCHER, 'discover_install') as discover:
            with self.assertRaises(ValueError):
                PATCHER.apply_patch('irrelevant', dictionary_snapshot=document(entry('A', scope='code')))
            discover.assert_not_called()

    def test_real_staged_patch_has_snapshot_and_marker(self):
        install = self.root / 'install'
        resources = install / 'resources'
        resources.mkdir(parents=True)
        (install / 'Antigravity.exe').write_bytes(b'fixture')
        make_archive(resources / 'app.asar')
        self.store.set_entry('ui', 'Settings', '个性配置')
        snapshot = self.store.snapshot()
        with mock.patch.object(PATCHER, 'stop_application'):
            PATCHER.apply_patch(install, dictionary_snapshot=snapshot)
        marker = json.loads((resources / 'app/.antigravity-zhcn.json').read_text())
        expected = hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True,
                                              separators=(',', ':')).encode('utf-8')).hexdigest()
        self.assertEqual(marker['dictionaryHash'], expected)
        self.assertEqual(marker['dictionaryRevision'], 1)
        self.assertIn('customTranslations', (resources / 'app/dist/preload.js').read_text(encoding='utf-8'))
        self.assertTrue((resources / 'app.asar.disabled').exists())


@unittest.skipUnless(shutil.which('node'), 'Node required for real engine execution')
class DictionaryInjectionTests(unittest.TestCase):
    def run_js(self, script, extra, texts):
        runner = r'''
const vm=require('node:vm'), fs=require('node:fs');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const ctx=vm.createContext({Node:{TEXT_NODE:3,ELEMENT_NODE:1},MutationObserver:class{observe(){}},document:{addEventListener(){}}});
vm.runInContext(input.script,ctx,{timeout:1000});
process.stdout.write(JSON.stringify(input.texts.map(text=>ctx.translateText(text))));
'''
        before, after = script.rsplit('})();', 1)
        script = before + '\nglobalThis.translateText=translateText;\n' + extra + '\n})();' + after
        result = subprocess.run(['node', '-e', runner], input=json.dumps(dict(script=script, texts=texts)),
                                text=True, encoding='utf-8', capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_exact_overrides_disable_dynamic_rules_and_literal_text(self):
        special = '字面 $& $` $\' \\ "\n</script>\u2028结尾'
        snapshot = document(entry('Settings', special), entry('99% left', 'unused', enabled=False),
                            entry('__proto__', '原型'), entry('constructor', '构造'), entry('Voice speed, 2x', '两倍'))
        script, _ = PATCHER.build_injections(snapshot)
        self.assertEqual(self.run_js(script, '', [' Settings ', '99% left', '__proto__', 'constructor',
                                                 'Voice speed, 2x', '88% left']),
                         [' ' + special + ' ', '99% left', '原型', '构造', '两倍', '剩余 88%'])

    def test_disabled_builtin_does_not_reappear_through_fallback(self):
        script, _ = PATCHER.build_injections(document(entry('Settings', enabled=False), entry('Try Remote Control', enabled=False)))
        self.assertEqual(self.run_js(script, '', ['Settings', 'Try Remote Control']), ['Settings', 'Try Remote Control'])

    def test_custom_target_does_not_disable_unrelated_source_or_inherit_object_keys(self):
        script, _ = PATCHER.build_injections(document(entry('Foo', 'Settings')))
        texts = ['Foo', 'Settings', '__proto__', 'constructor', 'toString']
        self.assertEqual(self.run_js(script, '', texts), ['Settings', '设置', '__proto__', 'constructor', 'toString'])
        original, _ = PATCHER.build_injections()
        self.assertEqual(self.run_js(original, '', texts[2:]), texts[2:])

    def test_menu_overrides_and_disabled_parent_preserve_children_and_actions(self):
        _, script = PATCHER.build_injections(document(entry('File', scope='menu', enabled=False),
                                                      entry('Copy', '$&复制', scope='menu'), entry('__proto__', '原型菜单', scope='menu')))
        runner = r'''
const vm=require('node:vm'),fs=require('node:fs');let n=0;
const Menu={buildFromTemplate(t){return t}};
vm.runInNewContext(JSON.parse(fs.readFileSync(0,'utf8')),{require(){return {Menu}},console});
const click=()=>n++, child={label:'Copy',click}, proto={label:'__proto__'};
const result=Menu.buildFromTemplate([{label:'File',submenu:[child,proto]}]);
child.click(); process.stdout.write(JSON.stringify([result[0].label,child.label,proto.label,n,child.click===click]));
'''
        result = subprocess.run(['node', '-e', runner], input=json.dumps(script), text=True, encoding='utf-8', capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ['File', '$&复制', '原型菜单', 1, True])

    def test_menu_custom_output_is_stable_without_blocking_other_menu_items(self):
        _, script = PATCHER.build_injections(document(entry('Copy', 'File', scope='menu')))
        runner = r'''
const vm=require('node:vm'),fs=require('node:fs');const Menu={buildFromTemplate(t){return t}};
vm.runInNewContext(JSON.parse(fs.readFileSync(0,'utf8')),{require(){return {Menu}},console});
const t=[{label:'Copy'},{label:'File'},{label:'constructor'},{label:'__proto__'}];
Menu.buildFromTemplate(t);Menu.buildFromTemplate(t);process.stdout.write(JSON.stringify(t.map(x=>x.label)));
'''
        result = subprocess.run(['node', '-e', runner], input=json.dumps(script), text=True, encoding='utf-8', capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ['File', '文件', 'constructor', '__proto__'])


@unittest.skipUnless(BROWSER, 'Chrome/Edge required for protected DOM and observer checks')
class DictionaryDOMTests(unittest.TestCase):
    def test_user_overrides_keep_protected_text_links_and_observer_stable(self):
        script, _ = PATCHER.build_injections(document(entry('Settings', '个性配置'),
            entry('99% left', enabled=False), entry('Voice speed, 2x', '两倍语速'),
            entry('literal', '$& \\ 字面'), entry('Foo', 'Settings'), entry('Copy', 'Settings', scope='menu')))
        fixtures = r'''
<div id="plain" title="Copy">Settings</div><div id="dynamic">Voice speed, 2x</div>
<div id="disabled">99% left</div><div id="mixed">Unchanged prefix: <span id="mixed-word">Settings</span></div>
<a id="link" href="https://example.invalid/">Settings</a>
<pre><code id="code">Settings</code></pre><div contenteditable="true" id="editable">Settings</div>
<div class="monaco-editor" id="editor">Settings</div><textarea id="textarea" placeholder="Settings">Settings</textarea>
<div id="literal">literal</div><pre id="icon-repair-result"></pre>
<div id="custom-source">Foo</div><div id="split-disabled"><span><b id="split-count">99%</b></span><span> left</span></div>
<input id="custom-placeholder" placeholder="Foo"><input id="native-placeholder" placeholder="Settings">
'''
        checks = r'''
const get=id=>document.getElementById(id), ensure=(v,m)=>{if(!v)throw Error(m)};
const originalLink=get('link'); let clicks=0;originalLink.addEventListener('click',e=>{e.preventDefault();clicks++});
document.addEventListener('DOMContentLoaded',async()=>{
  try {
    await new Promise(r=>setTimeout(r,0));
    ensure(get('plain').textContent==='个性配置','exact override');
    ensure(get('plain').title==='复制','independent title still translated');
    ensure(get('dynamic').textContent==='两倍语速','dynamic override');
    ensure(get('disabled').textContent==='99% left','disabled fallback');
    ensure(get('custom-source').textContent==='Settings','custom output matching another source');
    ensure(get('split-disabled').textContent==='99% left','disabled split initial');
    ensure(get('custom-placeholder').placeholder==='Settings' && get('native-placeholder').placeholder==='个性配置','separate attribute targets');
    ensure(get('literal').textContent==='$& \\ 字面','literal replacement');
    for(const id of ['code','editable','editor','textarea'])ensure(get(id).textContent==='Settings','protected '+id);
    ensure(get('textarea').placeholder==='个性配置','placeholder override');
    ensure(get('link')===originalLink && get('link').getAttribute('href')==='https://example.invalid/','link preserved');
    originalLink.click();ensure(clicks===1,'link handler');
    get('plain').firstChild.textContent='Settings';get('mixed-word').firstChild.textContent='Settings';get('disabled').firstChild.textContent='99% left';
    get('custom-source').firstChild.textContent='Foo';get('split-count').firstChild.textContent='99%';
    await new Promise(r=>setTimeout(r,0));
    ensure(get('plain').textContent==='个性配置' && get('mixed-word').textContent==='个性配置','rerender');
    ensure(get('disabled').textContent==='99% left','disabled rerender');
    ensure(get('custom-source').textContent==='Settings','custom output stable');
    ensure(get('split-disabled').textContent==='99% left','disabled deeply nested mutation');
    get('icon-repair-result').textContent=JSON.stringify({ok:true,checks:'custom exacts, disabled dynamic, protected nodes, links and mutation stability'});
  } catch(e) {get('icon-repair-result').textContent=JSON.stringify({ok:false,error:e.message})}
});
'''
        run_dom_check(self, fixtures, checks, injection=script)


if __name__ == '__main__':
    unittest.main()
