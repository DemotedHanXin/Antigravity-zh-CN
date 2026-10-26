"""Isolated tests: never read or write the host's real shortcuts."""
import base64
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / 'Setup-Proxy-Shortcuts.py'
SPEC = importlib.util.spec_from_file_location('proxy_shortcuts', SCRIPT)
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.app = Path(r'C:\Users\测试 用户\Antigravity')

    def link(self, target, arguments='', name='Renamed.lnk'):
        return {
            'path': str(Path(r'C:\测试 桌面') / name),
            'target': str(target), 'arguments': arguments,
            'icon': 'custom.ico,4', 'working_directory': r'D:\我的项目',
        }

    def test_matches_destination_even_when_shortcut_renamed(self):
        plans, ready, warnings = TOOL.make_plan(
            [self.link(self.app / 'Antigravity.exe')], self.app)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['target'], str(self.app / 'Antigravity-Proxy.cmd'))
        self.assertEqual(plans[0]['icon'], 'custom.ico,4')
        self.assertEqual(plans[0]['working_directory'], r'D:\我的项目')
        self.assertEqual((ready, warnings), ([], []))

    def test_same_name_other_install_or_program_is_untouched(self):
        links = [self.link(Path(r'D:\Other') / 'Antigravity.exe', name='Antigravity.lnk'),
                 self.link(Path(r'C:\Windows') / 'notepad.exe', name='Antigravity.lnk')]
        self.assertEqual(TOOL.make_plan(links, self.app), ([], [], []))

    def test_existing_proxy_link_is_idempotent(self):
        link = self.link(self.app / 'Antigravity-Proxy.cmd')
        self.assertEqual(TOOL.make_plan([link], self.app), ([], [link['path']], []))

    def test_existing_unknown_proxy_arguments_are_not_erased(self):
        link = self.link(self.app / 'Antigravity-Proxy.cmd', '--custom-data')
        plans, ready, warnings = TOOL.make_plan([link], self.app)
        self.assertEqual((plans, ready), ([], []))
        self.assertEqual(len(warnings), 1)

    def test_arguments_round_trip_unicode_quotes_and_shell_metacharacters(self):
        original = '--project "D:\\资料 目录\\" --title "a & b" --empty "" --percent "%TEMP%"'
        plans, _, _ = TOOL.make_plan(
            [self.link(self.app / 'Antigravity.exe', original)], self.app)
        prefix, encoded = plans[0]['arguments'].split(' ', 1)
        self.assertEqual(prefix, '-ShortcutArgsBase64')
        self.assertEqual(base64.b64decode(encoded).decode('utf-8'), original)
        self.assertEqual(TOOL.shortcut_arguments(''), '')

    def test_encoded_proxy_link_is_idempotent(self):
        link = self.link(self.app / 'Antigravity-Proxy.cmd',
                         TOOL.shortcut_arguments('--project "中文 路径"'))
        self.assertEqual(TOOL.make_plan([link], self.app), ([], [link['path']], []))

    def test_path_normalization(self):
        self.assertEqual(TOOL.path_key('"C:\\Demo\\x\\..\\Antigravity.exe"'),
                         TOOL.path_key('c:/demo/ANTIGRAVITY.EXE'))

    def test_default_icon_is_pinned_to_original_executable(self):
        link = self.link(self.app / 'Antigravity.exe')
        link['icon'] = ',0'
        plans, _, _ = TOOL.make_plan([link], self.app)
        self.assertEqual(plans[0]['icon'], str(self.app / 'Antigravity.exe') + ',0')

    def test_existing_proxy_default_icon_is_repaired_once(self):
        link = self.link(self.app / 'Antigravity-Proxy.cmd')
        link['icon'] = ',0'
        plans, ready, _ = TOOL.make_plan([link], self.app)
        self.assertEqual(len(plans), 1)
        self.assertEqual(ready, [])
        link['icon'] = plans[0]['icon']
        self.assertEqual(TOOL.make_plan([link], self.app), ([], [link['path']], []))


class FilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.antigravity-unit-', dir=str(SCRIPT.parent))
        self.root = Path(self.temp.name)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.ps = mock.patch.object(TOOL, 'run_powershell', return_value={'notified': True})
        self.ps_mock = self.ps.start()

    def tearDown(self):
        self.ps.stop()
        self.output.__exit__(None, None, None)
        self.temp.cleanup()

    def test_scan_deduplicates_and_excludes_backup_and_git(self):
        desktop = self.root / '中文 桌面'
        desktop.mkdir()
        (desktop / 'renamed.LNK').write_bytes(b'fake-shortcut')
        for name in ('antigravity-proxy-backups', 'Antigravity-proxy-backup-20261026', '.git'):
            folder = desktop / name
            folder.mkdir()
            (folder / 'Antigravity.lnk').write_bytes(b'backup')
        (desktop / 'unrelated.txt').write_text('unrelated', encoding='utf-8')
        links, errors = TOOL.find_shortcuts([desktop, desktop])
        self.assertEqual(links, [str(desktop / 'renamed.LNK')])
        self.assertEqual(errors, [])

    def test_install_preview_creates_no_launchers_shortcuts_or_backups(self):
        (self.root / 'Antigravity.exe').write_bytes(b'fake-executable')
        menu = self.root / 'Start Menu'

        def bridge(request):
            if request['action'] == 'folders':
                return {'StartMenu': str(menu)}
            if request['action'] == 'read':
                return {'links': [], 'errors': []}
            self.fail('Preview called a mutating bridge action')

        args = type('Args', (), {'app_dir': str(self.root), 'scan_root': [], 'dry_run': True})()
        with mock.patch.object(TOOL, 'run_powershell', side_effect=bridge):
            self.assertEqual(TOOL.install(args), 0)
        self.assertEqual([path.name for path in self.root.iterdir()], ['Antigravity.exe'])

    def test_restore_existing_file_exactly_and_repeat(self):
        target = self.root / '中文 快捷方式.lnk'
        original = bytes(range(256))
        target.write_bytes(original)
        backup = TOOL.Backup(self.root)
        entry = backup.prepare(target)
        TOOL.atomic_write(target, b'repaired')
        backup.complete(entry)
        self.assertEqual(TOOL.restore_backup(backup.folder), 0)
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(TOOL.restore_backup(backup.folder), 0)
        self.assertEqual(target.read_bytes(), original)

    def test_restore_removes_only_new_files(self):
        target = self.root / 'Antigravity-Proxy.cmd'
        backup = TOOL.Backup(self.root)
        entry = backup.prepare(target)
        target.write_bytes(b'new launcher')
        backup.complete(entry)
        self.assertEqual(TOOL.restore_backup(backup.folder), 0)
        self.assertFalse(target.exists())

    def test_restore_dry_run_does_not_modify_or_notify(self):
        target = self.root / 'example.lnk'
        target.write_bytes(b'old')
        backup = TOOL.Backup(self.root)
        entry = backup.prepare(target)
        target.write_bytes(b'new')
        backup.complete(entry)
        self.assertEqual(TOOL.restore_backup(backup.folder, preview=True), 0)
        self.assertEqual(target.read_bytes(), b'new')
        self.ps_mock.assert_not_called()

    def test_restore_preserves_user_changes(self):
        target = self.root / 'example.lnk'
        target.write_bytes(b'old')
        backup = TOOL.Backup(self.root)
        entry = backup.prepare(target)
        target.write_bytes(b'repaired')
        backup.complete(entry)
        target.write_bytes(b'user-changed-icon')
        self.assertEqual(TOOL.restore_backup(backup.folder), 2)
        self.assertEqual(target.read_bytes(), b'user-changed-icon')

    def test_corrupt_backup_is_not_applied(self):
        target = self.root / 'example.lnk'
        target.write_bytes(b'original')
        backup = TOOL.Backup(self.root)
        entry = backup.prepare(target)
        target.write_bytes(b'repaired')
        backup.complete(entry)
        (backup.folder / entry['backup']).write_bytes(b'corrupt')
        self.assertEqual(TOOL.restore_backup(backup.folder), 2)
        self.assertEqual(target.read_bytes(), b'repaired')

    def test_restore_conflict_keeps_required_launcher(self):
        launcher = self.root / 'Antigravity-Proxy.cmd'
        target = self.root / 'example.lnk'
        target.write_bytes(b'original-link')
        backup = TOOL.Backup(self.root)
        launcher_entry = backup.prepare(launcher)
        launcher.write_bytes(b'new-launcher')
        backup.complete(launcher_entry)
        link_entry = backup.prepare(target)
        target.write_bytes(b'repaired-link-targeting-proxy')
        backup.complete(link_entry)
        target.write_bytes(b'user-changed-icon-still-targeting-proxy')
        self.assertEqual(TOOL.restore_backup(backup.folder), 2)
        self.assertTrue(launcher.exists(), 'A conflicting shortcut may still need this launcher')
        self.assertEqual(target.read_bytes(), b'user-changed-icon-still-targeting-proxy')

    def test_concurrent_change_rejected_before_write_is_not_owned(self):
        app = self.root / 'app'
        menu = self.root / 'Start Menu'
        app.mkdir()
        programs = menu / 'Programs'
        programs.mkdir(parents=True)
        (app / 'Antigravity.exe').write_bytes(b'fake-executable')
        (app / 'Antigravity-Proxy.cmd').write_bytes(TOOL.LAUNCHER_CMD.replace('\n', '\r\n').encode('ascii'))
        (app / 'Antigravity-Proxy.ps1').write_bytes(TOOL.LAUNCHER_PS1.replace('\n', '\r\n').encode('utf-8-sig'))
        target = programs / 'Antigravity.lnk'
        target.write_bytes(b'original-link')

        def bridge(request):
            if request['action'] == 'folders':
                return {'StartMenu': str(menu)}
            if request['action'] == 'read':
                return {'links': [{'path': str(target), 'target': str(app / 'Antigravity.exe'), 'arguments': '', 'snapshot_hash': TOOL.sha256(target.read_bytes())}], 'errors': []}
            if request['action'] == 'write':
                target.write_bytes(b'concurrent-user-edit')
                raise RuntimeError('Shortcut changed since inspection; refusing to overwrite it.')
            return {'notified': True}

        args = type('Args', (), {'app_dir': str(app), 'scan_root': [], 'dry_run': False})()
        with mock.patch.object(TOOL, 'run_powershell', side_effect=bridge):
            self.assertEqual(TOOL.install(args), 2)
        manifests = list((app / 'antigravity-proxy-backups').glob('*/manifest.json'))
        self.assertEqual(len(manifests), 1)
        manifest = json.loads(manifests[0].read_text(encoding='utf-8'))
        entry = next(item for item in manifest['entries'] if item['path'] == str(target))
        self.assertIsNone(entry['after_hash'], 'A rejected write must not claim ownership of concurrent user changes')

    def test_change_after_scan_before_backup_is_not_overwritten(self):
        app = self.root / 'app'
        menu = self.root / 'Start Menu'
        app.mkdir()
        programs = menu / 'Programs'
        programs.mkdir(parents=True)
        (app / 'Antigravity.exe').write_bytes(b'fake-executable')
        (app / 'Antigravity-Proxy.cmd').write_bytes(TOOL.LAUNCHER_CMD.replace('\n', '\r\n').encode('ascii'))
        (app / 'Antigravity-Proxy.ps1').write_bytes(TOOL.LAUNCHER_PS1.replace('\n', '\r\n').encode('utf-8-sig'))
        target = programs / 'Antigravity.lnk'
        target.write_bytes(b'original-link')
        write_calls = []

        def bridge(request):
            if request['action'] == 'folders':
                return {'StartMenu': str(menu)}
            if request['action'] == 'read':
                snapshot_hash = TOOL.sha256(target.read_bytes())
                target.write_bytes(b'changed-target-to-another-app')
                return {'links': [{'path': str(target), 'target': str(app / 'Antigravity.exe'), 'arguments': '', 'snapshot_hash': snapshot_hash}], 'errors': []}
            if request['action'] == 'write':
                write_calls.append(request)
                target.write_bytes(b'tool-overwrite')
                return {'saved': str(target)}
            return {'notified': True}

        args = type('Args', (), {'app_dir': str(app), 'scan_root': [], 'dry_run': False})()
        with mock.patch.object(TOOL, 'run_powershell', side_effect=bridge):
            self.assertEqual(TOOL.install(args), 2)
        self.assertEqual(write_calls, [])
        self.assertEqual(target.read_bytes(), b'changed-target-to-another-app')


if __name__ == '__main__':
    unittest.main()
