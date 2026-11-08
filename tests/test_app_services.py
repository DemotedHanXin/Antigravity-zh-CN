"""Desktop service integration against temporary installations only."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from app import services
from test_localization import make_archive


ROOT = Path(__file__).resolve().parents[1]


class ServiceFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.desktop-service-test-', dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root / '中文 安装'
        self.resources = self.install / 'resources'
        self.resources.mkdir(parents=True)
        (self.install / 'Antigravity.exe').write_bytes(b'fixture: never run')
        self.archive = self.resources / 'app.asar'
        make_archive(self.archive)
        self.service = services.AppService(self.root / 'user-data')
        self.patcher = services._module('Antigravity-Patcher')
        self.restore = services._module('Restore')
        self.stop_patch = mock.patch.object(self.patcher, 'stop_application')
        self.stop_restore = mock.patch.object(self.restore, 'stop_application')
        self.stopped = self.stop_patch.start()
        self.stop_restore.start()
        self.addCleanup(self.stop_patch.stop)
        self.addCleanup(self.stop_restore.stop)
        self.launch_patch = mock.patch.object(services.common, 'launch_application')
        self.launched = self.launch_patch.start()
        self.addCleanup(self.launch_patch.stop)

    def inventory(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}


class ServiceTests(ServiceFixture):
    def test_inspection_validates_without_writes_or_launch(self):
        before = self.inventory()
        result = self.service.inspect(self.install)
        self.assertEqual(result.state, 'original')
        self.assertTrue(result.can_patch)
        self.assertTrue(result.can_restore)
        self.assertEqual(before, self.inventory())
        self.stopped.assert_not_called()
        self.launched.assert_not_called()

    def test_conflicting_archives_cannot_patch_restore_or_launch(self):
        (self.resources / 'app.asar.disabled').write_bytes(self.archive.read_bytes())
        before = self.inventory()
        for action in ('patch', 'restore', 'launch'):
            result = self.service.execute(action, self.install)
            self.assertEqual(result.status, 'failed')
            self.assertEqual(result.installation.state, 'conflict')
        self.assertEqual(before, self.inventory())
        self.stopped.assert_not_called()
        self.launched.assert_not_called()

    def test_invalid_archive_does_not_claim_original_state(self):
        self.archive.write_bytes(b'broken')
        result = self.service.inspect(self.install)
        self.assertEqual(result.state, 'invalid')
        self.assertFalse(result.can_patch)
        self.assertFalse(result.can_restore)

    def test_unknown_layout_allows_restore_but_blocks_patch(self):
        make_archive(self.archive, {'package.json': b'{"main":"entry.js","version":"99.0"}',
                                   'entry.js': b'// main'})
        result = self.service.inspect(self.install)
        self.assertEqual(result.version, '99.0')
        self.assertFalse(result.can_patch)
        self.assertTrue(result.can_restore)
        self.assertEqual(self.service.execute('patch', self.install).status, 'failed')
        self.stopped.assert_not_called()

    def test_patch_restore_roundtrip_records_verified_dictionary(self):
        original = self.archive.read_bytes()
        snapshot = {'schemaVersion': 1, 'revision': 3, 'entries': []}
        progress = []
        result = self.service.execute('patch', self.install, overlays=snapshot, progress=progress.append)
        self.assertEqual(result.status, 'success', result.message)
        self.assertEqual(result.installation.state, 'localized')
        self.assertEqual(result.installation.applied_revision, 3)
        expected = hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True,
                                            separators=(',', ':')).encode('utf-8')).hexdigest()
        self.assertEqual(result.installation.dictionary_hash, expected)
        self.assertTrue(progress)
        self.launched.assert_not_called()
        restored = self.service.execute('restore', self.install)
        self.assertEqual(restored.status, 'success', restored.message)
        self.assertEqual(restored.installation.state, 'original')
        self.assertEqual(self.archive.read_bytes(), original)
        self.assertFalse((self.resources / 'app').exists())
        self.launched.assert_not_called()

    def test_broken_active_directory_keeps_restore_available(self):
        self.archive.rename(self.resources / 'app.asar.disabled')
        app = self.resources / 'app'
        app.mkdir()
        (app / 'unique-file').write_text('preserve until core restores')
        status = self.service.inspect(self.install)
        self.assertEqual(status.state, 'invalid')
        self.assertTrue(status.can_restore)
        self.assertTrue(status.can_patch)
        self.assertEqual(self.service.execute('restore', self.install).status, 'success')

    def test_missing_original_preserves_only_remaining_code(self):
        self.archive.unlink()
        app = self.resources / 'app'
        app.mkdir()
        (app / 'only-code').write_text('do not delete')
        before = self.inventory()
        self.assertEqual(self.service.execute('restore', self.install).status, 'failed')
        self.assertEqual(before, self.inventory())
        self.stopped.assert_not_called()

    def test_progress_callback_failure_does_not_abort_transaction(self):
        def broken_callback(_):
            raise RuntimeError('presentation failed')
        result = self.service.execute('patch', self.install, progress=broken_callback)
        self.assertTrue(result.ok, result.message)

    def test_snapshot_is_copied_before_backend_consumes_it(self):
        snapshot = {'schemaVersion': 1, 'revision': 0, 'entries': []}
        def mutate(*_, dictionary_snapshot):
            dictionary_snapshot['entries'].append('changed')
            return True
        with mock.patch.object(self.patcher, 'apply_patch', side_effect=mutate):
            self.assertTrue(self.service.execute('patch', self.install, overlays=snapshot).ok)
        self.assertEqual(snapshot['entries'], [])

    def test_partial_restore_never_reports_success(self):
        with mock.patch.object(self.restore, 'restore', return_value=2):
            result = self.service.execute('restore', self.install)
        self.assertEqual(result.status, 'partial')
        self.assertFalse(result.ok)

    def test_busy_operation_rejected_without_backend_call(self):
        with services._TASK_LOCK:
            result = self.service.execute('patch', self.install)
        self.assertEqual(result.status, 'failed')
        self.stopped.assert_not_called()

    def test_target_lock_blocks_a_second_thread(self):
        result = []
        def contender():
            try:
                with services._installation_lock(self.install):
                    result.append('entered')
            except RuntimeError:
                result.append('blocked')
        with services._installation_lock(self.install):
            worker = threading.Thread(target=contender)
            worker.start()
            worker.join(timeout=5)
        self.assertEqual(result, ['blocked'])

    def test_manual_launch_is_separate_and_incomplete_proxy_blocks_it(self):
        self.assertTrue(self.service.execute('launch', self.install).ok)
        self.launched.assert_called_once_with(self.install)
        self.launched.reset_mock()
        (self.install / 'Antigravity-Proxy.ps1').write_text('fixture')
        self.assertEqual(self.service.execute('launch', self.install).status, 'failed')
        self.launched.assert_not_called()

    def test_diagnostics_omit_raw_errors_user_paths_and_credentials(self):
        secret = 'https://user:password@proxy.invalid/?token=SECRET'
        with mock.patch.object(self.patcher, 'apply_patch', side_effect=RuntimeError(str(self.install) + secret)):
            result = self.service.execute('patch', self.install)
        self.assertIn(secret, result.message)  # session details are useful locally
        exported = json.dumps(self.service.diagnostics(), ensure_ascii=False)
        for forbidden in ('SECRET', 'password', str(self.install), 'proxy.invalid'):
            self.assertNotIn(forbidden, exported)
        self.assertEqual(self.service.diagnostics()['events'][0]['status'], 'failed')


class ProxyServiceTests(ServiceFixture):
    def setUp(self):
        super().setUp()
        self.setup = services._module('Setup-Proxy-Shortcuts')
        self.menu = self.root / 'Menu'
        self.menu.mkdir()
        self.link = self.menu / 'Entry.lnk'
        self.link.write_bytes(b'shortcut-fixture')
        self.links = {str(self.link): {'path': str(self.link), 'target': str(self.install / 'Antigravity.exe'),
                      'arguments': '--中文 "a & b"', 'icon': str(self.install / 'Antigravity.exe') + ',0',
                      'working_directory': str(self.install)}}
        self.bridge_mock = mock.patch.object(self.setup, 'run_powershell', side_effect=self.bridge)
        self.bridge_mock.start()
        self.addCleanup(self.bridge_mock.stop)
        self.env = mock.patch.dict(os.environ, {'APPDATA': str(self.root / 'Roaming')})
        self.env.start()
        self.addCleanup(self.env.stop)

    def bridge(self, request):
        action = request['action']
        if action == 'policy':
            return {'effective': 'RemoteSigned'}
        if action == 'folders':
            return {'StartMenu': str(self.menu)}
        if action == 'read':
            return {'links': [dict(self.links[path], snapshot_hash=hashlib.sha256(Path(path).read_bytes()).hexdigest())
                              for path in request['paths'] if path in self.links], 'errors': []}
        if action == 'write':
            path = Path(request['path'])
            self.links[str(path)] = {key: request[key] for key in
                                    ('path', 'target', 'arguments', 'icon', 'working_directory')}
            path.write_bytes(json.dumps(self.links[str(path)], ensure_ascii=False).encode('utf-8'))
            return {}
        if action == 'notify':
            return {}
        raise AssertionError(action)

    def test_proxy_setup_requires_review_and_preview_never_mutates(self):
        before = self.inventory()
        rejected = self.service.execute('proxy_setup', self.install)
        self.assertFalse(rejected.ok)
        self.assertEqual(before, self.inventory())
        preview = self.service.execute('proxy_preview', self.install)
        self.assertTrue(preview.ok, preview.message)
        self.assertEqual(before, self.inventory())
        self.assertEqual(preview.items[0]['path'], str(self.link))
        result = self.service.execute('proxy_setup', self.install)
        self.assertTrue(result.ok, result.message)
        self.assertTrue((self.install / 'Antigravity-Proxy.ps1').is_file())
        self.assertEqual(self.links[str(self.link)]['target'], str(self.install / 'Antigravity-Proxy.cmd'))

    def test_changed_shortcut_content_invalidates_setup_preview(self):
        self.assertTrue(self.service.execute('proxy_preview', self.install).ok)
        self.links[str(self.link)]['arguments'] = '--new-value'
        self.link.write_bytes(b'changed after preview')
        before = self.inventory()
        result = self.service.execute('proxy_setup', self.install)
        self.assertFalse(result.ok)
        self.assertIn('发生变化', result.message)
        self.assertEqual(before, self.inventory())

    def test_proxy_remove_roundtrip_preserves_original_arguments(self):
        original_args = self.links[str(self.link)]['arguments']
        self.assertTrue(self.service.execute('proxy_preview', self.install).ok)
        self.assertTrue(self.service.execute('proxy_setup', self.install).ok)
        before = self.inventory()
        preview = self.service.execute('proxy_remove_preview', self.install)
        self.assertTrue(preview.ok, preview.message)
        self.assertEqual(before, self.inventory())
        removed = self.service.execute('proxy_remove', self.install)
        self.assertTrue(removed.ok, removed.message)
        self.assertEqual(self.links[str(self.link)]['arguments'], original_args)
        self.assertTrue(self.link.is_file())
        self.assertFalse((self.install / 'Antigravity-Proxy.ps1').exists())
        self.assertFalse((self.install / 'Antigravity-Proxy.cmd').exists())
        self.launched.assert_not_called()


if __name__ == '__main__':
    unittest.main()
