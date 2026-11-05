"""Exercise public review operations without a GUI, installation or provider."""
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from source_paths import LOCALIZATION
from translation_config import ConflictError
from credential_fixture import UserStore
from translation_service import DictionaryService


class DictionaryServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m2-service-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.now = 1800000000000
        self.store = UserStore(self.directory, clock=lambda: self.now)
        self.service = DictionaryService(self.store, builtin={'Save': '保存', 'Open': '打开'})

    def seed_candidate(self, source='Unknown action'):
        state = self.store.read_state()
        candidates = state['candidates']
        candidates['revision'] += 1
        candidates['entries'][source] = {'translation': '未知操作', 'context': 'ui',
            'createdAt': self.now, 'expiresAt': self.now + 604800000}
        target = self.directory / 'pending-translations/state.json'
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(candidates), encoding='utf-8')
        return candidates['revision']

    def test_personal_override_and_restore_default_do_not_change_builtin(self):
        listed = self.service.execute('list', query='save')
        self.assertTrue(listed['ok'])
        self.assertEqual(listed['entries'][0]['translation'], '保存')
        saved = self.service.execute('set', source='Save', translation='个人保存',
                                     revision=listed['dictionaryRevision'])
        self.assertTrue(saved['ok'])
        overridden = self.service.execute('list', query='个人')
        self.assertEqual(overridden['entries'][0], {
            'original': 'Save', 'translation': '个人保存', 'source': 'manual',
            'defaultTranslation': '保存', 'hasOverride': True})
        stale = self.service.execute('restore-default', source='Save', revision=listed['dictionaryRevision'])
        self.assertEqual(stale['code'], 'conflict')
        restored = self.service.execute('restore-default', source='Save', revision=saved['dictionaryRevision'])
        self.assertTrue(restored['ok'])
        self.assertEqual(self.service.execute('list', query='Save')['entries'][0]['translation'], '保存')

    def test_review_edit_accept_and_expiry_conflict_are_public_operations(self):
        revision = self.seed_candidate()
        pending = self.service.execute('pending')
        self.assertEqual(pending['entries'][0]['original'], 'Unknown action')
        result = self.service.execute('accept', source='Unknown action', revision=revision,
                                      translation='人工确认的操作')
        self.assertTrue(result['ok'])
        entry = self.service.execute('list', query='Unknown')['entries'][0]
        self.assertEqual((entry['translation'], entry['source']), ('人工确认的操作', 'accepted'))
        self.assertEqual(self.service.execute('pending')['entries'], [])
        revision = self.seed_candidate('Expired action')
        self.now += 604800000
        result = self.service.execute('accept', source='Expired action', revision=revision)
        self.assertFalse(result['ok'])
        self.assertNotIn('Expired action', self.store.read_dictionary()['entries'])

    def test_rejection_survives_cleanup_and_explicit_unblock(self):
        revision = self.seed_candidate()
        self.assertTrue(self.service.execute('reject', source='Unknown action', revision=revision)['ok'])
        self.now += 8 * 86400000
        self.assertTrue(self.service.execute('cleanup')['ok'])
        pending = self.service.execute('pending')
        self.assertEqual(pending['entries'], [])
        self.assertEqual(pending['rejected'][0]['original'], 'Unknown action')
        self.assertTrue(self.service.execute('unblock', source='Unknown action',
                                            revision=pending['candidatesRevision'])['ok'])
        self.assertEqual(self.service.execute('pending')['rejected'], [])

    def test_structured_results_never_export_provider_credentials(self):
        config = self.store.read_config()
        config['providers']['openai']['apiKey'] = 'private-fixture-value'
        self.store.save_config(config, config['revision'])
        self.seed_candidate()
        for action in ('list', 'pending', 'cleanup'):
            result = self.service.execute(action)
            self.assertTrue(result['ok'])
            encoded = json.dumps(result)
            for forbidden in ('private-fixture-value', 'apiKey', 'providers', 'baseUrl'):
                self.assertNotIn(forbidden, encoded)
        for args in ({'action': 'set', 'source': None, 'translation': '值', 'revision': 0},
                     {'action': 'accept', 'source': 'Unknown', 'revision': True},
                     {'action': 'list', 'query': None}, {'action': 'unsupported'}):
            self.assertFalse(self.service.execute(**args)['ok'])

    def test_invalid_catalog_returns_structured_error_without_raw_contents(self):
        service = DictionaryService(self.store)
        with patch('translation_service.load_builtin_dictionary', side_effect=ValueError('private raw catalog')):
            result = service.execute('list')
        self.assertEqual(result['code'], 'invalid_catalog')
        self.assertNotIn('private raw catalog', json.dumps(result))

    def test_settings_cleanup_cannot_advance_an_open_edit_revision(self):
        spec = importlib.util.spec_from_file_location('m2_settings', LOCALIZATION / 'Translation-Settings.py')
        settings = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(settings)
        controller = settings.SettingsController(self.store)
        controller.reload()
        original_revision = controller.dictionary['revision']
        self.store.set_entry('Save', '其他窗口的修改', expected_revision=original_revision)
        controller.cleanup()
        self.assertEqual(controller.dictionary['revision'], original_revision)
        with self.assertRaises(ConflictError):
            controller.set_entry('Save', '尚未保存的旧草稿')
        self.assertEqual(self.store.read_dictionary()['entries']['Save']['translation'], '其他窗口的修改')

    @unittest.skipUnless(sys.platform == 'win32', 'Windows user directory contract')
    def test_missing_default_user_directory_returns_json_without_traceback(self):
        result = subprocess.run([sys.executable, '-B', str(LOCALIZATION / 'Translation-Dictionary.py'), 'list'],
            cwd=self.directory, env=dict(os.environ, APPDATA='', PYTHONIOENCODING='utf-8'),
            capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['code'], 'invalid_data')
        self.assertEqual(result.stderr, '')

    def test_cli_from_other_cwd_writes_only_explicit_directory(self):
        script = LOCALIZATION / 'Translation-Dictionary.py'
        data = self.directory / 'cli-user'
        environment = dict(os.environ, PYTHONIOENCODING='utf-8')
        environment.pop('PYTHONPATH', None)
        def run(*arguments):
            return subprocess.run([sys.executable, '-B', str(script), '--data-dir', str(data), *arguments],
                                  cwd=self.directory, env=environment, text=True, encoding='utf-8',
                                  capture_output=True, timeout=15)
        help_result = run('--help')
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertFalse(data.exists())
        result = run('list', '--query', 'New Conversation')
        self.assertEqual(result.returncode, 0, result.stderr)
        revision = json.loads(result.stdout)['dictionaryRevision']
        result = run('set', '--source', 'New Conversation', '--translation', '我的新对话', '--revision', str(revision))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['ok'])
        stale = run('restore-default', '--source', 'New Conversation', '--revision', str(revision))
        self.assertEqual(stale.returncode, 2)
        self.assertEqual(json.loads(stale.stdout)['code'], 'conflict')
        fresh = json.loads(run('list', '--query', 'New Conversation').stdout)
        selected = next(item for item in fresh['entries'] if item['original'] == 'New Conversation')
        self.assertEqual(selected['translation'], '我的新对话')


if __name__ == '__main__':
    unittest.main()
