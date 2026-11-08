"""Desktop adapters for the existing, shared command-line implementation.

No installation is modified by importing this module or reading its status.
The UI runs expensive calls on a worker thread. Raw details remain in memory;
exported diagnostics deliberately contain only an allowlist of metadata.
"""
from __future__ import annotations

import contextlib
import copy
import ctypes
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from types import SimpleNamespace


SOURCE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'src'
# The legacy scripts use a normal import for their common module. All packaged
# source files live beside each other, just as they do for command-line users.
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))
import antigravity_common as common

_MODULES = {}
_MODULE_LOCK = threading.Lock()
_TASK_LOCK = threading.Lock()  # stdout redirection is process-global
_TARGET_LOCKS = {}
_TARGET_LOCK_GUARD = threading.Lock()


def _module(name):
    with _MODULE_LOCK:
        if name not in _MODULES:
            spec = importlib.util.spec_from_file_location(
                'antigravity_desktop_' + name.replace('-', '_'), SOURCE / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _MODULES[name] = module
        return _MODULES[name]


@dataclass
class Installation:
    path: str = ''
    version: str = '未知'
    state: str = 'missing'
    can_patch: bool = False
    can_restore: bool = False
    proxy: str = 'absent'
    warnings: list[str] = field(default_factory=list)
    message: str = ''
    applied_revision: int | None = None
    dictionary_hash: str | None = None


@dataclass
class TaskResult:
    status: str
    action: str
    message: str
    details: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    next_step: str = ''
    installation: Installation | None = None
    items: list[dict] = field(default_factory=list)

    @property
    def ok(self):
        return self.status == 'success'


@contextlib.contextmanager
def _installation_lock(path):
    """Nonblocking per-install lock, released automatically after a crash.

Windows named mutexes also cover other assistant instances in this session.
Legacy CLI tools and official updaters do not participate in this mutex; the
shared core still checks installation and shortcut snapshots before writes.
"""
    key = os.path.normcase(str(Path(path).resolve()))
    if sys.platform == 'win32':
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        name = 'Local\\AntigravityZhCN-' + hashlib.sha256(key.encode('utf-8')).hexdigest()
        handle = kernel.CreateMutexW(None, False, name)
        if not handle:
            raise OSError(ctypes.get_last_error(), '无法创建安装任务锁。')
        acquired = False
        try:
            result = kernel.WaitForSingleObject(handle, 0)
            acquired = result in (0, 0x80)  # WAIT_OBJECT_0 / abandoned owner
            if not acquired:
                raise RuntimeError('另一窗口正在操作此安装，请等待完成后重试。')
            yield
        finally:
            if acquired:
                kernel.ReleaseMutex(handle)
            kernel.CloseHandle(handle)
    else:
        with _TARGET_LOCK_GUARD:
            lock = _TARGET_LOCKS.setdefault(key, threading.Lock())
        if not lock.acquire(False):
            raise RuntimeError('另一任务正在操作此安装，请等待完成后重试。')
        try:
            yield
        finally:
            lock.release()


class _ProgressStream(io.StringIO):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.pending = ''

    def write(self, text):
        count = super().write(text)
        self.pending += text
        while '\n' in self.pending:
            line, self.pending = self.pending.split('\n', 1)
            if line.strip() and self.callback:
                # A presentation callback must never abort an installation.
                try:
                    self.callback(line.strip())
                except Exception:
                    pass
        return count


def _exists(path):
    return path.exists() or path.is_symlink()


def _regular(path):
    info = common._no_link(path)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('预期文件不是普通文件：' + str(path))


def _read_marker(application):
    path = application / '.antigravity-zhcn.json'
    if not path.is_file():
        return None, None
    _regular(path)
    if path.stat().st_size > 4096:
        raise ValueError('汉化应用记录过大，无法核对词典版本。')
    value = json.loads(path.read_text(encoding='utf-8'))
    revision = value.get('dictionaryRevision')
    fingerprint = value.get('dictionaryHash')
    if (value.get('schemaVersion') != 1 or type(revision) is not int or revision < 0
            or not isinstance(fingerprint, str) or not re.fullmatch('[0-9a-f]{64}', fingerprint)):
        raise ValueError('汉化应用记录无效，无法核对词典版本。')
    return revision, fingerprint


class AppService:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir is not None else None
        self._events = []
        self._previews = {}

    def inspect(self, path=None):
        """Verify archives, active entry and patch targets without any writes."""
        result = Installation(path=str(path or ''))
        try:
            root = common.discover_install(path)
            result.path = str(root)
            common._no_link(root)
            resources = common.resources_dir(root)
            common._no_link(resources)
            _regular(root / ('Contents/MacOS/Antigravity' if sys.platform == 'darwin' else 'Antigravity.exe'))
            launchers = [root / 'Antigravity-Proxy.cmd', root / 'Antigravity-Proxy.ps1']
            present = [_exists(item) for item in launchers]
            if any(present):
                try:
                    for item in launchers:
                        _regular(item)
                    result.proxy = 'installed'
                except (OSError, ValueError):
                    result.proxy = 'incomplete'
                    result.warnings.append('代理启动文件不完整或不是普通文件；请预览后重新配置。')
            archive, disabled = resources / 'app.asar', resources / 'app.asar.disabled'
            application = resources / 'app'
            if _exists(archive) and _exists(disabled):
                result.state = 'conflict'
                result.message = '官方归档与保留归档同时存在；请先核对官方更新或修复安装。'
                return result
            source = disabled if _exists(disabled) else archive
            checked = common.validate_asar(source, unpacked_dir=resources / 'app.asar.unpacked')
            result.can_restore = True
            with source.open('rb') as stream:
                package = json.loads(common._read_entry(stream, checked['records']['package.json'], 'bytes').decode('utf-8-sig'))
            result.version = str(package.get('version') or '未知')[:100]
            required = _module('Antigravity-Patcher').REQUIRED_PATCH_FILES
            missing = [name for name in required if name not in checked['records']]
            result.can_patch = not missing
            if missing:
                result.warnings.append('当前版本缺少汉化目标，禁止应用汉化：' + '、'.join(missing))
            if source == archive and not _exists(application):
                result.state = 'original'
                result.message = '官方归档及主入口校验通过。'
            elif source == disabled and _exists(application):
                common.validate_extracted_app(application, required)
                preload = common._contained(application, 'dist/preload.js')
                if 'Antigravity Chinese Localization Engine' not in preload.read_text(encoding='utf-8'):
                    raise ValueError('解包入口可用，但未识别到本项目汉化标记；可以从原版重新应用或还原。')
                result.state = 'localized'
                result.message = '汉化入口与保留的官方归档校验通过。'
                try:
                    result.applied_revision, result.dictionary_hash = _read_marker(application)
                except (OSError, ValueError, AttributeError) as error:
                    result.warnings.append(str(error))
            else:
                result.state = 'invalid'
                result.message = '安装入口状态异常；原版归档有效，可重新应用汉化或恢复英文。'
            leftovers = list(resources.glob('.antigravity-*'))
            if leftovers:
                result.warnings.append('存在上次操作的暂存或恢复目录，请查看会话详情并保留恢复材料。')
        except (OSError, ValueError, RuntimeError, KeyError, UnicodeError) as error:
            result.state = 'invalid' if path or result.path else 'missing'
            result.message = str(error)
            result.warnings.append(str(error))
        return result

    @staticmethod
    def proxy_status():
        """Read configuration kind only; neither disclose credentials nor probe."""
        status = {'mode': 'unknown', 'label': '无法读取系统代理', 'connection': '未测试连接'}
        if sys.platform != 'win32':
            return status
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
                def read(name, default=''):
                    try:
                        return winreg.QueryValueEx(key, name)[0]
                    except FileNotFoundError:
                        return default
                enabled, server, pac = read('ProxyEnable', 0), str(read('ProxyServer')), str(read('AutoConfigURL'))
            if pac.strip():
                status.update(mode='pac', label='PAC 自动代理脚本（启动器不支持）')
            elif not enabled:
                status.update(mode='direct', label='系统代理未启用（直连或 TUN）')
            elif not server.strip():
                status.update(mode='invalid', label='系统代理已启用，但未配置地址')
            elif '=' in server and not re.search(r'(?:^|[;\s])https=', server, re.I):
                status.update(mode='unsupported', label='分协议代理缺少 HTTPS 配置')
            else:
                status.update(mode='system', label='Windows 手动系统代理（配置待启动器校验）')
        except OSError:
            pass
        return status

    def _proxy_plan(self, action, root, roots):
        setup = _module('Setup-Proxy-Shortcuts')
        if action == 'proxy_preview':
            output = io.StringIO()
            snapshots = []
            original_plan = setup.make_plan
            def capture_plan(links, app_dir):
                snapshots.append(copy.deepcopy(links))
                return original_plan(links, app_dir)
            # Observe the shared core's actual scan; do not maintain a second
            # shortcut matching algorithm. This private module is serialized by
            # _TASK_LOCK and is never the CLI's module instance.
            setup.make_plan = capture_plan
            try:
                with contextlib.redirect_stdout(output):
                    code = setup.install(SimpleNamespace(app_dir=str(root), scan_root=list(roots), dry_run=True))
            finally:
                setup.make_plan = original_plan
            lines = output.getvalue().splitlines()
            items = [{'path': line[len('[计划修复] '):].split(' -> ', 1)[0],
                      'action': '配置代理启动', 'status': '待执行'}
                     for line in lines if line.startswith('[计划修复] ')]
            launcher_hashes = {name: hashlib.sha256(setup.regular_bytes(root / name)).hexdigest()
                               if _exists(root / name) else None
                               for name in ('Antigravity-Proxy.cmd', 'Antigravity-Proxy.ps1')}
            signature = json.dumps({'lines': lines, 'links': snapshots, 'launchers': launcher_hashes},
                                   sort_keys=True, ensure_ascii=False)
            return code, lines, items, (signature, None)
        cleanup = _module('Cleanup-Proxy-Shortcuts')
        plan = cleanup.plan_cleanup(root, roots, setup)
        lines = ['[扫描结果] {} 个快捷方式；将改回 EXE {} 个，快捷方式不会删除。'.format(
            plan['scanned'], sum(item['kind'] == 'shortcut' for item in plan['entries']))]
        items = []
        for item in plan['entries']:
            label = '改回 EXE' if item['kind'] == 'shortcut' else '删除代理启动文件'
            lines.append('[计划' + label + '] ' + item['path'])
            items.append({'path': item['path'], 'action': label, 'status': '待执行'})
        # This signature includes file hashes and all scanned roots, not just
        # the displayed plan labels. apply_cleanup rechecks it before mutation.
        signature = json.dumps(plan, sort_keys=True, ensure_ascii=False, default=str)
        return 0, lines, items, (signature, plan)

    @staticmethod
    def _preview_key(action, root, roots):
        return action, os.path.normcase(str(root)), tuple(os.path.normcase(str(item)) for item in roots)

    def execute(self, action, path, overlays=None, scan_roots=(), progress=None):
        actions = {'patch', 'restore', 'proxy_preview', 'proxy_setup',
                   'proxy_remove_preview', 'proxy_remove', 'launch'}
        if action not in actions:
            return TaskResult('failed', 'unknown', '不支持的操作。')
        if not _TASK_LOCK.acquire(False):
            return TaskResult('failed', action, '已有操作正在执行，请稍后重试。')
        result = TaskResult('failed', action, '操作未完成。')
        stream = _ProgressStream(progress)
        try:
            snapshot = copy.deepcopy(overlays)
            root = common.discover_install(path)
            roots = tuple(Path(item).expanduser().resolve() for item in scan_roots)
            with _installation_lock(root), contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                print('[检查] 正在核对所选安装与操作条件...')
                if action in ('patch', 'restore', 'launch'):
                    current = self.inspect(root)
                    if action == 'patch' and not current.can_patch:
                        raise ValueError(current.message + '\n' + '\n'.join(current.warnings))
                    if action == 'restore' and not current.can_restore:
                        raise ValueError(current.message + '\n' + '\n'.join(current.warnings))
                    if action == 'launch' and current.state not in ('original', 'localized'):
                        raise ValueError('安装入口尚未通过校验，请先重新检测或恢复英文。')
                code = 0
                if action == 'patch':
                    if not _module('Antigravity-Patcher').apply_patch(root, dictionary_snapshot=snapshot):
                        raise RuntimeError('汉化未返回完成状态，请重新检测。')
                    result.message = '汉化已应用，原版归档已保留。'
                    result.next_step = '需要使用时，请点击“启动 Antigravity”。'
                elif action == 'restore':
                    code = _module('Restore').restore(root)
                    result.message = '已恢复英文界面。' if not code else '原版入口已恢复，但临时目录清理未完成。'
                    result.next_step = '请核对详情；需要使用时手动启动 Antigravity。'
                elif action == 'launch':
                    if current.proxy == 'incomplete':
                        raise ValueError('代理启动文件不完整，请先配置或移除代理启动。')
                    common.launch_application(root)
                    result.message = '已发出启动请求。'
                    result.next_step = '请检查 Antigravity 窗口；启动请求不代表网络连接通过。'
                else:
                    preview_action = 'proxy_remove_preview' if action.startswith('proxy_remove') else 'proxy_preview'
                    key = self._preview_key(preview_action, root, roots)
                    code, lines, items, plan_info = self._proxy_plan(preview_action, root, roots)
                    signature = plan_info[0] if plan_info else '\n'.join(lines)
                    for line in lines:
                        print(line)
                    result.items = items
                    if action.endswith('preview'):
                        self._previews[key] = signature
                        result.message = '预览完成，尚未修改文件或快捷方式。'
                        result.next_step = '核对上述修改范围后，再执行相应操作。'
                    else:
                        previous = self._previews.pop(key, None)
                        if previous is None:
                            raise ValueError('请先预览本次代理操作，核对快捷方式范围后再执行。')
                        if previous != signature:
                            raise ValueError('代理配置或快捷方式在预览后发生变化；未开始修改，请重新预览。')
                        if action == 'proxy_setup':
                            code = _module('Setup-Proxy-Shortcuts').install(
                                SimpleNamespace(app_dir=str(root), scan_root=list(roots), dry_run=False))
                            result.message = '代理启动已配置。' if code == 0 else '代理启动部分完成，部分入口仍需处理。'
                        else:
                            code = _module('Cleanup-Proxy-Shortcuts').apply_cleanup(
                                plan_info[1], _module('Setup-Proxy-Shortcuts'))
                            result.message = '已移除代理启动。' if code == 0 else '代理移除部分完成，启动文件可能仍保留。'
                        result.next_step = '请查看逐项结果；完全退出 Antigravity 后从所选入口手动启动。'
                result.status = 'success' if code == 0 else 'partial' if code == 2 else 'failed'
        except Exception as error:
            result.status = 'partial' if action == 'patch' and '汉化已生效' in str(error) else 'failed'
            result.message = str(error)
            result.next_step = '请保留原版归档和恢复目录，查看详情，处理权限、文件占用或安装冲突后重新检测。'
            stream.write('[未完成] ' + str(error) + '\n')
        finally:
            try:
                result.details = stream.getvalue().splitlines()
                result.steps = [line for line in result.details if line.startswith(('[检查]', '[执行]', '[完成]', '[未完成]'))]
                if path:
                    result.installation = self.inspect(path)
                self._events.append({'time': dt.datetime.now(dt.timezone.utc).isoformat(),
                                     'action': action, 'status': result.status,
                                     'state': result.installation.state if result.installation else 'unknown',
                                     'stepCount': len(result.steps), 'itemCount': len(result.items)})
                self._events = self._events[-200:]
            finally:
                _TASK_LOCK.release()
        return result

    def diagnostics(self):
        """Only fixed metadata is exported, never raw logs or input strings."""
        return {'schemaVersion': 1, 'application': 'Antigravity 中文助手',
                'platform': sys.platform, 'python': '.'.join(map(str, sys.version_info[:3])),
                'connection': '未测试连接', 'events': copy.deepcopy(self._events)}
