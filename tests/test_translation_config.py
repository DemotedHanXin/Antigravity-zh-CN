"""Isolated user-data and headless GUI-controller tests; never use credentials."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import subprocess
import shutil
import unittest
from unittest import mock

import translation_config as config

SPEC = importlib.util.spec_from_file_location('translation_settings', Path(__file__).resolve().parents[1] / 'Translation-Settings.py')
GUI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUI)


class TranslationConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name) / 'user'
        self.store = config.UserStore(self.directory, lock_timeout=0.1)

    def tearDown(self):
        self.temporary.cleanup()

    def test_default_read_has_no_side_effects_and_ai_is_off(self):
        value = self.store.read_config()
        self.assertFalse(value['enabled'])
        self.assertFalse(value['autoSave'])
        self.assertEqual(set(value['providers']), set(config.PROVIDERS))
        self.assertEqual(self.store.read_dictionary()['entries'], {})
        self.assertFalse(self.directory.exists())

    def test_platform_paths(self):
        # Use absolute fixture paths native to the host, including a drive on Windows.
        home = self.directory / 'home'
        roaming = self.directory / 'roaming'
        xdg = self.directory / 'xdg'
        self.assertEqual(config.user_data_dir('win32', {'APPDATA': str(roaming)}, home), roaming / 'Antigravity-zh-CN')
        self.assertEqual(config.user_data_dir('darwin', {}, home), home / 'Library/Application Support/Antigravity-zh-CN')
        self.assertEqual(config.user_data_dir('linux', {}, home), home / '.config/Antigravity-zh-CN')
        self.assertEqual(config.user_data_dir('linux', {'XDG_CONFIG_HOME': str(xdg)}, home), xdg / 'Antigravity-zh-CN')
        with self.assertRaises(config.DataError):
            config.user_data_dir('win32', {}, home)
        with self.assertRaises(config.DataError):
            config.user_data_dir('win32', {'APPDATA': 'relative'}, home)

    def test_config_roundtrip_and_revision_conflict(self):
        value = self.store.save_config(config.default_config(), 0)
        self.assertEqual(value['revision'], 1)
        self.assertEqual(self.store.read_config(), value)
        with self.assertRaises(config.ConflictError):
            self.store.save_config(value, 0)
        self.assertEqual(self.store.read_config()['revision'], 1)

    def test_missing_fields_and_unknown_schema_preserved(self):
        self.directory.mkdir()
        path = self.directory / 'config.json'
        for value in ({'schemaVersion': 2}, {'schemaVersion': 1, 'revision': 0}, {'schemaVersion': True, 'revision': 0}):
            raw = json.dumps(value)
            path.write_text(raw)
            with self.assertRaises(config.DataError):
                self.store.save_config(config.default_config())
            self.assertEqual(path.read_text(), raw)

    def test_malformed_json_and_utf8_are_preserved(self):
        self.directory.mkdir()
        path = self.directory / 'config.json'
        for raw in (b'{', b'\xff\xfe'):
            path.write_bytes(raw)
            with self.assertRaises(config.DataError):
                self.store.read_config()
            self.assertEqual(path.read_bytes(), raw)

    def test_enabled_requires_complete_selected_profile(self):
        value = config.default_config()
        value['enabled'] = True
        with self.assertRaises(config.DataError):
            self.store.save_config(value)
        self.assertFalse(self.directory.exists())
        value['providers']['openai'].update(model='test-model', apiKey='test-only-placeholder')
        self.assertTrue(self.store.save_config(value)['enabled'])

    def test_urls_reject_credentials_http_queries_and_controls(self):
        for url in ('http://localhost:8080', 'https://user:key@host/v1', 'https://host/v1?key=x',
                    'https://host/#x', 'https://host/has space', 'https://host:bad', 'file:///tmp/key', 'https://host\\path'):
            with self.subTest(url=url), self.assertRaises(config.DataError):
                config.validate_url(url)
        config.validate_url('https://example.com:443/v1')

    def test_limits_cannot_be_unbounded_or_boolean(self):
        for name in config.DEFAULT_LIMITS:
            value = config.default_config()
            value['limits'][name] = True
            with self.assertRaises(config.DataError):
                config.validate_config(value)
            value['limits'][name] = 0
            with self.assertRaises(config.DataError):
                config.validate_config(value)

    def test_lock_is_never_stolen(self):
        self.directory.mkdir()
        lock = self.directory / '.translation.lock'
        lock.mkdir()
        (lock / 'owner.json').write_text('{"pid":-1}')
        with self.assertRaises(config.ConflictError):
            self.store.save_config(config.default_config())
        self.assertTrue(lock.exists())
        self.assertFalse((self.directory / 'config.json').exists())

    def test_write_failure_preserves_original_and_cleans_temp_lock(self):
        self.store.save_config(config.default_config())
        before = (self.directory / 'config.json').read_bytes()
        with mock.patch.object(config.os, 'replace', side_effect=OSError('test disk failure')):
            with self.assertRaises(OSError):
                self.store.save_config(config.default_config())
        self.assertEqual((self.directory / 'config.json').read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()), ['config.json'])

    @unittest.skipIf(os.name == 'nt', 'POSIX modes only')
    def test_permissions_and_symlink_rejection(self):
        self.store.save_config(config.default_config())
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.directory / 'config.json').stat().st_mode & 0o777, 0o600)
        linked = Path(self.temporary.name) / 'linked'
        linked.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaises(config.DataError):
            config.UserStore(linked).read_config()
        path = self.directory / 'config.json'
        path.unlink()
        path.symlink_to(Path(self.temporary.name) / 'absent')
        with self.assertRaises(config.DataError):
            self.store.read_config()

    def test_dictionary_crud_and_tombstone(self):
        first = self.store.set_entry(' Unknown ', '未知')
        self.assertEqual(first['entries']['Unknown']['source'], 'manual')
        self.assertEqual(first['revision'], 1)
        second = self.store.delete_entry('Unknown', 1)
        self.assertEqual(second['entries'], {})
        self.assertEqual(second['tombstones'], {'Unknown': 2})
        third = self.store.set_entry('Unknown', '手工恢复', 2)
        self.assertEqual(third['tombstones'], {})
        self.assertEqual(third['revision'], 3)

    def test_ai_cannot_overwrite_manual_or_resurrect_deleted(self):
        first = self.store.set_entry('Unknown', '手工')
        self.assertEqual(self.store.set_entry('Unknown', 'AI', first['revision'], 'ai'), first)
        deleted = self.store.delete_entry('Unknown')
        self.assertEqual(self.store.set_entry('Unknown', 'AI', deleted['revision'], 'ai'), deleted)
        with self.assertRaises(config.ConflictError):
            self.store.set_entry('Unknown', 'AI', first['revision'], 'ai')
        with self.assertRaises(config.ConflictError):
            self.store.set_entry('Other', '其他', origin='ai')

    def test_ai_persists_only_with_revision_and_records_origin(self):
        result = self.store.set_entry('Unknown', '未知', 0, 'ai')
        self.assertEqual(result['entries']['Unknown']['source'], 'ai')
        self.assertEqual(self.store.read_dictionary(), result)

    def test_unsafe_and_empty_entries_rejected(self):
        for key in ('', '  ', '__proto__', 'constructor', 'prototype', 'x' * 501):
            with self.assertRaises(config.DataError):
                self.store.set_entry(key, '中文')
        with self.assertRaises(config.DataError):
            self.store.set_entry('Unknown', '')

    def test_concurrent_writes_merge_latest_dictionary(self):
        errors = []
        def write(index):
            try:
                config.UserStore(self.directory, lock_timeout=3).set_entry('Entry ' + str(index), '条目 ' + str(index))
            except Exception as error:
                errors.append(error)
        threads = [threading.Thread(target=write, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(self.store.read_dictionary()['entries']), 8)
        self.assertEqual(self.store.read_dictionary()['revision'], 8)

    def test_clear_cache_preserves_config(self):
        initial = self.store.save_config(config.default_config())
        updated = self.store.clear_cache()
        self.assertEqual(updated['cacheEpoch'], 1)
        self.assertEqual(updated['providers'], initial['providers'])
        self.assertEqual(updated['revision'], initial['revision'] + 1)

    def test_gui_save_requires_plaintext_confirmation(self):
        controller = GUI.SettingsController(self.store)
        draft = controller.reload()
        draft['providers']['openai']['apiKey'] = 'test-only-placeholder'
        with self.assertRaises(config.DataError):
            controller.save(draft)
        self.assertFalse(self.directory.exists())
        controller.save(draft, plaintext_confirmed=True)
        self.assertEqual(self.store.read_config()['revision'], 1)

    def test_gui_cancel_reload_does_not_save_draft(self):
        controller = GUI.SettingsController(self.store)
        draft = controller.reload()
        draft['enabled'] = True
        reloaded = controller.reload()
        self.assertFalse(reloaded['enabled'])
        self.assertFalse(self.directory.exists())

    def test_gui_stale_save_and_dictionary_crud(self):
        controller = GUI.SettingsController(self.store)
        draft = controller.reload()
        self.store.clear_cache()
        with self.assertRaises(config.ConflictError):
            controller.save(draft)
        controller.reload()
        controller.set_entry('Unknown', '未知')
        self.assertEqual(len(controller.entries('未知')), 1)
        controller.delete_entry('Unknown')
        self.assertEqual(controller.entries(), [])

    def test_gui_probe_sanitizes_output_and_never_auto_executes(self):
        command = ['node', 'probe.cjs', '--confirm-network', '--revision', '1']
        cases = [
            ('{"ok":true,"status":"connected"}', 0, 'connected'),
            ('{"ok":false,"status":"connected"}', 0, 'invalid_response'),
            ('{"ok":true,"status":"connected"}', 1, 'invalid_response'),
            ('{"ok":false,"status":"authentication_failed"}', 1, 'authentication_failed'),
            ('a secret value from broken process', 1, 'unavailable'),
            ('{"status":"test-only-secret"}', 1, 'unavailable'),
            ('[]', 1, 'unavailable'),
        ]
        for output, code, expected in cases:
            with self.subTest(expected=expected), mock.patch.object(GUI.subprocess, 'run',
                    return_value=subprocess.CompletedProcess(command, code, stdout=output)) as run:
                self.assertEqual(GUI.run_confirmed_probe(command), expected)
                self.assertEqual(run.call_args.kwargs['stderr'], subprocess.DEVNULL)
        with mock.patch.object(GUI.subprocess, 'run', side_effect=subprocess.TimeoutExpired(command, 1)):
            self.assertEqual(GUI.run_confirmed_probe(command), 'timeout')
        with mock.patch.object(GUI.shutil, 'which', return_value=None):
            with self.assertRaises(config.DataError):
                GUI.probe_command()

    @unittest.skipUnless(shutil.which('node'), 'Node unavailable')
    def test_python_node_storage_contract(self):
        # No network: require storage only, write a fixture through Node's store.
        value = config.default_config()
        value['enabled'] = True
        value['autoSave'] = True
        value['providers']['openai'].update(model='fixture-model', apiKey='test-only-placeholder')
        value = self.store.save_config(value)
        root = Path(__file__).resolve().parents[1]
        script = """const {Store}=require('./localization_runtime/storage.cjs');
        (async()=>{const s=new Store(process.argv[1]);const x=await s.read();
        if(!x.config.enabled||x.dictionary.revision!==0)throw Error('bad read');
        const saved=await s.saveAI([{source:'Open fixture',translation:'打开样例'}],0,x.config.revision);
        if(!saved)throw Error('not saved');process.stdout.write('ok');})().catch(()=>process.exit(1));"""
        result = subprocess.run([shutil.which('node'), '-e', script, str(self.directory)],
            cwd=str(root), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, 'Node storage contract failed')
        self.assertEqual(result.stdout, 'ok')
        self.assertEqual(self.store.read_dictionary()['entries']['Open fixture']['translation'], '打开样例')
        # Python tombstones then prevent Node resurrection without overwriting.
        deleted = self.store.delete_entry('Open fixture')
        script = """const {Store}=require('./localization_runtime/storage.cjs');
        (async()=>{const s=new Store(process.argv[1]);const x=await s.read();
        const saved=await s.saveAI([{source:'Open fixture',translation:'错误恢复'}],x.dictionary.revision,x.config.revision);
        if(saved)throw Error('resurrected');})().catch(()=>process.exit(1));"""
        result = subprocess.run([shutil.which('node'), '-e', script, str(self.directory)],
            cwd=str(root), capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.store.read_dictionary(), deleted)

    def test_schema_limits_count_tombstones_and_controls(self):
        for field in ('entries', 'tombstones'):
            dictionary = config.default_dictionary()
            dictionary[field] = {str(index): 0 for index in range(10001)}
            with self.assertRaises(config.DataError):
                config.validate_dictionary(dictionary)
        dictionary = config.default_dictionary()
        dictionary['tombstones'][' padded '] = 0
        with self.assertRaises(config.DataError):
            config.validate_dictionary(dictionary)
        profile = config.default_config()
        profile['providers']['openai']['apiKey'] = 'bad\tkey'
        with self.assertRaises(config.DataError):
            config.validate_config(profile)
        for key, maximum in config.DEFAULT_LIMITS.items():
            profile = config.default_config()
            profile['limits'][key] = maximum + 1
            with self.assertRaises(config.DataError):
                config.validate_config(profile)

    def test_read_rejects_changed_file_descriptor(self):
        self.store.save_config(config.default_config())
        other = Path(self.temporary.name) / 'other.json'
        other.write_text(json.dumps(config.default_config()))
        original_open = os.open
        def swapped(path, flags, *args, **kwargs):
            if Path(path).name == 'config.json':
                return original_open(str(other), flags, *args, **kwargs)
            return original_open(path, flags, *args, **kwargs)
        with mock.patch.object(config.os, 'open', side_effect=swapped):
            with self.assertRaises(config.DataError):
                self.store.read_config()

    @unittest.skipUnless(shutil.which('node'), 'Node unavailable')
    def test_python_node_schema_rejection_parity(self):
        fixtures = []
        for key in config.DEFAULT_LIMITS:
            value = config.default_config()
            value['limits'][key] += 1
            fixtures.append(['config', value])
        value = config.default_config()
        value['enabled'] = True
        fixtures.append(['config', value])
        value = config.default_config()
        value['providers']['openai']['apiKey'] = 'bad\tkey'
        fixtures.append(['config', value])
        value = config.default_config()
        value['providers']['extra'] = {}
        fixtures.append(['config', value])
        for key in ('__proto__', ' padded ', 'x' * 501):
            value = config.default_dictionary()
            value['tombstones'][key] = 0
            fixtures.append(['dictionary', value])
        value = config.default_dictionary()
        value['entries']['Unknown'] = {'translation': ' ', 'source': 'manual', 'context': 'ui', 'updatedAt': ''}
        fixtures.append(['dictionary', value])
        value = config.default_dictionary()
        value['entries']['Unknown'] = {'translation': '😀' * 1001, 'source': 'manual', 'context': 'ui', 'updatedAt': ''}
        fixtures.append(['dictionary', value])
        for kind, value in fixtures:
            with self.assertRaises(config.DataError):
                (config.validate_config if kind == 'config' else config.validate_dictionary)(value)
        script = """const s=require('./localization_runtime/storage.cjs');let input='';
        process.stdin.on('data',v=>input+=v);process.stdin.on('end',()=>{
          const checks=JSON.parse(input).map(([kind,v])=>{try{(kind==='config'?s.validateConfig:s.validateDictionary)(v);return false;}catch{return true;}});
          process.stdout.write(JSON.stringify(checks));});"""
        result = subprocess.run([shutil.which('node'), '-e', script], input=json.dumps(fixtures),
            cwd=str(Path(__file__).resolve().parents[1]), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), [True] * len(fixtures))

    def test_read_does_not_emit_or_network_secrets(self):
        with mock.patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')):
            self.store.save_config(config.default_config())
            GUI.SettingsController(self.store).reload()


if __name__ == '__main__':
    unittest.main()
