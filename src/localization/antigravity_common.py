"""Shared, dependency-free installation and archive checks for localization tools."""
import base64
import hashlib
import json
import ntpath
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import stat
import struct
import subprocess
import sys
import time


def resources_dir(app_dir):
    root = Path(app_dir)
    return root / 'Contents' / 'Resources' if sys.platform == 'darwin' else root / 'resources'


def discover_install(explicit=None):
    if sys.platform not in ('win32', 'darwin'):
        raise ValueError('当前仅支持 Windows 和 macOS。')
    def valid(root):
        executable = root / ('Contents/MacOS/Antigravity' if sys.platform == 'darwin' else 'Antigravity.exe')
        return executable.is_file() and resources_dir(root).is_dir()
    if explicit:
        root = Path(os.path.expandvars(str(explicit))).expanduser().resolve()
        if not valid(root):
            raise ValueError('--app-dir 中未找到 Antigravity 程序及 resources 目录。macOS 请指定 .app。')
        return root
    candidates = []
    if sys.platform == 'darwin':
        candidates = [Path('/Applications/Antigravity.app'), Path.home() / 'Applications/Antigravity.app']
    else:
        for variable, suffix in [('LOCALAPPDATA', 'Programs/antigravity'), ('ProgramFiles', 'Antigravity'), ('ProgramFiles(x86)', 'Antigravity')]:
            if os.environ.get(variable):
                candidates.append(Path(os.environ[variable]) / suffix)
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, r'Software\Microsoft\Windows\CurrentVersion\App Paths\Antigravity.exe', 0, winreg.KEY_READ | view) as key:
                        candidates.append(Path(os.path.expandvars(winreg.QueryValue(key, None).strip('"'))).parent)
                except OSError:
                    pass
                try:
                    with winreg.OpenKey(hive, r'Software\Microsoft\Windows\CurrentVersion\Uninstall', 0, winreg.KEY_READ | view) as key:
                        for index in range(winreg.QueryInfoKey(key)[0]):
                            try:
                                with winreg.OpenKey(key, winreg.EnumKey(key, index)) as entry:
                                    if str(winreg.QueryValueEx(entry, 'DisplayName')[0]).casefold() == 'antigravity':
                                        candidates.append(Path(os.path.expandvars(winreg.QueryValueEx(entry, 'InstallLocation')[0].strip('"'))))
                            except OSError:
                                continue
                except OSError:
                    pass
    found = {os.path.normcase(str(root.resolve())): root.resolve() for root in candidates if valid(root)}
    if not found:
        raise ValueError('未找到 Antigravity，请使用 --app-dir "软件安装目录" 指定位置。')
    if len(found) != 1:
        raise ValueError('发现多个安装目录，请用 --app-dir 选择一个：\n' + '\n'.join(map(str, found.values())))
    return next(iter(found.values()))


def _no_link(path):
    info = Path(path).lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
        raise ValueError('拒绝处理符号链接或重解析点：' + str(path))
    return info


def _contained(root, relative):
    path = Path(root).joinpath(*PurePosixPath(relative).parts)
    root = Path(root).resolve()
    if root not in path.resolve().parents:
        raise ValueError('文件路径超出预期目录：' + str(path))
    current = root
    for name in PurePosixPath(relative).parts:
        current /= name
        if current.exists() or current.is_symlink():
            _no_link(current)
    return path


def remove_tree(path, parent):
    """Remove one immediate child directory; errors must reach the caller."""
    path, parent = Path(path), Path(parent).resolve()
    if path.resolve().parent != parent or path.resolve() == parent:
        raise ValueError('拒绝删除预期目录之外的路径：' + str(path))
    if not stat.S_ISDIR(_no_link(path).st_mode):
        raise ValueError('待删除路径不是普通目录：' + str(path))
    for current, directories, files in os.walk(str(path), followlinks=False):
        for name in directories + files:
            _no_link(Path(current) / name)
    shutil.rmtree(str(path))
    if path.exists():
        raise OSError('目录未完全删除：' + str(path))


def _relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or '\x00' in value:
        raise ValueError('归档包含无效路径。')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('归档包含越界路径：' + value)
    return path.as_posix()


def _main_path(package_bytes, exists):
    try:
        package = json.loads(package_bytes.decode('utf-8-sig'))
    except (UnicodeError, ValueError) as error:
        raise ValueError('package.json 无效。') from error
    if not isinstance(package, dict):
        raise ValueError('package.json 必须为对象。')
    main = _relative(package.get('main') or 'index.js')
    candidates = [main, main + '.js', main + '.json', main + '.node', main.rstrip('/') + '/index.js']
    for candidate in candidates:
        if exists(candidate):
            return candidate
    raise ValueError('缺少 package.json 指定的主入口：' + main)


def _archive_index(asar_path, unpacked_dir=None):
    archive = Path(asar_path)
    if not stat.S_ISREG(_no_link(archive).st_mode):
        raise ValueError('ASAR 不是普通文件。')
    size = archive.stat().st_size
    with archive.open('rb') as stream:
        first = stream.read(16)
        if len(first) != 16:
            raise ValueError('ASAR 文件头不完整。')
        magic, header_total, payload_size, json_size = struct.unpack('<4I', first)
        if (magic != 4 or header_total < 8 or payload_size + 4 != header_total or
                json_size > payload_size - 4 or json_size > 128 * 1024 * 1024 or
                8 + header_total > size):
            raise ValueError('ASAR 文件头长度无效。')
        try:
            header = json.loads(stream.read(json_size).decode('utf-8'))
        except (UnicodeError, ValueError) as error:
            raise ValueError('ASAR 索引无效。') from error
    if not isinstance(header, dict) or not isinstance(header.get('files'), dict):
        raise ValueError('ASAR 缺少文件索引。')
    original_name = archive.name[:-9] if archive.name.endswith('.disabled') else archive.name
    sidecar = Path(unpacked_dir) if unpacked_dir is not None else archive.with_name(original_name + '.unpacked')
    records, names = {}, set()
    def walk(node, prefix=''):
        for name, info in node.items():
            if (not isinstance(name, str) or name in ('', '.', '..') or '/' in name or '\\' in name or ':' in name or '\x00' in name or
                    (sys.platform == 'win32' and (name.endswith((' ', '.')) or ntpath.isabs(name)))):
                raise ValueError('ASAR 包含无效文件名。')
            relative = _relative(prefix + name)
            key = os.path.normcase(relative)
            if key in names or not isinstance(info, dict):
                raise ValueError('ASAR 存在重复或无效条目：' + relative)
            names.add(key)
            if 'files' in info:
                if not isinstance(info['files'], dict):
                    raise ValueError('ASAR 目录索引无效。')
                walk(info['files'], relative + '/')
            elif 'link' in info:
                raise ValueError('当前不支持包含链接条目的 ASAR，未修改安装：' + relative)
            else:
                length = info.get('size')
                if not isinstance(length, int) or isinstance(length, bool) or length < 0:
                    raise ValueError('ASAR 文件长度无效：' + relative)
                entry = {'size': length, 'integrity': info.get('integrity'), 'executable': bool(info.get('executable'))}
                if info.get('unpacked'):
                    _no_link(sidecar)
                    external = _contained(sidecar, relative)
                    if not stat.S_ISREG(_no_link(external).st_mode) or external.stat().st_size != length:
                        raise ValueError('ASAR 外置依赖缺失或长度不符：' + str(external))
                    entry['external'] = external
                else:
                    offset = info.get('offset')
                    if not isinstance(offset, (str, int)) or isinstance(offset, bool) or not str(offset).isdigit():
                        raise ValueError('ASAR 文件偏移无效：' + relative)
                    offset = 8 + header_total + int(offset)
                    if offset + length > size:
                        raise ValueError('ASAR 文件被截断：' + relative)
                    entry['offset'] = offset
                records[relative] = entry
    walk(header['files'])
    if 'package.json' not in records:
        raise ValueError('ASAR 缺少 package.json。')
    return archive, records


def _read_entry(archive_stream, entry, output=None):
    external = entry.get('external')
    stream = Path(external).open('rb') if external else archive_stream
    try:
        if external is None:
            stream.seek(entry['offset'])
        remaining = entry['size']
        hasher = hashlib.sha256()
        data = bytearray() if output == 'bytes' else None
        while remaining:
            block = stream.read(min(remaining, 1024 * 1024))
            if not block:
                raise ValueError('读取 ASAR 文件或外置依赖时遇到不完整数据。')
            hasher.update(block)
            if data is not None:
                data.extend(block)
            elif output is not None:
                output.write(block)
            remaining -= len(block)
        integrity = entry.get('integrity')
        if integrity and (not isinstance(integrity, dict) or integrity.get('algorithm') != 'SHA256' or integrity.get('hash') != hasher.hexdigest()):
            raise ValueError('ASAR 文件完整性校验失败。')
        return bytes(data) if data is not None else None
    finally:
        if external:
            stream.close()


def validate_asar(asar_path, unpacked_dir=None):
    """Validate complete contents and launch entry without mutating the installation."""
    archive, records = _archive_index(asar_path, unpacked_dir)
    with archive.open('rb') as stream:
        for entry in records.values():
            _read_entry(stream, entry)
        if records['package.json']['size'] > 1024 * 1024:
            raise ValueError('package.json 超过支持的大小。')
        main = _main_path(_read_entry(stream, records['package.json'], 'bytes'), lambda name: name in records)
    return {'archive': archive, 'records': records, 'main': main}


def extract_asar(asar_path, dest_dir, unpacked_dir=None):
    validated = validate_asar(asar_path, unpacked_dir)
    destination = Path(dest_dir)
    if destination.exists():
        _no_link(destination)
        if any(destination.iterdir()):
            raise ValueError('解包目标必须为空目录。')
    else:
        destination.mkdir(parents=True)
    with validated['archive'].open('rb') as stream:
        for relative, entry in validated['records'].items():
            target = _contained(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as output:
                _read_entry(stream, entry, output)
            if sys.platform != 'win32' and entry['executable']:
                target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    validate_extracted_app(destination)


def validate_extracted_app(path, required_files=()):
    root = Path(path)
    _no_link(root)
    def exists(name):
        file = _contained(root, _relative(name))
        return file.is_file()
    package_path = _contained(root, 'package.json')
    if not package_path.is_file():
        raise ValueError('解包目录缺少 package.json。')
    main = _main_path(package_path.read_bytes(), exists)
    for required in required_files:
        if not exists(required):
            raise ValueError('软件版本不兼容或解包不完整，缺少汉化目标：' + required)
    return main


def _powershell():
    root = Path(os.environ.get('SystemRoot', r'C:\Windows'))
    native = root / 'Sysnative/WindowsPowerShell/v1.0/powershell.exe'
    return native if native.is_file() else root / 'System32/WindowsPowerShell/v1.0/powershell.exe'


def _environment():
    result = dict(os.environ)
    result.pop('PSModulePath', None)
    return result


def _error_text(result):
    raw = result.stderr or result.stdout or b''
    for encoding in ('utf-8-sig', 'mbcs' if sys.platform == 'win32' else 'utf-8'):
        try:
            return raw.decode(encoding).strip()
        except UnicodeError:
            pass
    return raw.decode('utf-8', errors='replace').strip()


def stop_application(app_dir):
    """Close only processes belonging to this installation, before committing files."""
    root = Path(app_dir).resolve()
    if sys.platform == 'win32':
        script = r'''$ErrorActionPreference='Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$target=[Console]::In.ReadToEnd().Trim()
foreach($process in @(Get-CimInstance Win32_Process -Filter "Name = 'Antigravity.exe'")) {
    if (-not $process.ExecutablePath) { throw '无法确认 Antigravity 进程所属目录，请手动完全退出软件后重试。' }
    if ($process.ExecutablePath -ieq $target) {
        $result=Invoke-CimMethod -InputObject $process -MethodName Terminate
        if($result.ReturnValue -ne 0) { throw '无法关闭 Antigravity，请手动退出后重试。' }
    }
}'''
        encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
        result = subprocess.run([str(_powershell()), '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded], input=str(root / 'Antigravity.exe').encode('utf-8'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_environment(), creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        if result.returncode:
            raise RuntimeError('无法安全关闭当前安装的进程：' + _error_text(result))
    elif sys.platform == 'darwin':
        result = subprocess.run(['ps', '-axo', 'pid=,command='], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        prefix = str(root / 'Contents') + '/'
        pids = []
        for line in result.stdout.decode('utf-8').splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and parts[1].startswith(prefix):
                pids.append(int(parts[0]))
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 5
        while pids and time.monotonic() < deadline:
            for pid in pids[:]:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    pids.remove(pid)
            if pids:
                time.sleep(0.1)
        if pids:
            raise RuntimeError('Antigravity 仍在运行，请手动完全退出后重试。')


def launch_application(app_dir):
    root = Path(app_dir).resolve()
    if sys.platform == 'darwin':
        subprocess.run(['open', str(root)], check=True)
        return
    executable = root / 'Antigravity.exe'
    if not executable.is_file():
        raise ValueError('未找到 Antigravity.exe。')
    launcher = root / 'Antigravity-Proxy.ps1'
    if launcher.is_file():
        arguments = [str(_powershell()), '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(launcher)]
        for command in (arguments + ['-Diagnose'], arguments):
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(root), env=_environment(), creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
            if result.returncode:
                raise RuntimeError('文件操作已完成，但代理启动器执行失败（请检查执行策略及代理配置）：' + _error_text(result))
    else:
        process = subprocess.Popen([str(executable)], cwd=str(root), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP, close_fds=True)
        try:
            code = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            return
        if code:
            raise RuntimeError('文件操作已完成，但 Antigravity 启动进程返回错误：' + str(code))
