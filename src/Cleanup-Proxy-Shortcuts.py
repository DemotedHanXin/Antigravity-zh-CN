# coding: utf-8
"""将代理快捷方式改回原 EXE，直接删除代理 CMD/PS1，不创建备份。"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import stat
import subprocess
import sys
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


def recorded_shortcut_paths(app_dir, setup):
    """Read existing setup records to find custom shortcuts; never write backup data."""
    root = app_dir / SETUP_BACKUPS
    recorded_links = []
    if not root.exists():
        return recorded_links
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
    return recorded_links


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
    recorded = recorded_shortcut_paths(app_dir, setup)
    executable = app_dir / 'Antigravity.exe'
    if not executable.is_file():
        raise ValueError('未找到 Antigravity.exe，不能将快捷方式改回源程序。')
    folders = setup.run_powershell({'action': 'folders'})
    custom_roots = setup.validate_scan_roots(setup.read_launcher_scan_roots(app_dir) + list(extra_roots))
    roots = setup.scan_roots(folders, custom_roots)
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
    return {'app_dir': app_dir, 'entries': entries,
            'roots': roots, 'custom_roots': custom_roots, 'recorded': recorded, 'scanned': scanned}


def apply_cleanup(plan, setup):
    if not plan['entries']:
        print('[完成] 没有找到代理启动文件或相关快捷方式，无需清理。')
        return 0
    # Check the whole snapshot before changing shortcuts or removing launchers.
    setup.validate_scan_roots(plan['custom_roots'])
    for entry in plan['entries']:
        if digest(regular_bytes(entry['path'])) != entry['sha256']:
            raise ValueError('文件在预览后已变化，未开始修改或删除：' + entry['path'])
    for kind in ('shortcut', 'launcher'):
        if kind == 'launcher':
            setup.validate_scan_roots(plan['custom_roots'])
            remaining, errors, _ = scan_proxy_links(plan['roots'], plan['recorded'], plan['app_dir'], setup)
            if remaining or errors:
                print('[停止] 仍有代理快捷方式或扫描错误；启动文件已保留，请重新预览。')
                return 2
        for entry in plan['entries']:
            if entry['kind'] != kind:
                continue
            path = Path(entry['path'])
            try:
                if digest(regular_bytes(path)) != entry['sha256']:
                    raise ValueError('文件已被修改，保留当前内容。')
                if kind == 'shortcut':
                    setup.run_powershell(dict(entry['replacement'], action='write', path=str(path), before_hash=entry['sha256']))
                    print('[已改回 EXE] ' + str(path))
                else:
                    # Only the two exact launcher files can enter this branch.
                    if path.name not in LAUNCHERS or path.resolve().parent != plan['app_dir']:
                        raise ValueError('待删除文件不属于本次安装的代理启动文件。')
                    path.unlink()
                    print('[已删除] ' + str(path))
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                print('[停止] {}：{}；后续文件已保留，处理问题后可重新运行。'.format(path, error))
                return 2
    setup.run_powershell({'action': 'notify'})
    print('[完成] 快捷方式已保留并改回 Antigravity.exe，两个代理启动文件已清理。')
    print('[说明] 直接删除，不进入回收站，不创建备份；需要代理启动时请重新运行 Setup-Proxy-Shortcuts.py。')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='保留快捷方式并改回 Antigravity.exe，直接删除代理 CMD/PS1，不创建备份；需要时运行 Setup-Proxy-Shortcuts.py 重新创建。')
    parser.add_argument('--app-dir', help='包含 Antigravity.exe 的安装目录')
    parser.add_argument('--scan-root', action='append', default=[], help='额外递归扫描目录，可重复指定')
    parser.add_argument('--dry-run', action='store_true', help='仅预览，不写入或删除文件')
    args = parser.parse_args(argv)
    if sys.platform != 'win32':
        parser.error('此脚本仅支持 Windows。')
    try:
        setup = load_setup()
        app_dir = setup.discover_install(args.app_dir)
        plan = plan_cleanup(app_dir, args.scan_root, setup)
        print('[安装目录] ' + str(app_dir))
        print('[扫描结果] {} 个快捷方式；将改回 EXE {} 个，快捷方式不会删除。'.format(plan['scanned'], sum(e['kind'] == 'shortcut' for e in plan['entries'])))
        for entry in plan['entries']:
            print(('[计划改回 EXE] ' if entry['kind'] == 'shortcut' else '[计划删除] ') + entry['path'])
        if args.dry_run:
            print('[预览结束] 未写入或删除文件。')
            return 0
        return apply_cleanup(plan, setup)
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
