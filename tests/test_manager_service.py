"""M3 public service safety: isolation, revisions, imports and credential redaction."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from source_paths import ROOT
from antigravity_manager.service import ManagerService
from credential_fixture import UserStore


class ManagerServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m3-manager-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = UserStore(self.root / 'user')
        self.installation = Mock()
        self.installation.execute.return_value = {'ok': True, 'installation': {'running': 'unknown'}}
        self.service = ManagerService(store=self.store, installation=self.installation)

    def test_public_configuration_does_not_contain_key_and_saving_preserves_it(self):
        config = self.store.read_config()
        config['providers']['openai']['apiKey'] = 'private-fixture-key'
        self.store.save_config(config, config['revision'])
        public = self.service.execute('config')['config']
        self.assertTrue(public['providers']['openai']['hasKey'])
        self.assertNotIn('private-fixture-key', json.dumps(public))
        self.assertNotIn('apiKey', json.dumps(public))
        public['providers']['gemini']['model'] = 'fixture-model'
        result = self.service.execute('save-config', config=public, revision=public['revision'])
        self.assertTrue(result['ok'], result)
        self.assertEqual(self.store.read_config()['providers']['openai']['apiKey'], 'private-fixture-key')
        self.assertEqual(self.service.execute('save-config', config=public, revision=public['revision'])['code'], 'conflict')
        fresh = result['config']
        result = self.service.execute('save-config', config=fresh, revision=fresh['revision'], keys={'openai': ''})
        self.assertTrue(result['ok'])
        self.assertFalse(result['config']['providers']['openai']['hasKey'])
        self.assertNotIn('private-fixture-key', json.dumps(self.service.execute('diagnostics')))

    def test_extra_provider_fields_cannot_enter_saved_configuration(self):
        public = self.service.execute('config')['config']
        public['providers']['openai']['apiKey'] = 'injected-value'
        self.assertFalse(self.service.execute('save-config', config=public, revision=0)['ok'])
        self.assertFalse(self.store.directory.exists())

    def test_import_is_atomic_merges_and_invalidates_candidate_epochs(self):
        first = self.service.execute('set', source='Save', translation='旧译文', revision=0)
        path = self.root / 'import.json'
        path.write_text(json.dumps({'schemaVersion': 1, 'kind': 'dragongirl-dictionary',
                                    'entries': {'Save': '保存', 'Open': '打开'}}), encoding='utf-8')
        result = self.service.execute('import-dictionary', path=path, revision=first['dictionaryRevision'])
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['imported'], 2)
        state = self.store.read_state()
        self.assertEqual(state['dictionary']['entries']['Save']['translation'], '保存')
        self.assertEqual(state['candidates']['epochs']['Open'], 1)
        self.assertEqual(self.service.execute('import-dictionary', path=path, revision=0)['code'], 'conflict')
        before = copy.deepcopy(state)
        path.write_text(json.dumps({'schemaVersion': 1, 'kind': 'dragongirl-dictionary',
                                    'entries': {'Good': '可以', '__proto__': '无效'}}), encoding='utf-8')
        self.assertFalse(self.service.execute('import-dictionary', path=path, revision=state['dictionary']['revision'])['ok'])
        self.assertEqual(before, self.store.read_state())

    def test_export_has_only_personal_translations_and_cannot_overwrite_user_store(self):
        self.service.execute('set', source='Save', translation='保存', revision=0)
        target = self.root / 'export.json'
        result = self.service.execute('export-dictionary', path=target)
        self.assertTrue(result['ok'], result)
        self.assertEqual(json.loads(target.read_text(encoding='utf-8')), {
            'schemaVersion': 1, 'kind': 'dragongirl-dictionary', 'entries': {'Save': '保存'}})
        for name in ('config.json', 'personal-dictionary.json', '.translation-journal.json'):
            self.assertFalse(self.service.execute('export-dictionary', path=self.store.directory / name)['ok'])

    def test_import_rejects_duplicate_keys_and_oversized_files(self):
        path = self.root / 'invalid.json'
        for raw in ('{"schemaVersion":1,"kind":"dragongirl-dictionary","entries":{"X":"甲","X":"乙"}}',
                    'x' * (4 * 1024 * 1024 + 1)):
            path.write_text(raw, encoding='utf-8')
            self.assertFalse(self.service.execute('import-dictionary', path=path, revision=0)['ok'])
        self.assertFalse(self.store.directory.exists())

    def test_probe_requires_confirmation_and_exact_saved_revision(self):
        with patch('antigravity_manager.service._settings_module') as module:
            self.assertEqual(self.service.execute('probe', revision=0)['code'], 'confirmation_required')
            self.assertEqual(self.service.execute('probe', revision=8, confirmed=True)['code'], 'conflict')
            module.assert_not_called()

    def test_probe_passes_explicit_data_directory_and_keeps_output_redacted(self):
        config = self.store.read_config()
        config['providers']['openai'].update(model='fixture-model', apiKey='private-fixture-key')
        config = self.store.save_config(config, config['revision'])
        settings = Mock()
        settings.run_confirmed_probe.return_value = 'connected'
        settings.PROBE_STATUSES = {'connected': '测试成功'}
        with patch('antigravity_manager.service._settings_module', return_value=settings), \
                patch('antigravity_manager.service.shutil.which', return_value='fixture-node'):
            result = self.service.execute('probe', revision=config['revision'], confirmed=True)
        self.assertTrue(result['ok'], result)
        command = settings.run_confirmed_probe.call_args[0][0]
        self.assertEqual(command[-2:], ['--data-dir', str(self.store.directory.resolve())])
        self.assertNotIn('private-fixture-key', json.dumps(command))
        self.assertEqual(self.service.execute('status')['connection']['status'], 'connected')
        self.store.clear_cache()
        self.assertEqual(self.service.execute('status')['connection']['status'], 'not_tested')

    def test_probe_cli_wrong_revision_cannot_contact_provider_or_default_data(self):
        node = __import__('shutil').which('node')
        if not node:
            self.skipTest('Node required')
        result = subprocess.run([node, str(ROOT / 'src' / 'localization_runtime/probe.cjs'),
                                 '--confirm-network', '--revision', '7', '--data-dir', str(self.store.directory)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(json.loads(result.stdout), {'ok': False, 'status': 'configuration_changed'})
        self.assertFalse(self.store.directory.exists())

    def test_import_failure_is_sanitized_and_log_does_not_contain_arguments(self):
        with patch.object(self.service.dictionary, 'execute', side_effect=OSError('private-fixture-key')):
            result = self.service.execute('list', query='private-fixture-query')
        self.assertFalse(result['ok'])
        serialized = json.dumps([result, self.service.execute('diagnostics')])
        self.assertNotIn('private-fixture', serialized)

    def test_installation_diagnostics_keep_steps_without_arbitrary_output(self):
        self.installation.execute.return_value = {'ok': False, 'code': 'cleanup_incomplete',
            'message': 'private-fixture-output', 'filesChanged': True, 'restartRequired': True,
            'steps': [{'step': 'activate', 'status': 'completed'},
                      {'step': 'cleanup', 'status': 'incomplete'},
                      {'step': 'private-fixture-path', 'status': 'incomplete'}]}
        self.service.execute('restore', app_dir='private-fixture-path', confirmed=True)
        events = self.service.execute('diagnostics')['events']
        self.assertEqual(events[-1]['steps'], [{'step': 'activate', 'status': 'completed'},
                                               {'step': 'cleanup', 'status': 'incomplete'}])
        self.assertTrue(events[-1]['filesChanged'])
        self.assertNotIn('private-fixture', json.dumps(events))


if __name__ == '__main__':
    unittest.main()
