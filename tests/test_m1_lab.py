"""Offline lab-helper tests: synthetic files only, no application, UI, or registry."""
import contextlib
import copy
import datetime
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import types
import unittest
from unittest import mock

from source_paths import ROOT

SPEC = importlib.util.spec_from_file_location('m1_lab_under_test', ROOT / 'tests' / 'manual' / 'm1_lab.py')
LAB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAB)
REQUEST_ID = 'a' * 32


class LabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m1-helper-')
        self.addCleanup(self.temp.cleanup)
        self.repository = Path(self.temp.name).resolve()
        self.root = self.repository / '.m1-lab-fixture'
        self.app = self.root / 'install' / 'resources' / 'app'
        self.app.mkdir(parents=True)
        (self.root / 'install' / 'Antigravity.exe').write_bytes(b'not an executable')
        (self.root / 'evidence').mkdir()
        self.package = self.app / 'package.json'
        self.package.write_text('{"main":"dist/main.js"}', encoding='utf-8')
        (self.app / 'dist').mkdir()
        (self.app / 'dist' / 'main.js').write_text('// fixture', encoding='utf-8')
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(LAB, 'REPOSITORY', self.repository).start()
        mock.patch.object(LAB.secrets, 'token_hex', return_value=REQUEST_ID).start()
        self.popen = mock.patch.object(LAB.subprocess, 'Popen', side_effect=AssertionError('No process allowed')).start()
        self.run = mock.patch.object(LAB.subprocess, 'run', side_effect=AssertionError('No process allowed')).start()
        self.proxy = mock.patch.object(LAB, 'manual_proxy_environment', side_effect=AssertionError('No registry allowed')).start()

    def test_capture_publishes_complete_request_without_other_changes(self):
        before = set(self.root.rglob('*'))
        result = LAB.request_capture(self.root)
        marker = self.root / 'capture-request.json'
        self.assertEqual(json.loads(marker.read_text(encoding='utf-8')),
                         {'schemaVersion': 1, 'id': REQUEST_ID})
        self.assertEqual(result, self.root / 'evidence' / ('ui-' + REQUEST_ID + '.json'))
        self.assertEqual(set(self.root.rglob('*')) - before, {marker})
        self.assertFalse(result.exists())
        self.popen.assert_not_called()
        self.proxy.assert_not_called()

    def test_capture_does_not_overwrite_a_pending_or_malformed_request(self):
        marker = self.root / 'capture-request.json'
        for content in ('{"id":"existing"}', 'incomplete JSON'):
            with self.subTest(content=content):
                marker.write_text(content, encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'already pending'):
                    LAB.request_capture(self.root)
                self.assertEqual(marker.read_text(encoding='utf-8'), content)

    def test_capture_does_not_overwrite_concurrently_queued_request(self):
        marker = self.root / 'capture-request.json'
        def competitor(source, destination):
            Path(destination).write_text('other request', encoding='utf-8')
            raise FileExistsError()
        operation = 'rename' if os.name == 'nt' else 'link'
        with mock.patch.object(LAB.os, operation, side_effect=competitor):
            with self.assertRaisesRegex(ValueError, 'concurrently'):
                LAB.request_capture(self.root)
        self.assertEqual(marker.read_text(encoding='utf-8'), 'other request')
        self.assertFalse(list(self.root.glob('.capture-request-*.tmp')))

    def test_capture_refuses_existing_result_identifier(self):
        result = self.root / 'evidence' / ('ui-' + REQUEST_ID + '.json')
        result.write_text('previous result', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'identifier already exists'):
            LAB.request_capture(self.root)
        self.assertEqual(result.read_text(encoding='utf-8'), 'previous result')
        self.assertFalse((self.root / 'capture-request.json').exists())

    def test_capture_requires_existing_safe_lab_and_evidence_directory(self):
        for path in (self.repository, self.repository / 'src', self.root / 'nested',
                     self.repository / '.m1-lab-invalid' / '..' / 'elsewhere'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                LAB.request_capture(path)
        (self.root / 'evidence').rmdir()
        with self.assertRaises(FileNotFoundError):
            LAB.request_capture(self.root)
        self.assertFalse((self.root / 'capture-request.json').exists())

    def test_capture_rejects_non_regular_request(self):
        marker = self.root / 'capture-request.json'
        marker.mkdir()
        with self.assertRaisesRegex(ValueError, 'unexpected file type'):
            LAB.request_capture(self.root)
        self.assertTrue(marker.is_dir())

    def test_regular_rejects_mocked_symlink_and_windows_reparse_point(self):
        for mode, attributes in ((stat.S_IFLNK, 0), (stat.S_IFREG, 1024)):
            path = mock.Mock()
            path.lstat.return_value = types.SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                LAB.regular(path)

    def test_capture_cli_prints_result_location_without_ui_data(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(LAB.main(['capture', '--lab', str(self.root)]), 0)
        self.assertIn('no application was started', output.getvalue())
        self.assertIn('ui-' + REQUEST_ID + '.json', output.getvalue())
        self.popen.assert_not_called()
        self.proxy.assert_not_called()

    def restart_report(self):
        report_id = 'b' * 32
        report = {'schemaVersion': 1, 'requestId': report_id, 'status': 'ok', 'preloadErrors': 0,
                  'capturedAt': (datetime.datetime.now(datetime.timezone.utc) -
                                 datetime.timedelta(seconds=5)).isoformat(),
                  'bridge': {'mode': 'controlled-success', 'authorizedSnapshots': 3},
                  'lifecycle': {'sessionId': 'c' * 32, 'appPid': 456,
                                'service': {'generation': 1, 'pid': 789, 'port': 43210}},
                  'windows': [{'windowId': 1, 'port': 43210,
                               'security': {'contextIsolation': True, 'sandbox': True, 'nodeIntegration': False},
                               'ui': {'route': {'path': '/', 'hasQuery': False, 'hasHash': False}}}]}
        path = self.root / 'evidence' / ('ui-' + report_id + '.json')
        path.write_text(json.dumps(report), encoding='utf-8')
        (self.root / 'launch.lock').write_text('123', encoding='ascii')
        (self.root / 'pid').write_text('456', encoding='ascii')
        return path, report

    def test_restart_publishes_only_exact_binding_without_touching_processes(self):
        path, report = self.restart_report()
        report['private'] = 'private-body'
        report['lifecycle']['secret'] = 'private-key'
        report['windows'][0]['ui']['route']['url'] = 'private-url'
        path.write_text(json.dumps(report), encoding='utf-8')
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = LAB.request_service_restart(self.root, path)
        marker = self.root / 'restart-service-request.json'
        self.assertEqual(json.loads(marker.read_text(encoding='utf-8')), {
            'schemaVersion': 1, 'id': REQUEST_ID, 'sessionId': 'c' * 32,
            'expectedGeneration': 1, 'expectedPid': 789, 'expectedPort': 43210, 'expectedWindowId': 1})
        self.assertEqual(result, self.root / 'evidence' / ('service-restart-' + REQUEST_ID + '.json'))
        self.assertFalse(result.exists())
        self.assertNotIn('private', marker.read_text(encoding='utf-8'))
        after = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(set(after) - set(before), {marker})
        for p, data in before.items():
            self.assertEqual(after[p], data)
        self.popen.assert_not_called()
        self.run.assert_not_called()
        self.proxy.assert_not_called()

    def test_restart_rejects_wrong_report_path_and_filename_before_publication(self):
        path, _ = self.restart_report()
        for candidate in (Path(path.name), self.repository / path.name,
                          path.parent / 'nested' / path.name, path.parent / 'ui-invalid.json',
                          path.parent / '..' / 'evidence' / path.name,
                          path.parent / (path.name + ':alternate')):
            with self.subTest(path=candidate), self.assertRaises(ValueError):
                LAB.request_service_restart(self.root, candidate)
        self.assertFalse((self.root / 'restart-service-request.json').exists())

    def test_restart_rejects_symlink_or_reparse_report(self):
        path, _ = self.restart_report()
        original = Path.lstat
        for mode, attributes in ((stat.S_IFLNK, 0), (stat.S_IFREG, 1024)):
            def altered(p):
                if p == path:
                    return types.SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
                return original(p)
            with self.subTest(mode=mode), mock.patch.object(Path, 'lstat', altered), \
                    self.assertRaisesRegex(ValueError, 'unexpected file type'):
                LAB.request_service_restart(self.root, path)
        self.assertFalse((self.root / 'restart-service-request.json').exists())

    def test_restart_bounds_report_size_and_sanitizes_invalid_json(self):
        path, _ = self.restart_report()
        for data in (b' ' * (256 * 1024 + 1), b'private-secret-invalid-json', b'\xff'):
            path.write_bytes(data)
            with self.subTest(size=len(data)), self.assertRaises(ValueError) as caught:
                LAB.request_service_restart(self.root, path)
            self.assertNotIn('private-secret', str(caught.exception))
        self.assertFalse((self.root / 'restart-service-request.json').exists())

    def test_restart_rejects_ineligible_or_malformed_report(self):
        path, report = self.restart_report()
        changes = [
            (('schemaVersion',), True), (('schemaVersion',), 2), (('requestId',), 'd' * 32),
            (('status',), 'capture_failed'), (('preloadErrors',), True), (('preloadErrors',), 1),
            (('bridge',), None), (('bridge', 'mode'), 'not_installed'),
            (('bridge', 'mode'), 'controlled-disabled'), (('bridge', 'mode'), 'controlled-failure'),
            (('bridge', 'authorizedSnapshots'), 0), (('bridge', 'authorizedSnapshots'), True),
            (('lifecycle',), None), (('lifecycle', 'sessionId'), 'invalid'),
            (('lifecycle', 'appPid'), True), (('lifecycle', 'appPid'), 9007199254740992),
            (('lifecycle', 'service'), None), (('lifecycle', 'service', 'generation'), 0),
            (('lifecycle', 'service', 'generation'), True), (('lifecycle', 'service', 'pid'), True),
            (('lifecycle', 'service', 'pid'), 456), (('lifecycle', 'service', 'port'), True),
            (('lifecycle', 'service', 'port'), 65536), (('windows',), []),
            (('windows',), [{}, {}]), (('windows', 0), None),
            (('windows', 0, 'windowId'), True), (('windows', 0, 'windowId'), 0),
            (('windows', 0, 'port'), 43211), (('windows', 0, 'security'), None),
            (('windows', 0, 'security', 'contextIsolation'), False),
            (('windows', 0, 'security', 'sandbox'), False),
            (('windows', 0, 'security', 'nodeIntegration'), True),
            (('windows', 0, 'ui'), None), (('windows', 0, 'ui', 'route'), None),
            (('windows', 0, 'ui', 'route', 'path'), '/settings'),
            (('windows', 0, 'ui', 'route', 'hasQuery'), True),
            (('windows', 0, 'ui', 'route', 'hasHash'), True),
        ]
        for keys, value in changes:
            changed = copy.deepcopy(report)
            parent = changed
            for key in keys[:-1]:
                parent = parent[key]
            parent[keys[-1]] = value
            path.write_text(json.dumps(changed), encoding='utf-8')
            with self.subTest(keys=keys, value=value), self.assertRaises(ValueError):
                LAB.request_service_restart(self.root, path)
            self.assertFalse((self.root / 'restart-service-request.json').exists())

    def test_restart_requires_recent_timezone_aware_report(self):
        path, report = self.restart_report()
        now = datetime.datetime.now(datetime.timezone.utc)
        for captured in (None, 'private-invalid-time', now.replace(tzinfo=None).isoformat(),
                         (now - datetime.timedelta(seconds=301)).isoformat(),
                         (now + datetime.timedelta(seconds=30)).isoformat()):
            report['capturedAt'] = captured
            path.write_text(json.dumps(report), encoding='utf-8')
            with self.subTest(captured=captured), self.assertRaises(ValueError) as caught:
                LAB.request_service_restart(self.root, path)
            self.assertNotIn('private-invalid-time', str(caught.exception))
        report['capturedAt'] = (now - datetime.timedelta(seconds=299)).isoformat().replace('+00:00', 'Z')
        path.write_text(json.dumps(report), encoding='utf-8')
        LAB.request_service_restart(self.root, path)

    def test_restart_requires_matching_launcher_records_and_not_stopping(self):
        path, _ = self.restart_report()
        for name in ('launch.lock', 'pid'):
            record = self.root / name
            original = record.read_bytes()
            record.unlink()
            with self.subTest(name=name), self.assertRaises(FileNotFoundError):
                LAB.request_service_restart(self.root, path)
            for value in ('0', '-1', 'true', 'x' * 33, '9007199254740992'):
                record.write_text(value, encoding='ascii')
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    LAB.request_service_restart(self.root, path)
            record.write_bytes(original)
        (self.root / 'pid').write_text('457', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'does not match'):
            LAB.request_service_restart(self.root, path)
        (self.root / 'pid').write_text('456', encoding='ascii')
        (self.root / 'stop').write_text('stop', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'stopping'):
            LAB.request_service_restart(self.root, path)
        self.assertFalse((self.root / 'restart-service-request.json').exists())

    def test_restart_preserves_existing_pending_request_or_receipt_or_claim(self):
        path, _ = self.restart_report()
        for target in (self.root / 'restart-service-request.json',
                       self.root / 'evidence' / ('service-restart-' + REQUEST_ID + '.json'),
                       self.root / 'evidence' / ('service-restart-' + REQUEST_ID + '.claim.json')):
            target.write_text('existing', encoding='ascii')
            with self.subTest(target=target), self.assertRaises(ValueError):
                LAB.request_service_restart(self.root, path)
            self.assertEqual(target.read_text(encoding='ascii'), 'existing')
            target.unlink()
        self.assertFalse((self.root / 'restart-service-request.json').exists())

    def test_restart_publication_never_overwrites_a_concurrent_request(self):
        path, _ = self.restart_report()
        marker = self.root / 'restart-service-request.json'
        def competitor(source, destination):
            complete = json.loads(Path(source).read_text(encoding='utf-8'))
            self.assertEqual(complete['expectedPid'], 789)
            Path(destination).write_text('other request', encoding='ascii')
            raise FileExistsError()
        operation = 'rename' if os.name == 'nt' else 'link'
        with mock.patch.object(LAB.os, operation, side_effect=competitor):
            with self.assertRaisesRegex(ValueError, 'concurrently'):
                LAB.request_service_restart(self.root, path)
        self.assertEqual(marker.read_text(encoding='ascii'), 'other request')
        self.assertFalse(list(self.root.glob('.restart-service-request-*.tmp')))

    def test_restart_rechecks_launcher_records_before_publication(self):
        path, _ = self.restart_report()
        def changed_record(_size):
            (self.root / 'pid').write_text('457', encoding='ascii')
            return REQUEST_ID
        with mock.patch.object(LAB.secrets, 'token_hex', side_effect=changed_record):
            with self.assertRaisesRegex(ValueError, 'records changed'):
                LAB.request_service_restart(self.root, path)
        self.assertFalse((self.root / 'restart-service-request.json').exists())

    def test_restart_failed_flush_leaves_no_partial_request_or_temporary(self):
        path, _ = self.restart_report()
        with mock.patch.object(LAB.os, 'fsync', side_effect=OSError('fixture disk failure')):
            with self.assertRaises(OSError):
                LAB.request_service_restart(self.root, path)
        self.assertFalse((self.root / 'restart-service-request.json').exists())
        self.assertFalse(list(self.root.glob('.restart-service-request-*.tmp')))

    def test_restart_never_removes_a_preexisting_temporary(self):
        path, _ = self.restart_report()
        temporary = self.root / ('.restart-service-request-' + REQUEST_ID + '.tmp')
        temporary.write_text('other publisher', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'concurrently'):
            LAB.request_service_restart(self.root, path)
        self.assertEqual(temporary.read_text(encoding='ascii'), 'other publisher')
        self.assertFalse((self.root / 'restart-service-request.json').exists())

    def test_restart_cli_reports_only_queued_action_and_receipt(self):
        path, _ = self.restart_report()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(LAB.main(['restart-service', '--lab', str(self.root), '--from-report', str(path)]), 0)
        self.assertIn('this CLI did not change any process', output.getvalue())
        self.assertIn('service-restart-' + REQUEST_ID + '.json', output.getvalue())
        self.popen.assert_not_called()
        self.run.assert_not_called()
        self.proxy.assert_not_called()

    def test_environment_excludes_inherited_credentials_and_keeps_loopback_bypass(self):
        inherited = {'SystemRoot': r'C:\Windows', 'API_KEY': 'fixture-secret',
                     'HTTPS_PROXY': 'http://untrusted.invalid:8888', 'DEV_URL': 'https://untrusted.invalid',
                     'ANTIGRAVITY_M1_LOGIN': '1', 'ELECTRON_RUN_AS_NODE': '1'}
        with mock.patch.dict(os.environ, inherited, clear=True):
            env = LAB.child_environment(self.root)
        for key in ('API_KEY', 'HTTPS_PROXY', 'DEV_URL', 'ANTIGRAVITY_M1_LOGIN', 'ELECTRON_RUN_AS_NODE'):
            self.assertNotIn(key, env)
        self.assertEqual(env['NO_PROXY'], '127.0.0.1,localhost,::1')
        self.assertEqual(env['no_proxy'], env['NO_PROXY'])
        for key in ('USERPROFILE', 'HOME', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP'):
            self.assertTrue(env[key].startswith(str(self.root)))
        self.proxy.assert_not_called()

    def test_login_environment_uses_only_explicit_proxy_reader(self):
        self.proxy.side_effect = None
        self.proxy.return_value = {'HTTPS_PROXY': 'http://fixture.invalid:8080'}
        env = LAB.child_environment(self.root, allow_login=True)
        self.assertEqual(env['ANTIGRAVITY_M1_LOGIN'], '1')
        self.assertEqual(env['HTTPS_PROXY'], 'http://fixture.invalid:8080')
        self.assertEqual(env['NO_PROXY'], '127.0.0.1,localhost,::1')
        self.proxy.assert_called_once_with()

    def test_proxy_failure_precedes_package_backup_or_data_mutation(self):
        backup = self.root / 'launch-package.json'
        backup.write_bytes(self.package.read_bytes())
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        args = types.SimpleNamespace(lab=str(self.root), allow_login=True, refresh_package=False, duration=1)
        # Replace this module's os reference only; pathlib still uses the host OS.
        with mock.patch.object(LAB, 'os', types.SimpleNamespace(name='nt')), \
                mock.patch.object(LAB, 'child_environment', side_effect=ValueError('proxy rejected')), \
                mock.patch.object(LAB, 'package_backup') as write_backup, \
                mock.patch.object(LAB, 'ensure_data') as prepare_data:
            with self.assertRaisesRegex(ValueError, 'proxy rejected'):
                LAB.launch(args)
        self.assertEqual({p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}, before)
        write_backup.assert_not_called()
        prepare_data.assert_not_called()
        self.popen.assert_not_called()

    def stale_bridge_backup(self):
        backup = self.root / 'launch-package.json'
        saved = b'{"main":".dragongirl/bootstrap.cjs"}'
        backup.write_bytes(saved)
        return backup, saved

    def test_refresh_after_reset_archives_missing_old_entry_and_keeps_current_package(self):
        backup, saved = self.stale_bridge_backup()
        current = self.package.read_bytes()
        self.assertEqual(LAB.package_backup(self.root, self.package, True), current)
        self.assertEqual(self.package.read_bytes(), current)
        self.assertEqual(backup.read_bytes(), current)
        history = list((self.root / 'package-backups').glob('*.json'))
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].read_bytes(), saved)
        self.popen.assert_not_called()

    def test_reset_without_refresh_preserves_backup_and_requests_explicit_refresh(self):
        backup, saved = self.stale_bridge_backup()
        with self.assertRaisesRegex(ValueError, '--refresh-package'):
            LAB.package_backup(self.root, self.package, False)
        self.assertEqual(backup.read_bytes(), saved)
        self.assertFalse((self.root / 'package-backups').exists())

    def test_refresh_rejects_invalid_current_entry_before_archiving(self):
        backup, saved = self.stale_bridge_backup()
        for entry in ('missing.js', '../outside.js'):
            with self.subTest(entry=entry):
                self.package.write_text(json.dumps({'main': entry}), encoding='utf-8')
                with self.assertRaises((FileNotFoundError, ValueError)):
                    LAB.package_backup(self.root, self.package, True)
                self.assertEqual(backup.read_bytes(), saved)
                self.assertFalse((self.root / 'package-backups').exists())

    def test_refresh_cannot_recover_wrapped_package_with_missing_original_entry(self):
        backup, saved = self.stale_bridge_backup()
        self.package.write_text(json.dumps({'main': LAB.ENTRY}), encoding='utf-8')
        with self.assertRaises(FileNotFoundError):
            LAB.package_backup(self.root, self.package, True)
        self.assertEqual(backup.read_bytes(), saved)
        self.assertFalse((self.root / 'package-backups').exists())

    def test_unchanged_backup_still_requires_existing_entry(self):
        backup, saved = self.stale_bridge_backup()
        self.package.write_bytes(saved)
        with self.assertRaises(FileNotFoundError):
            LAB.package_backup(self.root, self.package, True)
        self.assertEqual(backup.read_bytes(), saved)
        self.assertFalse((self.root / 'package-backups').exists())


if __name__ == '__main__':
    unittest.main()
