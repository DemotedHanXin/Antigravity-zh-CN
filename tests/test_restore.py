"""Restore tests mutate only isolated fixtures and never stop or launch an app."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest import mock


WORKSPACE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('restore_application', WORKSPACE / 'Restore.py')
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


def write_asar(path, main='index.js', external=False):
    files = {
        'package.json': json.dumps({'name': 'fixture', 'main': main}).encode(),
        'index.js': b'console.log("original application");',
    }
    entries, payload = {}, bytearray()
    for name, data in files.items():
        entries[name] = {'size': len(data), 'offset': str(len(payload))}
        payload.extend(data)
    if external:
        entries['dependency.node'] = {'size': 7, 'unpacked': True}
    header = json.dumps({'files': entries}, separators=(',', ':')).encode()
    padding = b'\x00' * (-len(header) % 4)
    pickle_payload_size = 4 + len(header) + len(padding)
    header_pickle = struct.pack('<II', pickle_payload_size, len(header)) + header + padding
    path.write_bytes(struct.pack('<II', 4, len(header_pickle)) + header_pickle + payload)


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.restore-unit-', dir=str(WORKSPACE))
        self.root = Path(self.temp.name).resolve()
        self.assertEqual(self.root.parent, WORKSPACE)
        self.resources = self.root / 'resources'
        self.resources.mkdir()
        self.application = self.resources / 'app'
        self.application.mkdir()
        (self.application / 'package.json').write_text('{"main":"index.js"}', encoding='utf-8')
        (self.application / 'index.js').write_bytes(b'only localized application code')
        self.archive = self.resources / 'app.asar'
        self.disabled = self.resources / 'app.asar.disabled'
        self.output = io.StringIO()
        self.stack = contextlib.ExitStack()
        self.stack.enter_context(contextlib.redirect_stdout(self.output))
        self.stack.enter_context(mock.patch.object(TOOL, 'discover_install', return_value=self.root))
        self.stack.enter_context(mock.patch.object(TOOL, 'resources_dir', return_value=self.resources))
        self.stop = self.stack.enter_context(mock.patch.object(TOOL, 'stop_application'))
        self.launch = self.stack.enter_context(mock.patch.object(TOOL, 'launch_application'))

    def tearDown(self):
        self.stack.close()
        self.temp.cleanup()

    def inventory(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file()}

    def test_missing_archives_preserves_only_application_without_stopping(self):
        before = self.inventory()
        with self.assertRaisesRegex(ValueError, '未找到可恢复'):
            TOOL.restore(self.root)
        self.assertEqual(self.inventory(), before)
        self.stop.assert_not_called()
        self.launch.assert_not_called()

    def test_invalid_archive_preserves_application_and_archive(self):
        self.disabled.write_bytes(b'not an archive')
        before = self.inventory()
        with self.assertRaises((ValueError, OSError)):
            TOOL.restore(self.root)
        self.assertEqual(self.inventory(), before)
        self.stop.assert_not_called()

    def test_archive_missing_entry_point_is_rejected_before_mutation(self):
        write_asar(self.disabled, main='missing.js')
        before = self.inventory()
        with self.assertRaises(ValueError):
            TOOL.restore(self.root)
        self.assertEqual(self.inventory(), before)
        self.stop.assert_not_called()

    def test_archive_missing_external_file_is_rejected_before_mutation(self):
        write_asar(self.disabled, external=True)
        before = self.inventory()
        with self.assertRaises((ValueError, OSError)):
            TOOL.restore(self.root)
        self.assertEqual(self.inventory(), before)
        self.stop.assert_not_called()

    def test_conflicting_archives_are_never_overwritten(self):
        write_asar(self.archive)
        write_asar(self.disabled)
        before = self.inventory()
        with self.assertRaisesRegex(ValueError, '同时存在'):
            TOOL.restore(self.root)
        self.assertEqual(self.inventory(), before)
        self.stop.assert_not_called()

    def test_success_restores_exact_archive_and_removes_only_localization(self):
        write_asar(self.disabled, external=True)
        sidecar = self.resources / 'app.asar.unpacked'
        sidecar.mkdir()
        dependency = sidecar / 'dependency.node'
        dependency.write_bytes(b'fixture')
        expected = self.disabled.read_bytes()
        proxy = self.root / 'Antigravity-Proxy.ps1'
        proxy.write_bytes(b'proxy configuration')
        self.assertEqual(TOOL.restore(self.root, launch=False), 0)
        self.assertEqual(self.archive.read_bytes(), expected)
        self.assertFalse(self.disabled.exists())
        self.assertFalse(self.application.exists())
        self.assertEqual(dependency.read_bytes(), b'fixture')
        self.assertEqual(proxy.read_bytes(), b'proxy configuration')
        self.assertEqual(set(self.resources.iterdir()), {self.archive, sidecar})
        self.stop.assert_called_once_with(self.root)
        self.launch.assert_not_called()
        after = self.inventory()
        self.assertEqual(TOOL.restore(self.root, launch=False), 0)
        self.assertEqual(self.inventory(), after)
        self.stop.assert_called_once_with(self.root)

    def test_valid_active_archive_can_remove_stale_localization(self):
        write_asar(self.archive)
        expected = self.archive.read_bytes()
        self.assertEqual(TOOL.restore(self.root), 0)
        self.assertEqual(self.archive.read_bytes(), expected)
        self.assertFalse(self.application.exists())
        self.launch.assert_called_once_with(self.root)

    def test_stop_failure_changes_no_files(self):
        write_asar(self.disabled)
        before = self.inventory()
        self.stop.side_effect = RuntimeError('fixture application cannot stop')
        with self.assertRaisesRegex(RuntimeError, 'cannot stop'):
            TOOL.restore(self.root)
        self.assertEqual(self.inventory(), before)
        self.launch.assert_not_called()

    def test_archive_changed_while_stopping_aborts_before_directory_move(self):
        write_asar(self.disabled)
        original_app = (self.application / 'index.js').read_bytes()
        self.stop.side_effect = lambda root: self.disabled.write_bytes(b'concurrent updater')
        with self.assertRaisesRegex(ValueError, '发生变化'):
            TOOL.restore(self.root)
        self.assertEqual((self.application / 'index.js').read_bytes(), original_app)
        self.assertEqual(self.disabled.read_bytes(), b'concurrent updater')
        self.assertFalse(self.archive.exists())
        self.assertFalse(list(self.resources.glob('.antigravity-restore-*')))

    def test_app_appearing_while_stopping_prevents_archive_activation(self):
        write_asar(self.disabled)
        TOOL.remove_tree(self.application, self.resources)
        original_archive = self.disabled.read_bytes()

        def updater(root):
            self.application.mkdir()
            (self.application / 'index.js').write_bytes(b'concurrent updater application')

        self.stop.side_effect = updater
        with self.assertRaisesRegex(ValueError, '工作目录.*发生变化'):
            TOOL.restore(self.root)
        self.assertEqual(self.disabled.read_bytes(), original_archive)
        self.assertFalse(self.archive.exists())
        self.assertEqual((self.application / 'index.js').read_bytes(), b'concurrent updater application')
        self.assertFalse(list(self.resources.glob('.antigravity-restore-*')))
        self.launch.assert_not_called()

    def test_app_replaced_while_stopping_preserves_both_directories(self):
        write_asar(self.disabled)
        original_archive = self.disabled.read_bytes()
        previous = self.resources / 'updater-previous-app'

        def updater(root):
            self.application.rename(previous)
            self.application.mkdir()
            (self.application / 'index.js').write_bytes(b'concurrent replacement')

        self.stop.side_effect = updater
        with self.assertRaisesRegex(ValueError, '工作目录.*发生变化'):
            TOOL.restore(self.root)
        self.assertEqual(self.disabled.read_bytes(), original_archive)
        self.assertFalse(self.archive.exists())
        self.assertEqual((self.application / 'index.js').read_bytes(), b'concurrent replacement')
        self.assertEqual((previous / 'index.js').read_bytes(), b'only localized application code')
        self.assertFalse(list(self.resources.glob('.antigravity-restore-*')))
        self.launch.assert_not_called()

    def test_archive_activation_failure_rolls_back_application(self):
        write_asar(self.disabled)
        before = self.inventory()
        rename = Path.rename

        def fail_activation(path, target):
            if path == self.disabled:
                raise PermissionError('fixture archive locked')
            return rename(path, target)

        with mock.patch.object(Path, 'rename', fail_activation):
            with self.assertRaisesRegex(PermissionError, 'archive locked'):
                TOOL.restore(self.root)
        self.assertEqual(self.inventory(), before)
        self.assertFalse(list(self.resources.glob('.antigravity-restore-*')))
        self.launch.assert_not_called()

    def test_interruption_before_archive_activation_rolls_back_application(self):
        write_asar(self.disabled)
        before = self.inventory()
        rename = Path.rename

        def interrupt_activation(path, target):
            if path == self.disabled:
                raise KeyboardInterrupt()
            return rename(path, target)

        with mock.patch.object(Path, 'rename', interrupt_activation):
            with self.assertRaises(KeyboardInterrupt):
                TOOL.restore(self.root)
        self.assertEqual(self.inventory(), before)
        self.assertFalse(list(self.resources.glob('.antigravity-restore-*')))
        self.launch.assert_not_called()

    def test_rollback_failure_retains_original_code_and_reports_location(self):
        write_asar(self.disabled)
        rename = Path.rename

        def fail_activation_and_rollback(path, target):
            if path == self.disabled or path.name.startswith('.antigravity-restore-'):
                raise PermissionError('fixture locked')
            return rename(path, target)

        with mock.patch.object(Path, 'rename', fail_activation_and_rollback):
            with self.assertRaisesRegex(RuntimeError, '请勿删除') as error:
                TOOL.restore(self.root)
        temporary = list(self.resources.glob('.antigravity-restore-*'))
        self.assertEqual(len(temporary), 1)
        self.assertEqual((temporary[0] / 'index.js').read_bytes(), b'only localized application code')
        self.assertIn(str(temporary[0]), str(error.exception))
        self.assertTrue(self.disabled.is_file())
        self.assertFalse(self.archive.exists())
        self.launch.assert_not_called()

    def test_partial_cleanup_failure_does_not_reactivate_incomplete_app(self):
        write_asar(self.disabled)

        def fail_cleanup(path, parent):
            self.assertEqual(path.resolve().parent, self.resources)
            (path / 'index.js').unlink()
            raise PermissionError('fixture locked remaining file')

        with mock.patch.object(TOOL, 'remove_tree', side_effect=fail_cleanup):
            self.assertEqual(TOOL.restore(self.root), 2)
        self.assertTrue(self.archive.is_file())
        self.assertFalse(self.disabled.exists())
        self.assertFalse(self.application.exists())
        temporary = list(self.resources.glob('.antigravity-restore-*'))
        self.assertEqual(len(temporary), 1)
        self.assertIn(str(temporary[0]), self.output.getvalue())
        self.assertNotIn('[完成]', self.output.getvalue())
        self.launch.assert_not_called()

    def test_cli_no_launch_and_failure_exit_codes(self):
        self.assertEqual(TOOL.main(['--app-dir', str(self.root), '--no-launch']), 1)
        write_asar(self.disabled)
        self.assertEqual(TOOL.main(['--app-dir', str(self.root), '--no-launch']), 0)
        self.launch.assert_not_called()

    def test_launch_failure_is_reported_after_safe_restore(self):
        write_asar(self.disabled)
        self.launch.side_effect = RuntimeError('fixture proxy policy denied')
        self.assertEqual(TOOL.main(['--app-dir', str(self.root)]), 1)
        self.assertTrue(self.archive.exists())
        self.assertFalse(self.application.exists())
        self.assertIn('自动启动未完成', self.output.getvalue())
        self.assertIn('proxy policy denied', self.output.getvalue())

    def test_process_timeout_has_failure_exit_code_without_losing_code(self):
        write_asar(self.disabled)
        before = self.inventory()
        self.stop.side_effect = subprocess.TimeoutExpired('fixture PowerShell', 30)
        self.assertEqual(TOOL.main(['--app-dir', str(self.root)]), 1)
        self.assertEqual(self.inventory(), before)
        self.assertIn('[错误]', self.output.getvalue())


if __name__ == '__main__':
    unittest.main()
