# coding: utf-8
"""将代理快捷方式改回原 EXE，仅清除代理 CMD/PS1；保留快捷方式及旧备份。"""
import argparse
import base64
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace


LAUNCHERS = ('Antigravity-Proxy.cmd', 'Antigravity-Proxy.ps1')
SETUP_BACKUPS = 'antigravity-proxy-backups'


def load_setup():
    source = Path(__file__).with_name('Setup-Proxy-Shortcuts.py')
    if not source.is_file():
        raise ValueError('请将此脚本与 Setup-Proxy-Shortcuts.py 放在同一个文件夹中。')
    # run_path does not run the sibling script's __main__ entry point.
    return SimpleNamespace(**runpy.run_path(str(source)))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def regular_bytes(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
        raise ValueError('拒绝处理符号链接、重解析点或非普通文件：' + str(path))
    return path.read_bytes()


def checked_directory(path, parent):
    path, parent = Path(path), Path(parent).resolve()
    resolved = path.resolve()
    if resolved == parent or os.path.commonpath([str(resolved), str(parent)]) != str(parent):
        raise ValueError('目录超出预期范围：' + str(path))
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
        raise ValueError('拒绝遍历目录链接：' + str(path))
    return resolved


def backup_inventory(app_dir, setup):
    """Read recorded custom shortcuts without modifying or collecting old backups."""
    root = app_dir / SETUP_BACKUPS
    recorded_links = []
    if not root.exists():
        return [], [], recorded_links
    checked_directory(root, app_dir)
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        checked_directory(folder, root)
        manifest_path = folder / 'manifest.json'
        if not manifest_path.is_file():
            continue
        manifest = json.loads(regular_bytes(manifest_path).decode('utf-8'))
        if manifest.get('format') != 1 or setup.path_key(manifest.get('app_dir', '')) != setup.path_key(app_dir):
            continue
        for entry in manifest['entries']:
            path = Path(entry['path'])
            if path.is_absolute() and path.suffix.lower() == '.lnk' and path.exists():
                recorded_links.append(str(path))
    return [], [], recorded_links


def decode_shortcut_arguments(value):
    if not value.strip():
        return ''
    match = re.fullmatch(r'\s*-ShortcutArgsBase64\s+(?:"([A-Za-z0-9+/=]+)"|([A-Za-z0-9+/=]+))\s*', value, re.IGNORECASE)
    if not match:
        raise ValueError('代理快捷方式包含未知启动参数，保留原状，请先人工核对。')
    try:
        decoded = base64.b64decode(match.group(1) or match.group(2), validate=True).decode('utf-8')
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError('快捷方式的原始参数编码无效，保留原状。') from error
    if '\x00' in decoded:
        raise ValueError('快捷方式的原始参数包含空字符，保留原状。')
    return decoded


def scan_proxy_links(roots, recorded_links, app_dir, setup):
    paths, errors = setup.find_shortcuts(roots)
    paths = list({setup.path_key(p): p for p in paths + recorded_links if Path(p).exists()}.values())
    response = setup.run_powershell({'action': 'read', 'paths': paths})
    errors.extend(response['errors'])
    targets = {setup.path_key(app_dir / name) for name in LAUNCHERS}
    links = [link for link in response['links'] if setup.path_key(link['target']) in targets]
    return links, errors, len(paths)


def plan_cleanup(app_dir, extra_roots, setup):
    app_dir = Path(app_dir).resolve()
    _, _, recorded = backup_inventory(app_dir, setup)
    executable = app_dir / 'Antigravity.exe'
    if not executable.is_file():
        raise ValueError('未找到 Antigravity.exe，不能将快捷方式改回源程序。')
    folders = setup.run_powershell({'action': 'folders'})
    roots = setup.scan_roots(folders, extra_roots)
    links, errors, scanned = scan_proxy_links(roots, recorded, app_dir, setup)
    if errors:
        raise ValueError('快捷方式扫描不完整，未执行清理：\n' + '\n'.join(errors))
    entries = []
    seen = set()

    def add(path, kind, expected=None, replacement=None):
        path = Path(path)
        key = setup.path_key(path)
        if key in seen:
            return
        current_hash = digest(regular_bytes(path))
        if expected is not None and current_hash != expected:
            raise ValueError('快捷方式在扫描后被修改，请重新预览：' + str(path))
        entry = {'path': str(path), 'kind': kind, 'sha256': current_hash}
        if replacement is not None:
            entry['replacement'] = replacement
        entries.append(entry)
        seen.add(key)

    for link in links:
        if not link.get('snapshot_hash'):
            raise ValueError('缺少快捷方式校验值，请使用当前版本的 Setup-Proxy-Shortcuts.py。')
        icon = link.get('icon', '')
        if not icon.split(',', 1)[0].strip():
            icon = str(executable) + ',0'
        add(link['path'], 'shortcut', link['snapshot_hash'], {
            'target': str(executable),
            'arguments': decode_shortcut_arguments(link.get('arguments', '')),
            'icon': icon,
            'working_directory': link.get('working_directory') or str(app_dir),
            'window_style': 1,  # The proxy launcher used minimized; launch the app normally.
        })
    for name in LAUNCHERS:
        path = app_dir / name
        if path.exists():
            if path.resolve().parent != app_dir:
                raise ValueError('代理启动文件不在预期安装目录内。')
            add(path, 'launcher')
    return {'app_dir': app_dir, 'entries': entries, 'directories': [],
            'roots': roots, 'recorded': recorded, 'scanned': scanned}


def save_manifest(folder, manifest, setup):
    setup.atomic_write(folder / 'manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'))


def archive_plan(plan, backup_root, setup):
    backup_root = Path(backup_root).expanduser().resolve()
    app_dir = plan['app_dir']
    try:
        inside_install = os.path.commonpath([str(backup_root), str(app_dir)]) == str(app_dir)
    except ValueError:  # Different drives are outside the install directory.
        inside_install = False
    if inside_install:
        raise ValueError('清理备份目录必须放在 Antigravity 安装目录之外。')
    backup_root.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix=datetime.now().strftime('%Y%m%d-%H%M%S-'), dir=str(backup_root)))
    manifest = {'format': 'antigravity-proxy-cleanup-v2', 'app_dir': str(app_dir), 'entries': []}
    for number, item in enumerate(plan['entries']):
        source = Path(item['path'])
        if digest(regular_bytes(source)) != item['sha256']:
            raise ValueError('文件在预览后已变化，未开始删除：' + str(source))
        name = '{:04d}.bin'.format(number)
        shutil.copy2(str(source), str(folder / name))
        if digest(regular_bytes(folder / name)) != item['sha256']:
            raise ValueError('备份校验失败，未开始删除：' + str(source))
        manifest['entries'].append(dict(item, blob=name, removed=False, after_hash=None))
    save_manifest(folder, manifest, setup)
    return folder, manifest


def apply_cleanup(plan, backup_root, setup):
    if not plan['entries']:
        print('[完成] 没有找到代理启动文件或相关快捷方式，无需清理。')
        return 0
    folder, manifest = archive_plan(plan, backup_root, setup)
    print('[清理备份] ' + str(folder))
    print('[还原命令] python "{}" --restore "{}"'.format(Path(__file__).name, folder))
    # Check the whole snapshot before changing shortcuts or removing launchers.
    for entry in manifest['entries']:
        if digest(regular_bytes(entry['path'])) != entry['sha256']:
            raise ValueError('文件在备份后已变化，未开始删除：' + entry['path'])
    for kind in ('shortcut', 'launcher'):
        if kind == 'launcher':
            remaining, errors, _ = scan_proxy_links(plan['roots'], plan['recorded'], plan['app_dir'], setup)
            if remaining or errors:
                print('[停止] 仍有代理快捷方式或扫描错误；启动文件已保留，请重新预览。')
                return 2
        for entry in manifest['entries']:
            if entry['kind'] != kind:
                continue
            path = Path(entry['path'])
            try:
                if digest(regular_bytes(path)) != entry['sha256']:
                    raise ValueError('文件已被修改，保留当前内容。')
                if kind == 'shortcut':
                    setup.run_powershell(dict(entry['replacement'], action='write', path=str(path), before_hash=entry['sha256']))
                    entry['after_hash'] = digest(regular_bytes(path))
                    print('[已改回 EXE] ' + str(path))
                else:
                    # Only the two exact launcher files can enter this branch.
                    if path.name not in LAUNCHERS or path.resolve().parent != plan['app_dir']:
                        raise ValueError('待删除文件不属于本次安装的代理启动文件。')
                    path.unlink()
                    entry['removed'] = True
                    print('[已删除] ' + str(path))
                save_manifest(folder, manifest, setup)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                print('[停止] {}：{}；后续文件已保留，可用上方备份恢复。'.format(path, error))
                return 2
    setup.run_powershell({'action': 'notify'})
    print('[完成] 快捷方式已保留并改回 Antigravity.exe，两个代理启动文件已清理。')
    print('[说明] 软件、汉化文件和旧修复备份均保留；后续启动不再自动注入代理。')
    return 0


def restore_cleanup(folder, preview, setup):
    folder = Path(folder).resolve()
    manifest = json.loads(regular_bytes(folder / 'manifest.json').decode('utf-8'))
    version = manifest.get('format')
    if version not in ('antigravity-proxy-cleanup-v1', 'antigravity-proxy-cleanup-v2'):
        raise ValueError('这不是本清理脚本生成的备份。')
    operations = []
    for entry in manifest['entries']:
        if not re.fullmatch(r'[0-9]+\.bin', entry['blob']):
            raise ValueError('备份文件名不合法。')
        saved = regular_bytes(folder / entry['blob'])
        if digest(saved) != entry['sha256']:
            raise ValueError('备份校验失败。')
        target = Path(entry['path'])
        if not target.is_absolute():
            raise ValueError('还原路径必须是绝对路径。')
        current_hash = digest(regular_bytes(target)) if target.exists() else None
        if current_hash == entry['sha256']:
            continue
        if current_hash is not None and not (
            version == 'antigravity-proxy-cleanup-v2' and entry['kind'] == 'shortcut'
            and current_hash == entry.get('after_hash')
        ):
            raise ValueError('目标已存在且内容不同，未执行还原：' + str(target))
        operations.append((target, saved, entry['kind'], current_hash))
    # Restore launchers before shortcuts, so a partial restore leaves no dangling link.
    operations.sort(key=lambda item: {'launcher': 0, 'setup_backup': 1, 'shortcut': 2}[item[2]])
    for target, saved, _, expected_hash in operations:
        print(('[预览还原] ' if preview else '[还原] ') + str(target))
        if not preview:
            target.parent.mkdir(parents=True, exist_ok=True)
            current_hash = digest(regular_bytes(target)) if target.exists() else None
            if current_hash != expected_hash:
                raise ValueError('还原期间目标被其他程序修改，停止：' + str(target))
            setup.atomic_write(target, saved)
    if not preview:
        setup.run_powershell({'action': 'notify'})
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='保留快捷方式并改回 Antigravity.exe，仅删除代理 CMD/PS1；旧备份保留，改动可还原。')
    parser.add_argument('--app-dir', help='包含 Antigravity.exe 的安装目录')
    parser.add_argument('--scan-root', action='append', default=[], help='额外递归扫描目录，可重复指定')
    parser.add_argument('--dry-run', action='store_true', help='仅预览，不写入或删除文件')
    parser.add_argument('--backup-dir', help='清理归档的存放根目录，必须在软件安装目录之外')
    parser.add_argument('--restore', help='还原本清理脚本输出的备份目录')
    args = parser.parse_args(argv)
    if sys.platform != 'win32':
        parser.error('此脚本仅支持 Windows。')
    try:
        setup = load_setup()
        if args.restore:
            return restore_cleanup(args.restore, args.dry_run, setup)
        app_dir = setup.discover_install(args.app_dir)
        plan = plan_cleanup(app_dir, args.scan_root, setup)
        print('[安装目录] ' + str(app_dir))
        print('[扫描结果] {} 个快捷方式；将改回 EXE {} 个，快捷方式不会删除。'.format(plan['scanned'], sum(e['kind'] == 'shortcut' for e in plan['entries'])))
        for entry in plan['entries']:
            print(('[计划改回 EXE] ' if entry['kind'] == 'shortcut' else '[计划删除] ') + entry['path'])
        if args.dry_run:
            print('[预览结束] 未写入或删除文件。')
            return 0
        if not args.backup_dir and not os.environ.get('LOCALAPPDATA'):
            raise ValueError('无法确定备份位置，请用 --backup-dir 指定。')
        backup_root = args.backup_dir or str(Path(os.environ['LOCALAPPDATA']) / 'AntigravityProxyCleanupBackups')
        return apply_cleanup(plan, backup_root, setup)
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as error:
        print('[错误] ' + str(error))
        return 1


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    result = main()
    if len(sys.argv) == 1 and sys.stdin.isatty():
        try:
            input('\n执行完毕，按 Enter 键退出...')
        except (EOFError, KeyboardInterrupt):
            pass
    sys.exit(result)
