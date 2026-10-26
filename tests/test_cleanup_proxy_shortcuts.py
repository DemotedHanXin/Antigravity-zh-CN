"""Cleanup tests use only fixture bytes and mock every PowerShell invocation."""
import contextlib
import base64
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / 'Cleanup-Proxy-Shortcuts.py'
SPEC = importlib.util.spec_from_file_location('cleanup_proxy_shortcuts', SCRIPT)
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.cleanup-unit-', dir=str(SCRIPT.parent))
        self.root = Path(self.temp.name)
        self.app = self.root / '安装 目录'
        self.desktop = self.root / '桌面'
        self.app.mkdir()
        self.desktop.mkdir()
        (self.app / 'Antigravity.exe').write_bytes(b'original application')
        for name in TOOL.LAUNCHERS:
            (self.app / name).write_bytes(('launcher ' + name).encode())
        self.links = {}
        self.setup = TOOL.load_setup()
        self.setup.run_powershell = mock.Mock(side_effect=self.bridge)
        self.setup.scan_roots = lambda folders, extra: [self.desktop] + [Path(p) for p in extra]
        self.setup.discover_install = lambda path=None: self.app
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()

    def tearDown(self):
        self.output.__exit__(None, None, None)
        self.temp.cleanup()

    def link(self, name, target, parent=None, arguments=''):
        path = (parent or self.desktop) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(('binary fixture ' + str(path)).encode('utf-8'))
        self.links[str(path)] = {
            'target': str(target), 'arguments': arguments, 'icon': 'custom.ico,4',
            'working_directory': str(self.root / '项目 目录'), 'window_style': 7,
        }
        return path

    def bridge(self, request):
        if request['action'] == 'folders':
            return {'Desktop': str(self.desktop)}
        if request['action'] == 'notify':
            return {'notified': True}
        if request['action'] == 'read':
            return {'links': [
                dict(self.links[p], path=p,
                     snapshot_hash=TOOL.digest(Path(p).read_bytes()))
                for p in request['paths'] if p in self.links and Path(p).is_file()
            ], 'errors': []}
        if request['action'] == 'write':
            path = Path(request['path'])
            self.assertEqual(TOOL.digest(path.read_bytes()), request['before_hash'])
            value = {key: request[key] for key in (
                'target', 'arguments', 'icon', 'working_directory', 'window_style')}
            self.links[str(path)] = value
            path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            return {'saved': str(path)}
        self.fail('Unexpected PowerShell action: ' + request['action'])

    def plan(self):
        return TOOL.plan_cleanup(self.app, [], self.setup)

    def setup_backup(self, recorded_link=None):
        folder = self.app / TOOL.SETUP_BACKUPS / '20261026-test'
        folder.mkdir(parents=True)
        original = b'original shortcut bytes'
        (folder / '0000.bin').write_bytes(original)
        entry = {'path': str(recorded_link or self.app / TOOL.LAUNCHERS[0]),
                 'backup': '0000.bin', 'before_hash': TOOL.digest(original),
                 'after_hash': 'test'}
        manifest = {'format': 1, 'app_dir': str(self.app), 'entries': [entry]}
        (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return folder

    def test_exact_targets_only_and_renamed_shortcuts(self):
        cmd_link = self.link('改名.lnk', self.app / TOOL.LAUNCHERS[0])
        ps_link = self.link('脚本入口.lnk', self.app / TOOL.LAUNCHERS[1])
        self.link('Antigravity.lnk', self.app / 'Antigravity.exe')
        self.link('另一个安装.lnk', self.root / 'other' / TOOL.LAUNCHERS[0])
        planned = {e['path'] for e in self.plan()['entries'] if e['kind'] == 'shortcut'}
        self.assertEqual(planned, {str(cmd_link), str(ps_link)})

    def test_recorded_custom_shortcut_is_scanned(self):
        custom = self.link('custom.lnk', self.app / TOOL.LAUNCHERS[0], self.root / 'custom')
        self.setup_backup(custom)
        planned = {e['path'] for e in self.plan()['entries'] if e['kind'] == 'shortcut'}
        self.assertIn(str(custom), planned)

    def test_old_setup_backups_and_unknown_extra_files_are_preserved(self):
        folder = self.setup_backup()
        extra = folder / 'user-notes.txt'
        extra.write_bytes(b'user content')
        inventory = {str(p): p.read_bytes() for p in folder.iterdir()}
        plan = self.plan()
        self.assertTrue(all(e['kind'] != 'setup_backup' for e in plan['entries']))
        self.assertEqual(TOOL.apply_cleanup(plan, self.setup), 0)
        self.assertTrue(all(Path(p).read_bytes() == data for p, data in inventory.items()))
        self.assertEqual(extra.read_bytes(), b'user content')
        self.assertTrue(folder.is_dir())

    def test_scan_errors_abort_plan(self):
        self.setup.run_powershell.side_effect = lambda request: (
            {'links': [], 'errors': ['fixture permission denied']}
            if request['action'] == 'read' else {'Desktop': str(self.desktop)})
        with self.assertRaisesRegex(ValueError, '扫描不完整'):
            self.plan()
        self.assertEqual(set(self.root.iterdir()), {self.app, self.desktop})

    def test_snapshot_change_is_rejected_during_plan(self):
        target = self.link('proxy.lnk', self.app / TOOL.LAUNCHERS[0])

        def bridge(request):
            result = self.bridge(request)
            if request['action'] == 'read':
                target.write_bytes(b'user edit during inspection')
            return result

        self.setup.run_powershell.side_effect = bridge
        with self.assertRaisesRegex(ValueError, '扫描后'):
            self.plan()
        self.assertEqual(target.read_bytes(), b'user edit during inspection')

    def test_dry_run_creates_no_archive_or_mutations(self):
        target = self.link('proxy.lnk', self.app / TOOL.LAUNCHERS[0])
        original = target.read_bytes()
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with mock.patch.object(TOOL, 'load_setup', return_value=self.setup):
            self.assertEqual(TOOL.main(['--dry-run']), 0)
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual({str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}, before)
        self.assertTrue((self.app / TOOL.LAUNCHERS[0]).is_file())

    def test_cleanup_deletes_only_launchers_without_creating_files(self):
        arguments = '--profile "D:\\中文 路径\\" --title "a & b" --empty ""'
        encoded = base64.b64encode(arguments.encode('utf-8')).decode('ascii')
        target = self.link('代理.lnk', self.app / TOOL.LAUNCHERS[0],
                           arguments='-ShortcutArgsBase64 ' + encoded)
        direct = self.link('原程序.lnk', self.app / 'Antigravity.exe')
        old_backup = self.setup_backup(target)
        old_backup_bytes = {str(p): p.read_bytes() for p in old_backup.iterdir()}
        plan = self.plan()
        before_files = {p for p in self.root.rglob('*') if p.is_file()}
        before_directories = {p for p in self.root.rglob('*') if p.is_dir()}
        direct_bytes = direct.read_bytes()
        self.setup.atomic_write = mock.Mock(side_effect=AssertionError('Cleanup must not write backup files'))
        self.setup.Backup = mock.Mock(side_effect=AssertionError('Cleanup must not create a backup'))
        self.assertEqual(TOOL.apply_cleanup(plan, self.setup), 0)
        self.assertTrue(target.is_file())
        self.assertTrue(all(not (self.app / name).exists() for name in TOOL.LAUNCHERS))
        self.assertEqual(self.links[str(target)]['target'], str(self.app / 'Antigravity.exe'))
        self.assertEqual(self.links[str(target)]['arguments'], arguments)
        self.assertEqual(self.links[str(target)]['icon'], 'custom.ico,4')
        self.assertEqual(self.links[str(target)]['working_directory'], str(self.root / '项目 目录'))
        self.assertEqual(self.links[str(target)]['window_style'], 1)
        self.assertEqual(direct.read_bytes(), direct_bytes)
        self.assertTrue((self.app / 'Antigravity.exe').is_file())
        self.assertTrue(all(Path(p).read_bytes() == data for p, data in old_backup_bytes.items()))
        self.assertEqual({p for p in self.root.rglob('*') if p.is_file()},
                         before_files - {self.app / name for name in TOOL.LAUNCHERS})
        self.assertEqual({p for p in self.root.rglob('*') if p.is_dir()}, before_directories)
        after = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(TOOL.apply_cleanup(self.plan(), self.setup), 0)
        self.assertEqual({str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}, after)
        self.setup.atomic_write.assert_not_called()
        self.setup.Backup.assert_not_called()

    def test_changed_file_before_apply_prevents_all_deletion(self):
        target = self.link('proxy.lnk', self.app / TOOL.LAUNCHERS[0])
        plan = self.plan()
        target.write_bytes(b'user edit after preview')
        with self.assertRaisesRegex(ValueError, '预览后'):
            TOOL.apply_cleanup(plan, self.setup)
        self.assertEqual(target.read_bytes(), b'user edit after preview')
        self.assertTrue(all((self.app / name).is_file() for name in TOOL.LAUNCHERS))

    def test_shortcut_retarget_failure_retains_launchers(self):
        target = self.link('proxy.lnk', self.app / TOOL.LAUNCHERS[0])
        plan = self.plan()
        original = target.read_bytes()
        def bridge(request):
            if request['action'] == 'write':
                raise PermissionError('fixture locked shortcut')
            return self.bridge(request)
        self.setup.run_powershell.side_effect = bridge
        self.assertEqual(TOOL.apply_cleanup(plan, self.setup), 2)
        self.assertTrue(target.is_file())
        self.assertEqual(target.read_bytes(), original)
        self.assertTrue(all((self.app / name).is_file() for name in TOOL.LAUNCHERS))

    def test_new_shortcut_detected_before_launcher_deletion(self):
        target = self.link('proxy.lnk', self.app / TOOL.LAUNCHERS[0])
        plan = self.plan()
        def bridge(request):
            result = self.bridge(request)
            if request['action'] == 'write':
                self.link('new.lnk', self.app / TOOL.LAUNCHERS[0])
            return result
        self.setup.run_powershell.side_effect = bridge
        self.assertEqual(TOOL.apply_cleanup(plan, self.setup), 2)
        self.assertTrue(target.is_file())
        self.assertTrue((self.desktop / 'new.lnk').is_file())
        self.assertTrue(all((self.app / name).is_file() for name in TOOL.LAUNCHERS))

    def test_removed_backup_and_restore_options_are_rejected(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        for option in ('--backup-dir', '--restore'):
            with self.subTest(option=option), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    TOOL.main([option, str(self.root / 'unused')])
                self.assertEqual(raised.exception.code, 2)
        self.assertEqual({str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}, before)

    def test_launcher_delete_failure_preserves_all_shortcuts(self):
        target = self.link('proxy.lnk', self.app / TOOL.LAUNCHERS[0])
        plan = self.plan()
        original_unlink = Path.unlink

        def unlink(path, *args, **kwargs):
            if path == self.app / TOOL.LAUNCHERS[0]:
                raise PermissionError('fixture locked launcher')
            return original_unlink(path, *args, **kwargs)

        with mock.patch.object(Path, 'unlink', unlink):
            self.assertEqual(TOOL.apply_cleanup(plan, self.setup), 2)
        self.assertTrue(target.is_file())
        self.assertEqual(self.links[str(target)]['target'], str(self.app / 'Antigravity.exe'))
        self.assertTrue(all((self.app / name).is_file() for name in TOOL.LAUNCHERS))

    def test_strict_original_argument_decode(self):
        original = '--new-window "D:\\中文 a&b" ""'
        encoded = base64.b64encode(original.encode('utf-8')).decode('ascii')
        self.assertEqual(TOOL.decode_shortcut_arguments(''), '')
        self.assertEqual(TOOL.decode_shortcut_arguments('-ShortcutArgsBase64 ' + encoded), original)
        self.assertEqual(TOOL.decode_shortcut_arguments('-ShortcutArgsBase64 "' + encoded + '"'), original)
        for value in ('-Diagnose', '-File something.ps1', '-ShortcutArgsBase64 ???',
                      '-ShortcutArgsBase64 /w==', '-ShortcutArgsBase64 AA=='):
            with self.subTest(value=value), self.assertRaises(ValueError):
                TOOL.decode_shortcut_arguments(value)

    def test_unknown_launcher_arguments_abort_without_deletion(self):
        target = self.link('proxy.lnk', self.app / TOOL.LAUNCHERS[0], arguments='-Diagnose')
        before = target.read_bytes()
        with self.assertRaisesRegex(ValueError, '未知启动参数'):
            self.plan()
        self.assertEqual(target.read_bytes(), before)
        self.assertTrue(all((self.app / name).is_file() for name in TOOL.LAUNCHERS))

    def test_missing_executable_aborts_plan(self):
        (self.app / 'Antigravity.exe').unlink()
        with self.assertRaisesRegex(ValueError, '未找到 Antigravity.exe'):
            self.plan()
        self.assertTrue(all((self.app / name).is_file() for name in TOOL.LAUNCHERS))

if __name__ == '__main__':
    unittest.main()
