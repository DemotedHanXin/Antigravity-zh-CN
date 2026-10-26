"""Isolated tests: never read or write the host's real shortcuts."""
import base64
import contextlib
import importlib.util
import io
import ipaddress
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
from urllib.parse import urlsplit
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
        self.app = self.root / '安装 目录'
        self.menu = self.root / 'Start Menu'
        self.desktop = self.root / 'Desktop'
        self.public = self.root / 'Public Start Menu'
        for path in (self.app, self.menu, self.desktop, self.public):
            path.mkdir()
        (self.app / 'Antigravity.exe').write_bytes(b'fixture executable')
        self.links = {}
        self.policy = 'RemoteSigned'
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.ps = mock.patch.object(TOOL, 'run_powershell', side_effect=self.bridge)
        self.ps_mock = self.ps.start()
        self.scanner = mock.patch.dict(os.environ, {'APPDATA': str(self.root / 'Roaming')})
        self.scanner.start()

    def tearDown(self):
        self.scanner.stop()
        self.ps.stop()
        self.output.__exit__(None, None, None)
        self.temp.cleanup()

    def args(self, extra=None, preview=False):
        return type('Args', (), {'app_dir': str(self.app), 'scan_root': extra or [], 'dry_run': preview})()

    def inventory(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def link(self, parent=None, arguments=''):
        path = (parent or self.desktop) / 'Antigravity.lnk'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixture shortcut')
        self.links[str(path)] = dict(path=str(path), target=str(self.app / 'Antigravity.exe'),
                                    arguments=arguments, icon=str(self.app / 'Antigravity.exe') + ',0',
                                    working_directory=str(self.app), window_style=1)
        return path

    def bridge(self, request):
        action = request['action']
        if action == 'policy':
            return {'effective': self.policy}
        if action == 'folders':
            return {'Desktop': str(self.desktop), 'StartMenu': str(self.menu), 'AllUsersStartMenu': str(self.public)}
        if action == 'read':
            return {'links': [dict(self.links[p], snapshot_hash=TOOL.sha256(Path(p).read_bytes()))
                              for p in request['paths'] if p in self.links], 'errors': []}
        if action == 'write':
            path = Path(request['path'])
            current_hash = TOOL.sha256(path.read_bytes()) if path.exists() else None
            if current_hash != request.get('before_hash'):
                raise RuntimeError('Shortcut changed since inspection')
            self.links[str(path)] = {key: request[key] for key in
                                    ('path', 'target', 'arguments', 'icon', 'working_directory')}
            self.links[str(path)]['window_style'] = request.get('window_style', 7)
            path.write_text(json.dumps(self.links[str(path)], ensure_ascii=False), encoding='utf-8')
            return {'saved': str(path)}
        if action == 'notify':
            return {'notified': True}
        self.fail('Unexpected action: ' + action)

    def test_scan_deduplicates_and_excludes_backup_and_git(self):
        (self.desktop / 'renamed.LNK').write_bytes(b'fake-shortcut')
        for name in ('antigravity-proxy-backups', 'Antigravity-proxy-backup-20261026', '.git'):
            folder = self.desktop / name
            folder.mkdir()
            (folder / 'Antigravity.lnk').write_bytes(b'backup')
        links, errors = TOOL.find_shortcuts([self.desktop, self.desktop])
        self.assertEqual(links, [str(self.desktop / 'renamed.LNK')])
        self.assertEqual(errors, [])

    def test_install_preview_creates_no_files_or_directories(self):
        self.link()
        before = self.inventory()
        directories = {p for p in self.root.rglob('*') if p.is_dir()}
        self.assertEqual(TOOL.install(self.args(preview=True)), 0)
        self.assertEqual(self.inventory(), before)
        self.assertEqual({p for p in self.root.rglob('*') if p.is_dir()}, directories)

    def test_install_has_no_backup_and_repeat_changes_nothing(self):
        target = self.link(arguments='--title "中文 a & b" --empty ""')
        before = set(self.inventory())
        self.assertEqual(TOOL.install(self.args()), 0)
        self.assertEqual(set(self.inventory()) - before, {
            str(Path('安装 目录') / 'Antigravity-Proxy.cmd'),
            str(Path('安装 目录') / 'Antigravity-Proxy.ps1'),
            str(Path('Start Menu') / 'Programs' / 'Antigravity (Proxy).lnk'),
        })
        self.assertEqual(TOOL.read_launcher_scan_roots(self.app), [])
        self.assertEqual(self.links[str(target)]['target'], str(self.app / 'Antigravity-Proxy.cmd'))
        after = self.inventory()
        self.assertEqual(TOOL.install(self.args()), 0)
        self.assertEqual(self.inventory(), after)

    def test_policy_rejection_changes_nothing(self):
        self.link()
        before = self.inventory()
        for policy in ('Restricted', 'AllSigned', 'unknown'):
            self.policy = policy
            with self.subTest(policy=policy), self.assertRaisesRegex(ValueError, '执行策略'):
                TOOL.install(self.args())
            self.assertEqual(self.inventory(), before)

    def test_explicit_missing_scan_root_changes_nothing(self):
        before = self.inventory()
        with self.assertRaisesRegex(ValueError, '自定义快捷方式目录'):
            TOOL.install(self.args([str(self.root / 'missing')]))
        self.assertEqual(self.inventory(), before)

    def test_custom_directories_are_recorded_and_merged_without_extra_files(self):
        custom = self.root / 'custom'
        custom2 = self.root / 'custom2'
        custom.mkdir()
        custom2.mkdir()
        target = self.link(custom)
        self.assertEqual(TOOL.install(self.args([str(custom)])), 0)
        self.assertEqual(TOOL.read_launcher_scan_roots(self.app), [str(custom.resolve())])
        self.assertEqual(TOOL.install(self.args([str(custom2)])), 0)
        self.assertEqual(set(TOOL.read_launcher_scan_roots(self.app)), {str(custom.resolve()), str(custom2.resolve())})
        self.assertEqual(self.links[str(target)]['target'], str(self.app / 'Antigravity-Proxy.cmd'))
        self.assertEqual({p.name for p in self.app.iterdir()},
                         {'Antigravity.exe', 'Antigravity-Proxy.cmd', 'Antigravity-Proxy.ps1'})

    def test_missing_recorded_directory_prevents_changes(self):
        custom = self.root / 'custom'
        custom.mkdir()
        self.assertEqual(TOOL.install(self.args([str(custom)])), 0)
        custom.rmdir()
        before = self.inventory()
        with self.assertRaisesRegex(ValueError, '自定义快捷方式目录'):
            TOOL.install(self.args())
        self.assertEqual(self.inventory(), before)

    def test_invalid_metadata_is_not_executed_or_overwritten(self):
        script = self.app / 'Antigravity-Proxy.ps1'
        script.write_text(TOOL.METADATA_PREFIX + '{"format":1,"scan_roots":"wrong"}\nthrow "never execute"', encoding='utf-8')
        before = self.inventory()
        with self.assertRaisesRegex(ValueError, '记录无效'):
            TOOL.install(self.args())
        self.assertEqual(self.inventory(), before)

    def test_public_shortcut_permission_failure_gets_personal_fallback(self):
        public_link = self.link(self.public / 'Programs')
        original = public_link.read_bytes()
        def bridge(request):
            if request['action'] == 'write' and request['path'] == str(public_link):
                raise PermissionError('Public Start Menu is read-only')
            return self.bridge(request)
        self.ps_mock.side_effect = bridge
        self.assertEqual(TOOL.install(self.args()), 2)
        self.assertEqual(public_link.read_bytes(), original)
        personal = self.menu / 'Programs' / 'Antigravity (Proxy).lnk'
        self.assertTrue(personal.is_file())
        self.assertEqual(self.links[str(personal)]['target'], str(self.app / 'Antigravity-Proxy.cmd'))

    def test_launcher_write_failure_rolls_back_before_shortcut_changes(self):
        target = self.link()
        before = self.inventory()
        original_atomic_write = TOOL.atomic_write
        def atomic_write(path, data):
            if path.name == 'Antigravity-Proxy.cmd':
                raise PermissionError('locked CMD')
            original_atomic_write(path, data)
        with mock.patch.object(TOOL, 'atomic_write', side_effect=atomic_write):
            with self.assertRaisesRegex(RuntimeError, '部署失败'):
                TOOL.install(self.args())
        self.assertEqual(self.inventory(), before)
        self.assertTrue(target.is_file())

    def test_interrupt_after_atomic_replace_rolls_back_both_launchers(self):
        self.link()
        before = self.inventory()
        original_atomic_write = TOOL.atomic_write
        def atomic_write(path, data):
            original_atomic_write(path, data)
            if path.name == 'Antigravity-Proxy.cmd':
                raise KeyboardInterrupt()
        with mock.patch.object(TOOL, 'atomic_write', side_effect=atomic_write):
            with self.assertRaises(KeyboardInterrupt):
                TOOL.install(self.args())
        self.assertEqual(self.inventory(), before)

    def test_failed_deployment_does_not_overwrite_concurrent_launcher_edit(self):
        script = self.app / 'Antigravity-Proxy.ps1'
        script.write_text('original user launcher', encoding='utf-8')
        original_atomic_write = TOOL.atomic_write
        def atomic_write(path, data):
            if path.name == 'Antigravity-Proxy.cmd':
                script.write_bytes(b'concurrent-user-edit')
                raise PermissionError('locked CMD')
            original_atomic_write(path, data)
        with mock.patch.object(TOOL, 'atomic_write', side_effect=atomic_write):
            with self.assertRaisesRegex(RuntimeError, '回退未完成'):
                TOOL.install(self.args())
        self.assertEqual(script.read_bytes(), b'concurrent-user-edit')
        self.assertFalse((self.app / 'Antigravity-Proxy.cmd').exists())

    def test_change_after_scan_is_not_overwritten(self):
        target = self.link()
        def bridge(request):
            result = self.bridge(request)
            if request['action'] == 'read':
                target.write_bytes(b'changed-by-user')
            return result
        self.ps_mock.side_effect = bridge
        with self.assertRaisesRegex(ValueError, '扫描后'):
            TOOL.install(self.args())
        self.assertEqual(target.read_bytes(), b'changed-by-user')
        self.assertFalse((self.app / 'Antigravity-Proxy.cmd').exists())

    def test_concurrent_change_at_bridge_write_is_not_overwritten(self):
        target = self.link()
        def bridge(request):
            if request['action'] == 'write' and request['path'] == str(target):
                target.write_bytes(b'changed-by-user')
            return self.bridge(request)
        self.ps_mock.side_effect = bridge
        self.assertEqual(TOOL.install(self.args()), 2)
        self.assertEqual(target.read_bytes(), b'changed-by-user')
        self.assertFalse((self.app / 'antigravity-proxy-backups').exists())

    def test_removed_restore_option_is_rejected(self):
        before = self.inventory()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            TOOL.main(['--restore', str(self.root)])
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(self.inventory(), before)


@unittest.skipUnless(sys.platform == 'win32', 'Windows PowerShell integration')
class NativeProxyTests(unittest.TestCase):
    def test_native_proxy_resolution_and_persistent_policy_read(self):
        # Run only resolver functions, never the launcher entry point or an app.
        prefix = TOOL.LAUNCHER_PS1.split('\ntry {\n', 1)[0]
        code = prefix + r"""
$ProgressPreference = 'SilentlyContinue'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$cases = [Console]::In.ReadToEnd() | ConvertFrom-Json
$results = @()
foreach ($case in $cases) {
    try {
        $configuration = Resolve-AntigravitySystemProxy -Enabled $case.enabled -Server $case.server -PacUrl $case.pac
        $results += @{ name = $case.name; mode = $configuration.Mode; http = $configuration.HTTP_PROXY; https = $configuration.HTTPS_PROXY; rejected = $false }
    } catch { $results += @{ name = $case.name; rejected = $true } }
}
$results | ConvertTo-Json -Compress
"""
        cases = [
            dict(name='mixed', enabled=True, server='127.0.0.1:10808', pac=''),
            dict(name='split', enabled=True, server='http=127.0.0.1:8000;https=127.0.0.1:8001', pac=''),
            dict(name='ipv6', enabled=True, server='http://[::1]:10808', pac=''),
            dict(name='disabled', enabled=False, server='', pac=''),
            dict(name='PAC', enabled=False, server='', pac='http://local/proxy.pac'),
            dict(name='SOCKS', enabled=True, server='socks=127.0.0.1:1080', pac=''),
        ]
        encoded = base64.b64encode(code.encode('utf-16-le')).decode('ascii')
        result = subprocess.run([str(TOOL.powershell_path()), '-NoLogo', '-NoProfile', '-NonInteractive',
                                 '-EncodedCommand', encoded],
                                input=json.dumps(cases).encode('utf-8'), capture_output=True, timeout=30,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        values = {item['name']: item for item in json.loads(result.stdout.decode('utf-8-sig'))}
        self.assertEqual(values['mixed']['https'], 'http://127.0.0.1:10808')
        self.assertEqual(values['split']['http'], 'http://127.0.0.1:8000')
        self.assertEqual(values['split']['https'], 'http://127.0.0.1:8001')
        ipv6 = urlsplit(values['ipv6']['https'])
        self.assertEqual(ipaddress.ip_address(ipv6.hostname), ipaddress.ip_address('::1'))
        self.assertEqual(ipv6.port, 10808)
        self.assertEqual(values['disabled']['mode'], 'DirectOrTun')
        self.assertEqual(values['disabled']['https'], '')
        self.assertTrue(values['PAC']['rejected'])
        self.assertTrue(values['SOCKS']['rejected'])
        policy = TOOL.run_powershell({'action': 'policy'})
        self.assertIn(policy['effective'], ('Restricted', 'AllSigned', 'RemoteSigned', 'Unrestricted', 'Bypass'))



if __name__ == '__main__':
    unittest.main()
