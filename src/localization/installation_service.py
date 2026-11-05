"""Structured, headless installation operations used by manager and CLI.

Inspection never starts/stops the app or writes to its installation. Runtime
connectivity is deliberately unknown: a file or a process is not a handshake.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

from antigravity_common import (
    _contained, _no_link, _read_entry, discover_install, launch_application,
    resources_dir, validate_asar, validate_extracted_app,
)
from translation_integration import (
    REGISTRY, RUNTIME_FILES, _file_digest, _validate_profile, resource_root,
)


def _load_tool(filename):
    spec = importlib.util.spec_from_file_location(
        '_manager_' + filename.replace('-', '_'), Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_file(path):
    _no_link(path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('元数据文件超过大小限制。')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _registry():
    data = _json_file(resource_root() / REGISTRY)
    if not isinstance(data, dict) or data.get('schemaVersion') != 1 or not isinstance(data.get('profiles'), list):
        raise ValueError('兼容注册表无效。')
    for profile in data['profiles']:
        _validate_profile(profile)
    return data['profiles']


def _archive_profile(validated, resources, profiles):
    """Compare pristine archive bytes without extracting into the install tree."""
    records = validated['records']
    matches = []
    with validated['archive'].open('rb') as stream:
        package = json.loads(_read_entry(stream, records['package.json'], 'bytes').decode('utf-8-sig'))
        for profile in profiles:
            if (package.get('name'), package.get('version'), package.get('main', 'index.js'),
                    package.get('type', 'commonjs')) != (profile['name'], profile['version'],
                                                       profile['main'], 'commonjs'):
                continue
            class Digest:
                def __init__(self):
                    self.value = hashlib.sha256()

                def write(self, block):
                    self.value.update(block)

            matched = True
            for relative, expected in profile['files'].items():
                if relative not in records:
                    matched = False
                    break
                digest = Digest()
                _read_entry(stream, records[relative], digest)
                if digest.value.hexdigest() != expected:
                    matched = False
                    break
            if matched:
                try:
                    matched = all(_file_digest(resources, name) == digest
                                  for name, digest in profile.get('resourcesFiles', {}).items())
                except (OSError, ValueError):
                    matched = False
            if matched:
                matches.append(profile)
    if len(matches) > 1:
        raise ValueError('匹配多个兼容配置。')
    return package, matches[0] if matches else None


def _component(application, profile):
    if not application.exists():
        return 'not_installed'
    try:
        validate_extracted_app(application)
        bridge = _contained(application, '.dragongirl')
        if not bridge.exists():
            preload = _contained(application, 'dist/preload.js')
            if preload.is_file() and preload.stat().st_size <= 16 * 1024 * 1024:
                return ('static_only' if 'Antigravity Chinese Localization Engine' in
                        preload.read_text(encoding='utf-8') else 'not_installed')
            return 'not_installed'
        installed = _json_file(_contained(application, '.dragongirl/profile.json'))
        if not profile or any(installed.get(key) != value for key, value in profile.items()):
            return 'invalid'
        integrity = installed.get('runtimeIntegrity')
        required = set(profile['files']) | {'.dragongirl/' + name for name in RUNTIME_FILES}
        if not isinstance(integrity, dict) or not required.issubset(integrity):
            return 'invalid'
        if not all(_file_digest(application, name) == digest for name, digest in integrity.items()):
            return 'invalid'
        if _json_file(application / 'package.json').get('main') != '.dragongirl/bootstrap.cjs':
            return 'invalid'
        if any(_file_digest(application, '.dragongirl/' + name) !=
               _file_digest(resource_root(), name) for name in RUNTIME_FILES):
            return 'outdated'
        return 'installed'
    except (OSError, ValueError, TypeError, AttributeError):
        return 'invalid'


class InstallationService:
    def inspect(self, app_dir=None):
        root = discover_install(app_dir)
        resources = resources_dir(root)
        archive, disabled = resources / 'app.asar', resources / 'app.asar.disabled'
        present = [path for path in (archive, disabled) if path.exists() or path.is_symlink()]
        status = dict(path=str(root), version=None, compatibility='unavailable',
                      component='unknown', running='unknown', runtime='unknown',
                      archive='missing', recoveryAvailable=False)
        if len(present) > 1:
            status['archive'] = 'conflict'
            return status
        if not present:
            return status
        validated = validate_asar(present[0], unpacked_dir=resources / 'app.asar.unpacked')
        package, profile = _archive_profile(validated, resources, _registry())
        status.update(version=package.get('version'),
                      compatibility='matched' if profile else 'unsupported',
                      matchedProfile=profile['id'] if profile else None,
                      archive='original' if present[0] == archive else 'preserved',
                      recoveryAvailable=True,
                      component=_component(resources / 'app', profile))
        return status

    def execute(self, action, app_dir=None, confirmed=False):
        steps = []
        installation = None

        def event(step, status):
            steps.append(dict(step=step, status=status))

        try:
            if action not in ('status', 'apply', 'restore', 'launch'):
                return dict(ok=False, code='invalid_action', message='不支持的安装操作。', steps=steps)
            if (action != 'status' and not app_dir) or (action in ('apply', 'restore') and confirmed is not True):
                return dict(ok=False, code='confirmation_required',
                            message='请选择明确的安装目录，并确认已保存工作及操作内容。', steps=steps)
            installation = self.inspect(app_dir)
            if action == 'status':
                return dict(ok=True, installation=installation, steps=steps,
                            message='已检查安装文件；运行连接状态尚未验证。')
            root = Path(installation['path'])
            if action in ('apply', 'restore') and not installation['recoveryAvailable']:
                return dict(ok=False, code='invalid_installation', installation=installation,
                            message='原始归档缺失或存在冲突；请核对安装文件，已保留现有程序。', steps=steps)
            if action == 'apply':
                _load_tool('Antigravity-Patcher.py').apply_patch(
                    root, no_launch=True, log=lambda _message: None, event=event)
            elif action == 'restore':
                result = _load_tool('Restore.py').restore(
                    root, launch=False, log=lambda _message: None, event=event)
                if result == 2:
                    return dict(ok=False, code='cleanup_incomplete', steps=steps,
                                installation=self.inspect(root), filesChanged=True, restartRequired=True,
                                message='原版已恢复，但临时目录未清理；解除文件占用或权限问题后再处理。')
            else:
                launch_application(root)
                event('launch', 'requested')
                return dict(ok=True, installation=installation, steps=steps,
                            launchRequested=True, restartRequired=False,
                            message='启动命令已完成；请在应用中核对窗口与翻译连接。')
            return dict(ok=True, installation=self.inspect(root), steps=steps,
                        filesChanged=any(step['step'] == 'activate' for step in steps),
                        restartRequired=True, message='安装操作已完成；请手动启动应用核对结果。')
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            # Raw filesystem/process errors may contain arbitrary paths or output.
            # Keep them in the original interactive CLI, never in GUI diagnostics.
            changed = any(step['step'] == 'activate' or
                          (step['step'] == 'rollback' and step['status'] == 'incomplete')
                          for step in steps)
            if action != 'status' and installation:
                try:
                    installation = self.inspect(installation['path'])
                except (OSError, ValueError, RuntimeError):
                    # Avoid presenting the old snapshot as the post-failure state.
                    installation = dict(path=installation['path'], version=None,
                                        compatibility='unavailable', component='unknown',
                                        running='unknown', runtime='unknown', archive='unknown',
                                        recoveryAvailable=False)
            return dict(ok=False, code='inspection_failed' if action == 'status' else 'operation_failed',
                        installation=installation, steps=steps, filesChanged=changed,
                        restartRequired=changed,
                        message='操作未完成。请检查目录、原始归档、版本、权限及文件占用；保留归档和暂存目录后重新检查。')
