"""Regression fixtures never stop or launch the user's installed application."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest import mock

import antigravity_common as common


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('patcher', ROOT / 'Antigravity-Patcher.py')
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)


def make_archive(path, files=None, external=None, integrity=False):
    files = dict(files if files is not None else {
        'package.json': b'{"main":"dist/main.js"}',
        'dist/main.js': b'// main', 'dist/preload.js': b'// preload',
        'dist/menu.js': b'// menu', 'dist/tray.js': b"'Quit';'Show Antigravity';",
    })
    external = dict(external or {})
    header, payload = {'files': {}}, bytearray()
    for name, data in list(files.items()) + list(external.items()):
        parts = name.split('/')
        node = header['files']
        for part in parts[:-1]:
            node = node.setdefault(part, {'files': {}})['files']
        entry = {'size': len(data)}
        if name in external:
            entry['unpacked'] = True
            sidecar = path.with_name('app.asar.unpacked') / name
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_bytes(data)
        else:
            entry['offset'] = str(len(payload))
            payload.extend(data)
        if integrity:
            entry['integrity'] = {'algorithm': 'SHA256', 'hash': hashlib.sha256(data).hexdigest()}
        node[parts[-1]] = entry
    encoded = json.dumps(header).encode('utf-8')
    padding = b'\0' * (-len(encoded) % 4)
    payload_size = 4 + len(encoded) + len(padding)
    path.write_bytes(struct.pack('<4I', 4, 4 + payload_size, payload_size, len(encoded)) + encoded + padding + payload)


class LocalizationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='.localization-test-', dir=str(ROOT))
        self.root = Path(self.temporary.name).resolve()
        self.assertEqual(self.root.parent, ROOT)
        self.app = self.root / '中文 安装'
        self.resources = self.app / 'resources'
        self.resources.mkdir(parents=True)
        (self.app / 'Antigravity.exe').write_bytes(b'never executed')
        self.archive = self.resources / 'app.asar'
        self.disabled = self.resources / 'app.asar.disabled'
        self.work = self.resources / 'app'
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.stop = mock.patch.object(PATCHER, 'stop_application')
        self.stop_mock = self.stop.start()
        self.launch = mock.patch.object(PATCHER, 'launch_application')
        self.launch_mock = self.launch.start()
        # These are Windows-layout fixtures, independent of the test host OS.
        # Production platform guards remain unchanged; process calls stay mocked.
        platform = mock.patch.object(common.sys, 'platform', 'win32')
        platform.start()
        self.addCleanup(platform.stop)

    def tearDown(self):
        self.launch.stop()
        self.stop.stop()
        self.output.__exit__(None, None, None)
        self.temporary.cleanup()

    def old_app(self):
        self.work.mkdir()
        (self.work / 'package.json').write_text('{"main":"index.js"}')
        (self.work / 'index.js').write_bytes(b'old working app')

    def assert_no_temporary(self):
        self.assertFalse(list(self.resources.glob('.antigravity-localization-*')))

    def test_complete_patch_copies_external_dependencies_and_preserves_archive(self):
        make_archive(self.archive, external={'node_modules/dependency.js': b'exported dependency'}, integrity=True)
        original = self.archive.read_bytes()
        self.assertTrue(PATCHER.apply_patch(self.app, no_launch=True))
        self.assertFalse(self.archive.exists())
        self.assertEqual(self.disabled.read_bytes(), original)
        self.assertEqual((self.work / 'node_modules/dependency.js').read_bytes(), b'exported dependency')
        self.assertIn('Antigravity Chinese Localization Engine', (self.work / 'dist/preload.js').read_text(encoding='utf-8'))
        self.assertEqual(common.validate_extracted_app(self.work), 'dist/main.js')
        self.stop_mock.assert_called_once_with(self.app)
        self.launch_mock.assert_not_called()
        self.assert_no_temporary()

    def test_repeat_rebuilds_damaged_working_directory_from_disabled_archive(self):
        make_archive(self.disabled, external={'node_modules/dependency.js': b'dep'})
        self.old_app()
        PATCHER.apply_patch(self.app, no_launch=True)
        self.assertFalse((self.work / 'index.js').exists())
        self.assertEqual((self.work / 'node_modules/dependency.js').read_bytes(), b'dep')
        self.assert_no_temporary()

    def test_missing_archive_preserves_only_working_app(self):
        self.old_app()
        with self.assertRaisesRegex(ValueError, '保留'):
            PATCHER.apply_patch(self.app, no_launch=True)
        self.assertEqual((self.work / 'index.js').read_bytes(), b'old working app')
        self.stop_mock.assert_not_called()
        self.assert_no_temporary()

    def test_failed_extraction_with_only_disabled_archive_never_activates_partial_stage(self):
        make_archive(self.disabled)
        def extract(source, destination, **kwargs):
            (destination / 'package.json').write_bytes(b'{"main":"missing.js"}')
            raise ValueError('fixture interrupted extraction')
        with mock.patch.object(PATCHER, 'extract_asar', side_effect=extract), self.assertRaises(ValueError):
            PATCHER.apply_patch(self.app, no_launch=True)
        self.assertFalse(self.work.exists())
        self.assertTrue(self.disabled.exists())
        self.stop_mock.assert_not_called()
        self.assert_no_temporary()

    def test_failed_injection_with_only_disabled_archive_never_activates_stage(self):
        make_archive(self.disabled)
        with mock.patch.object(PATCHER, '_inject', side_effect=PermissionError('fixture failed injection')), self.assertRaises(PermissionError):
            PATCHER.apply_patch(self.app, no_launch=True)
        self.assertFalse(self.work.exists())
        self.assertTrue(self.disabled.exists())
        self.stop_mock.assert_not_called()
        self.assert_no_temporary()

    def test_stop_failure_with_only_disabled_archive_does_not_change_layout(self):
        make_archive(self.disabled)
        self.stop_mock.side_effect = RuntimeError('fixture process cannot stop')
        with self.assertRaises(RuntimeError):
            PATCHER.apply_patch(self.app, no_launch=True)
        self.assertFalse(self.work.exists())
        self.assertTrue(self.disabled.exists())
        self.assert_no_temporary()

    def test_truncated_archive_preserves_old_app_before_stopping_process(self):
        make_archive(self.archive)
        self.archive.write_bytes(self.archive.read_bytes()[:-2])
        self.old_app()
        with self.assertRaises(ValueError):
            PATCHER.apply_patch(self.app, no_launch=True)
        self.assertTrue((self.work / 'index.js').is_file())
        self.assertTrue(self.archive.is_file())
        self.assertFalse(self.disabled.exists())
        self.stop_mock.assert_not_called()
        self.assert_no_temporary()

    def test_missing_injection_target_does_not_disable_original(self):
        make_archive(self.archive, files={'package.json': b'{"main":"index.js"}', 'index.js': b'original'})
        self.old_app()
        with self.assertRaisesRegex(ValueError, '汉化目标'):
            PATCHER.apply_patch(self.app, no_launch=True)
        self.assertTrue(self.archive.exists())
        self.assertTrue((self.work / 'index.js').exists())
        self.stop_mock.assert_not_called()
        self.assert_no_temporary()

    def test_both_archives_are_never_silently_overwritten(self):
        make_archive(self.archive)
        make_archive(self.disabled)
        self.old_app()
        with self.assertRaisesRegex(ValueError, '同时发现'):
            PATCHER.apply_patch(self.app, no_launch=True)
        self.stop_mock.assert_not_called()
        self.assertTrue((self.work / 'index.js').exists())

    def test_archive_rename_failure_rolls_back_working_directory(self):
        make_archive(self.archive)
        self.old_app()
        original_rename = Path.rename
        def rename(path, target):
            if path == self.archive:
                raise PermissionError('fixture locked archive')
            return original_rename(path, target)
        with mock.patch.object(Path, 'rename', rename), self.assertRaises(PermissionError):
            PATCHER.apply_patch(self.app, no_launch=True)
        self.assertTrue(self.archive.is_file())
        self.assertEqual((self.work / 'index.js').read_bytes(), b'old working app')
        self.assert_no_temporary()

    def test_keyboard_interrupt_after_stage_rename_rolls_back(self):
        make_archive(self.archive)
        self.old_app()
        original_rename = Path.rename
        def rename(path, target):
            result = original_rename(path, target)
            if path.name.startswith('.antigravity-localization-stage-'):
                raise KeyboardInterrupt()
            return result
        with mock.patch.object(Path, 'rename', rename), self.assertRaises(KeyboardInterrupt):
            PATCHER.apply_patch(self.app, no_launch=True)
        self.assertTrue(self.archive.exists())
        self.assertEqual((self.work / 'index.js').read_bytes(), b'old working app')
        self.assert_no_temporary()

    def test_keyboard_interrupt_after_archive_rename_rolls_back(self):
        make_archive(self.archive)
        self.old_app()
        original_rename = Path.rename
        def rename(path, target):
            result = original_rename(path, target)
            if path == self.archive:
                raise KeyboardInterrupt()
            return result
        with mock.patch.object(Path, 'rename', rename), self.assertRaises(KeyboardInterrupt):
            PATCHER.apply_patch(self.app, no_launch=True)
        self.assertTrue(self.archive.exists())
        self.assertFalse(self.disabled.exists())
        self.assertEqual((self.work / 'index.js').read_bytes(), b'old working app')
        self.assert_no_temporary()

    def test_partial_cleanup_failure_cannot_corrupt_active_app_during_rollback(self):
        make_archive(self.archive)
        self.old_app()
        original_rename = Path.rename
        def rename(path, target):
            if path == self.archive:
                raise PermissionError('fixture locked archive')
            return original_rename(path, target)
        original_remove = PATCHER.remove_tree
        def remove(path, parent):
            if path.name.startswith('.antigravity-localization-stage-'):
                (path / 'dist/main.js').unlink()
                raise PermissionError('fixture partial cleanup failure')
            return original_remove(path, parent)
        with mock.patch.object(Path, 'rename', rename), mock.patch.object(PATCHER, 'remove_tree', remove), self.assertRaises(PermissionError):
            PATCHER.apply_patch(self.app, no_launch=True)
        self.assertTrue(self.archive.exists())
        self.assertEqual(common.validate_extracted_app(self.work), 'index.js')
        self.assertEqual((self.work / 'index.js').read_bytes(), b'old working app')

    def test_archive_rollback_failure_keeps_validated_new_app(self):
        make_archive(self.archive)
        self.old_app()
        original_rename = Path.rename
        def rename(path, target):
            if path == self.disabled:
                raise PermissionError('fixture cannot restore archive')
            result = original_rename(path, target)
            if path == self.archive:
                raise KeyboardInterrupt()
            return result
        with mock.patch.object(Path, 'rename', rename), self.assertRaisesRegex(RuntimeError, '回退未完成'):
            PATCHER.apply_patch(self.app, no_launch=True)
        self.assertFalse(self.archive.exists())
        self.assertTrue(self.disabled.exists())
        self.assertEqual(common.validate_extracted_app(self.work), 'dist/main.js')
        previous = list(self.resources.glob('.antigravity-localization-previous-*'))
        self.assertEqual(len(previous), 1)
        self.assertEqual((previous[0] / 'index.js').read_bytes(), b'old working app')

    def test_partial_old_directory_cleanup_after_commit_keeps_new_app(self):
        make_archive(self.archive)
        self.old_app()
        original_remove = PATCHER.remove_tree
        def remove(path, parent):
            if path.name.startswith('.antigravity-localization-previous-'):
                (path / 'index.js').unlink()
                raise PermissionError('fixture cannot finish cleanup')
            return original_remove(path, parent)
        with mock.patch.object(PATCHER, 'remove_tree', remove), self.assertRaisesRegex(RuntimeError, '旧工作目录未清理'):
            PATCHER.apply_patch(self.app, no_launch=True)
        self.assertTrue(self.disabled.exists())
        self.assertEqual(common.validate_extracted_app(self.work), 'dist/main.js')

    def test_missing_external_dependency_is_rejected(self):
        make_archive(self.archive, external={'dependency.js': b'required'})
        (self.resources / 'app.asar.unpacked/dependency.js').unlink()
        with self.assertRaises(OSError):
            common.validate_asar(self.archive)

    def test_disabled_archive_uses_original_sidecar(self):
        make_archive(self.disabled, external={'dependency.js': b'required'})
        destination = self.root / 'extracted'
        common.extract_asar(self.disabled, destination)
        self.assertEqual((destination / 'dependency.js').read_bytes(), b'required')

    def test_integrity_mismatch_is_rejected(self):
        make_archive(self.archive, external={'dependency.js': b'original'}, integrity=True)
        (self.resources / 'app.asar.unpacked/dependency.js').write_bytes(b'modified')
        with self.assertRaisesRegex(ValueError, '完整性'):
            common.validate_asar(self.archive)

    def test_path_traversal_is_rejected_before_extraction(self):
        make_archive(self.archive, files={'../outside.js': b'bad'})
        with self.assertRaisesRegex(ValueError, '文件名'):
            common.extract_asar(self.archive, self.work)
        self.assertFalse((self.resources / 'outside.js').exists())
        self.assertFalse(self.work.exists())

    def test_missing_main_is_rejected(self):
        make_archive(self.archive, files={'package.json': b'{"main":"missing.js"}'})
        with self.assertRaisesRegex(ValueError, '主入口'):
            common.validate_asar(self.archive)

    def test_remove_tree_refuses_outside_parent(self):
        outside = self.root / 'outside'
        outside.mkdir()
        with self.assertRaisesRegex(ValueError, '之外'):
            common.remove_tree(outside, self.resources)
        self.assertTrue(outside.exists())

    def test_proxy_launch_failure_is_visible_without_direct_fallback(self):
        (self.app / 'Antigravity-Proxy.ps1').write_text('fixture')
        failure = subprocess.CompletedProcess([], 1, b'', b'blocked by execution policy')
        with mock.patch.object(common.subprocess, 'CREATE_NO_WINDOW', 0x08000000, create=True), mock.patch.object(common.subprocess, 'run', return_value=failure) as run, mock.patch.object(common.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, '执行失败'):
                common.launch_application(self.app)
        run.assert_called_once()
        spawn.assert_not_called()

    def test_explicit_install_uses_custom_directory(self):
        self.assertEqual(common.discover_install(str(self.app)), self.app)
        with self.assertRaisesRegex(ValueError, 'app-dir'):
            common.discover_install(str(self.root))

    def test_unsupported_platform_still_rejected_for_explicit_install(self):
        with mock.patch.object(common.sys, 'platform', 'linux'):
            with self.assertRaisesRegex(ValueError, '仅支持 Windows 和 macOS'):
                common.discover_install(str(self.app))

    def test_stop_process_uses_utf8_and_exact_executable_path(self):
        result = subprocess.CompletedProcess([], 0, b'', b'')
        with mock.patch.object(common.subprocess, 'CREATE_NO_WINDOW', 0x08000000, create=True), mock.patch.object(common.subprocess, 'run', return_value=result) as run:
            common.stop_application(self.app)
        self.assertEqual(run.call_args.kwargs['input'].decode('utf-8'), str(self.app / 'Antigravity.exe'))
        import base64
        script = base64.b64decode(run.call_args.args[0][-1]).decode('utf-16-le')
        self.assertIn('[Console]::InputEncoding', script)
        self.assertIn('$process.ExecutablePath -ieq $target', script)


if __name__ == '__main__':
    unittest.main()
