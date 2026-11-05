"""Structured installation operations use disposable fake app bytes only."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from source_paths import ROOT
import antigravity_common as common
import installation_service as service
import translation_integration as bridge
from test_localization import make_archive, PATCHER
from test_restore import TOOL as RESTORE


class InstallationServiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='.install-service-', dir=str(ROOT))
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.resources = self.root / 'resources'
        self.resources.mkdir()
        (self.root / 'Antigravity.exe').write_bytes(b'never execute')
        self.archive = self.resources / 'app.asar'
        self.app = self.resources / 'app'
        make_archive(self.archive)
        self.service = service.InstallationService()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(common.sys, 'platform', 'win32'))
        self.stop_patch = self.stack.enter_context(mock.patch.object(PATCHER, 'stop_application'))
        self.stop_restore = self.stack.enter_context(mock.patch.object(RESTORE, 'stop_application'))
        self.launch = self.stack.enter_context(mock.patch.object(service, 'launch_application'))
        self.stack.enter_context(mock.patch.object(service, '_load_tool',
            side_effect=lambda name: PATCHER if name == 'Antigravity-Patcher.py' else RESTORE))

    def inventory(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file()}

    def test_status_is_read_only_and_never_claims_connection(self):
        before = self.inventory()
        result = self.service.execute('status', app_dir=self.root)
        self.assertTrue(result['ok'])
        self.assertEqual(result['installation']['compatibility'], 'unsupported')
        self.assertEqual(result['installation']['component'], 'not_installed')
        self.assertEqual(result['installation']['runtime'], 'unknown')
        self.assertEqual(before, self.inventory())
        self.stop_patch.assert_not_called()
        self.launch.assert_not_called()

    def test_mutations_require_explicit_target_and_confirmation(self):
        before = self.inventory()
        for action in ('apply', 'restore'):
            for kwargs in ({'app_dir': self.root}, {'confirmed': True}):
                self.assertEqual(self.service.execute(action, **kwargs)['code'], 'confirmation_required')
        self.assertEqual(before, self.inventory())
        self.assertEqual(self.service.execute('launch')['code'], 'confirmation_required')
        self.stop_patch.assert_not_called()
        self.launch.assert_not_called()

    def test_apply_restore_return_events_without_console_output(self):
        original = self.archive.read_bytes()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            applied = self.service.execute('apply', app_dir=self.root, confirmed=True)
            restored = self.service.execute('restore', app_dir=self.root, confirmed=True)
        self.assertEqual(output.getvalue(), '')
        self.assertTrue(applied['ok'], applied)
        self.assertTrue(applied['filesChanged'])
        self.assertEqual(applied['installation']['component'], 'static_only')
        self.assertEqual(applied['steps'], [dict(step=name, status='completed')
                                         for name in ('prepare', 'stop', 'activate', 'cleanup')])
        self.assertTrue(restored['ok'], restored)
        self.assertFalse(self.app.exists())
        self.assertEqual(original, self.archive.read_bytes())
        self.stop_patch.assert_called_once()
        self.stop_restore.assert_called_once()
        self.launch.assert_not_called()

    def test_conflicting_archives_report_no_recovery_and_cannot_mutate(self):
        (self.resources / 'app.asar.disabled').write_bytes(self.archive.read_bytes())
        before = self.inventory()
        status = self.service.execute('status', app_dir=self.root)
        self.assertEqual(status['installation']['archive'], 'conflict')
        result = self.service.execute('apply', app_dir=self.root, confirmed=True)
        self.assertEqual(result['code'], 'invalid_installation')
        self.assertEqual(before, self.inventory())
        self.stop_patch.assert_not_called()

    def test_corrupt_archive_failure_is_structured_and_sanitized(self):
        self.archive.write_bytes(b'corrupt archive')
        result = self.service.execute('status', app_dir=self.root)
        self.assertEqual(result['code'], 'inspection_failed')
        self.assertNotIn('corrupt archive', json.dumps(result))
        self.stop_patch.assert_not_called()

    def test_failed_injection_leaves_original_and_reports_failure(self):
        before = self.inventory()
        with mock.patch.object(PATCHER, '_inject', side_effect=OSError('private-secret-error')):
            result = self.service.execute('apply', app_dir=self.root, confirmed=True)
        self.assertFalse(result['ok'])
        self.assertFalse(result['filesChanged'])
        self.assertNotIn('private-secret-error', json.dumps(result))
        self.assertEqual(before, self.inventory())
        self.stop_patch.assert_not_called()

    def test_restore_cleanup_failure_is_distinct_from_failed_activation(self):
        applied = self.service.execute('apply', app_dir=self.root, confirmed=True)
        self.assertTrue(applied['ok'], applied)
        with mock.patch.object(RESTORE, 'remove_tree', side_effect=PermissionError('busy')):
            result = self.service.execute('restore', app_dir=self.root, confirmed=True)
        self.assertEqual(result['code'], 'cleanup_incomplete')
        self.assertTrue(result['filesChanged'])
        self.assertTrue(self.archive.is_file())
        self.assertFalse(self.app.exists())
        self.launch.assert_not_called()

    def test_launch_is_explicit_and_does_not_claim_window_connected(self):
        result = self.service.execute('launch', app_dir=self.root)
        self.assertTrue(result['ok'])
        self.assertTrue(result['launchRequested'])
        self.assertEqual(result['installation']['runtime'], 'unknown')
        self.launch.assert_called_once_with(self.root)
        self.stop_patch.assert_not_called()

    def test_json_cli_uses_service_and_returns_only_json(self):
        for tool in (PATCHER, RESTORE):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = tool.main(['--json'])
            self.assertEqual(result, 1)
            self.assertEqual(json.loads(output.getvalue())['code'], 'confirmation_required')

    def test_profile_and_component_are_separate_and_detect_tampering(self):
        files = {'package.json': b'{"name":"fixture","version":"0.0.0","main":"dist/main.js"}'}
        files.update({'dist/' + name: ('// fixture ' + name).encode()
                      for name in ('main.js', 'preload.js', 'menu.js', 'tray.js', 'ui.js')})
        make_archive(self.archive, files=files)
        common.extract_asar(self.archive, self.app)
        profile = dict(bridge.fingerprints(self.app, ['dist/ui.js']),
                       id='fixture', schemaVersion=1, verified=True, preload='dist/preload.js',
                       uiFiles=['dist/ui.js'], trustedUrls=['https://fixture.invalid/ui'],
                       policy={'verified': True, 'rules': [{'selector': '#settings',
                               'contextKind': 'settings', 'text': True}]})
        profile.pop('note')
        profile.pop('bridgeVerified')
        with mock.patch.object(service, '_registry', return_value=[profile]):
            result = self.service.execute('status', app_dir=self.root)
            self.assertEqual(result['installation']['compatibility'], 'matched')
            self.assertEqual(result['installation']['component'], 'not_installed')
            bridge.prepare_bridge(self.app, profile)
            result = self.service.execute('status', app_dir=self.root)
            self.assertEqual(result['installation']['component'], 'installed')
            (self.app / '.dragongirl/main.cjs').write_text('tampered', encoding='utf-8')
            result = self.service.execute('status', app_dir=self.root)
            self.assertEqual(result['installation']['compatibility'], 'matched')
            self.assertEqual(result['installation']['component'], 'invalid')


if __name__ == '__main__':
    unittest.main()
