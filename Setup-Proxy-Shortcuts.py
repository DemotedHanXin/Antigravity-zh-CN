# coding: utf-8
"""Windows 一键部署 Antigravity 代理启动器并修复快捷方式（仅使用标准库）。"""
import argparse
import base64
import hashlib
import json
import ntpath
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


LAUNCHER_CMD = r'''@echo off
setlocal DisableDelayedExpansion
set "ANTIGRAVITY_PROXY_START_DIRECTORY=%CD%"
set "PSModulePath=%SystemRoot%\System32\WindowsPowerShell\v1.0\Modules"
rem Read the current Windows system proxy on every launch.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -File "%~dp0Antigravity-Proxy.ps1" %*
set "ANTIGRAVITY_PROXY_EXIT_CODE=%errorlevel%"
if "%ANTIGRAVITY_PROXY_EXIT_CODE%"=="0" exit /b 0
rem Exit 2 means the script already displayed its own error message.
if not "%ANTIGRAVITY_PROXY_EXIT_CODE%"=="2" "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -Command "Add-Type -AssemblyName System.Windows.Forms; [void][System.Windows.Forms.MessageBox]::Show('The proxy launcher could not run. Run Setup-Proxy-Shortcuts.py in a terminal to check the PowerShell execution policy. No system policy was changed.', 'Antigravity launch failed')"
exit /b %ANTIGRAVITY_PROXY_EXIT_CODE%
'''
LAUNCHER_PS1 = r'''param(
    [switch]$Diagnose,
    [string]$ShortcutArgsBase64 = ''
)

$ErrorActionPreference = 'Stop'
$env:PSModulePath = [IO.Path]::Combine($PSHOME, 'Modules')

function ConvertTo-AntigravityProxyUrl {
    param([string]$Value)
    $Value = $Value.Trim()
    if ($Value -notmatch '^[a-z][a-z0-9+.-]*://') { $Value = 'http://' + $Value }
    $parsed = $null
    if (-not [Uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$parsed) -or
        $parsed.Scheme -notin @('http', 'https', 'socks5', 'socks5h') -or
        -not $parsed.Host -or $parsed.Port -lt 1 -or $parsed.Port -gt 65535 -or
        $parsed.UserInfo -or $parsed.Query -or $parsed.Fragment -or
        $parsed.AbsolutePath -notin @('', '/')) {
        throw '系统代理地址格式不受支持。请在代理软件中开启 HTTP 或混合端口的系统代理。'
    }
    return $parsed.AbsoluteUri.TrimEnd('/')
}

function Resolve-AntigravitySystemProxy {
    param([bool]$Enabled, [string]$Server, [string]$PacUrl)
    $result = [ordered]@{
        Mode = 'DirectOrTun'
        HTTP_PROXY = ''
        HTTPS_PROXY = ''
        ALL_PROXY = ''
        NO_PROXY = 'localhost,127.0.0.1,::1'
    }
    if (-not [string]::IsNullOrWhiteSpace($PacUrl)) {
        throw '检测到 PAC 自动代理脚本，此启动器不解析 PAC。请在代理软件中切换到系统代理（HTTP/混合端口）模式；使用 TUN 模式时请关闭 Windows 的代理脚本设置。'
    }
    if (-not $Enabled) { return [pscustomobject]$result }
    if ([string]::IsNullOrWhiteSpace($Server)) {
        throw 'Windows 系统代理已开启，但代理地址为空。请重新开启代理软件的系统代理功能。'
    }
    if ($Server -match '=') {
        $entries = @{}
        foreach ($entry in ($Server.Trim() -split '[;\s]+')) {
            if (-not $entry) { continue }
            $parts = $entry -split '=', 2
            if ($parts.Count -ne 2) { throw 'Windows 分协议代理设置格式不正确。' }
            $entries[$parts[0].ToLowerInvariant()] = $parts[1]
        }
        if (-not $entries.ContainsKey('https')) {
            throw '系统代理没有配置 HTTPS 代理。请在代理软件中开启覆盖 HTTPS 的系统代理或混合端口。'
        }
        if ($entries.ContainsKey('http')) {
            $result.HTTP_PROXY = ConvertTo-AntigravityProxyUrl $entries['http']
        }
        $result.HTTPS_PROXY = ConvertTo-AntigravityProxyUrl $entries['https']
    } else {
        $result.HTTP_PROXY = ConvertTo-AntigravityProxyUrl $Server
        $result.HTTPS_PROXY = $result.HTTP_PROXY
    }
    $result.Mode = 'WindowsSystemProxy'
    return [pscustomobject]$result
}

function Set-AntigravityProcessProxy {
    param($Configuration)
    # Process scope only. Clear inherited values when system proxy is off.
    foreach ($name in @('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY')) {
        [Environment]::SetEnvironmentVariable($name, [string]$Configuration.$name, 'Process')
    }
}

function ConvertFrom-AntigravityShortcutArgs {
    param([string]$Base64)
    if ([string]::IsNullOrEmpty($Base64)) { return '' }
    try {
        $bytes = [Convert]::FromBase64String($Base64)
        $strictUtf8 = New-Object System.Text.UTF8Encoding($false, $true)
        $decoded = $strictUtf8.GetString($bytes)
    } catch {
        throw '快捷方式参数编码无效，请重新运行快捷方式修复脚本。'
    }
    if ($decoded.IndexOf([char]0) -ge 0) {
        throw '快捷方式参数包含无效的空字符，请重新运行快捷方式修复脚本。'
    }
    return $decoded
}

try {
    $shortcutArguments = ConvertFrom-AntigravityShortcutArgs $ShortcutArgsBase64
    $settings = Get-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
    $configuration = Resolve-AntigravitySystemProxy -Enabled ($settings.ProxyEnable -eq 1) -Server $settings.ProxyServer -PacUrl $settings.AutoConfigURL
    if ($Diagnose) {
        $configuration | ConvertTo-Json
        exit 0
    }
    $executable = Join-Path $PSScriptRoot 'Antigravity.exe'
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw '同目录下未找到 Antigravity.exe，请将两个代理启动文件放在软件安装目录中。'
    }
    Set-AntigravityProcessProxy $configuration
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $executable
    $startInfo.WorkingDirectory = $PSScriptRoot
    if ($env:ANTIGRAVITY_PROXY_START_DIRECTORY -and [IO.Directory]::Exists($env:ANTIGRAVITY_PROXY_START_DIRECTORY)) {
        $startInfo.WorkingDirectory = $env:ANTIGRAVITY_PROXY_START_DIRECTORY
    }
    $startInfo.UseShellExecute = $false
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Normal
    # Preserve the original Windows command line verbatim; do not split/requote it.
    $startInfo.Arguments = $shortcutArguments
    [void][System.Diagnostics.Process]::Start($startInfo)
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    if (-not $Diagnose) {
        Add-Type -AssemblyName System.Windows.Forms
        [void][System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Antigravity 启动提示')
    }
    exit 2
}
'''

POWERSHELL_BRIDGE = r'''
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
$shell = New-Object -ComObject WScript.Shell
function Get-AntigravityFileHash([string]$path) {
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($hasher.ComputeHash([IO.File]::ReadAllBytes($path))).Replace('-', '').ToLowerInvariant() }
    finally { $hasher.Dispose() }
}
switch ($request.action) {
    'policy' {
        # Import the Windows PowerShell binary directly. Some installations load
        # duplicate ObjectSecurity type data through the module manifest.
        $security = [Reflection.Assembly]::Load('Microsoft.PowerShell.Security, Version=3.0.0.0, Culture=neutral, PublicKeyToken=31bf3856ad364e35')
        Import-Module $security.Location -ErrorAction Stop
        @{ effective = [string](Get-ExecutionPolicy); machine = [string](Get-ExecutionPolicy -Scope MachinePolicy); user = [string](Get-ExecutionPolicy -Scope UserPolicy) } | ConvertTo-Json -Compress
    }
    'folders' {
        $folders = @{}
        foreach ($name in @('Desktop', 'AllUsersDesktop', 'StartMenu', 'AllUsersStartMenu', 'Startup', 'AllUsersStartup')) {
            $folders[$name] = [string]$shell.SpecialFolders.Item($name)
        }
        $folders | ConvertTo-Json -Compress
    }
    'read' {
        $links = @()
        $errors = @()
        foreach ($path in $request.paths) {
            try {
                $beforeHash = Get-AntigravityFileHash $path
                $link = $shell.CreateShortcut([string]$path)
                $item = [pscustomobject]@{
                    path = [string]$path; target = $link.TargetPath; arguments = $link.Arguments
                    icon = $link.IconLocation; working_directory = $link.WorkingDirectory
                    description = $link.Description; window_style = $link.WindowStyle
                    snapshot_hash = $beforeHash
                }
                if ((Get-AntigravityFileHash $path) -ne $beforeHash) { throw 'Shortcut changed while reading it.' }
                $links += $item
            } catch { $errors += "${path}: $($_.Exception.Message)" }
        }
        @{ links = @($links); errors = @($errors) } | ConvertTo-Json -Compress -Depth 5
    }
    'write' {
        $path = [string]$request.path
        if (Test-Path -LiteralPath $path) {
            $currentHash = Get-AntigravityFileHash $path
            if (-not $request.before_hash -or $currentHash -ne $request.before_hash) {
                throw 'Shortcut changed since inspection; refusing to overwrite it.'
            }
        } elseif ($request.before_hash) { throw 'Shortcut disappeared since inspection.' }
        $link = $shell.CreateShortcut($path)
        $link.TargetPath = [string]$request.target
        $link.Arguments = [string]$request.arguments
        $link.WorkingDirectory = [string]$request.working_directory
        $link.IconLocation = [string]$request.icon
        # Setup minimizes the console launcher; cleanup explicitly requests Normal.
        if ($request.PSObject.Properties.Name -contains 'window_style') {
            $link.WindowStyle = [int]$request.window_style
        } else { $link.WindowStyle = 7 }
        $link.Save()
        $check = $shell.CreateShortcut($path)
        if ($check.TargetPath -ne $request.target -or $check.Arguments -cne $request.arguments -or
            (($request.PSObject.Properties.Name -contains 'window_style') -and $check.WindowStyle -ne $request.window_style)) {
            throw 'Shortcut verification failed after saving.'
        }
        @{ saved = $path } | ConvertTo-Json -Compress
    }
    'notify' {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class AntigravityShellNotify {
    [DllImport("shell32.dll")] public static extern void SHChangeNotify(uint e, uint f, IntPtr a, IntPtr b);
}
'@
        [AntigravityShellNotify]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)
        @{ notified = $true } | ConvertTo-Json -Compress
    }
    default { throw 'Unknown action.' }
}
'''


def powershell_path():
    root = Path(os.environ.get('SystemRoot', r'C:\Windows'))
    # A 32-bit Python process can reach the native shell through Sysnative.
    native = root / 'Sysnative' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'
    return native if native.is_file() else root / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'


def run_powershell(request):
    encoded = base64.b64encode(POWERSHELL_BRIDGE.encode('utf-16-le')).decode('ascii')
    environment = dict(os.environ)
    # Only bundled 5.1 modules are needed. Inherited/user module paths may select
    # incompatible PowerShell 7 modules, even when the variable is simply unset.
    environment['PSModulePath'] = str(Path(os.environ.get('SystemRoot', r'C:\Windows')) /
                                       'System32/WindowsPowerShell/v1.0/Modules')
    if request.get('action') == 'policy':
        # A temporary terminal Process policy does not apply to Explorer shortcuts.
        environment.pop('PSExecutionPolicyPreference', None)
    result = subprocess.run(
        [str(powershell_path()), '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
        input=json.dumps(request, ensure_ascii=False).encode('utf-8'),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        env=environment,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8-sig', errors='replace').strip())
    return json.loads(result.stdout.decode('utf-8-sig'))


def path_key(value):
    return ntpath.normcase(ntpath.normpath(os.path.expandvars(str(value).strip('"'))))


def discover_install(explicit=None):
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not (root / 'Antigravity.exe').is_file():
            raise ValueError('--app-dir 指定的文件夹中没有 Antigravity.exe。')
        return root
    candidates = []
    for variable, suffix in [('LOCALAPPDATA', 'Programs/antigravity'), ('ProgramFiles', 'Antigravity'), ('ProgramFiles(x86)', 'Antigravity')]:
        if os.environ.get(variable):
            candidates.append(Path(os.environ[variable]) / suffix)
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, r'Software\Microsoft\Windows\CurrentVersion\App Paths\Antigravity.exe', 0, winreg.KEY_READ | view) as key:
                    candidates.append(Path(winreg.QueryValue(key, None).strip('"')).parent)
            except OSError:
                pass
            try:
                with winreg.OpenKey(hive, r'Software\Microsoft\Windows\CurrentVersion\Uninstall', 0, winreg.KEY_READ | view) as key:
                    for index in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            with winreg.OpenKey(key, winreg.EnumKey(key, index)) as entry:
                                name = winreg.QueryValueEx(entry, 'DisplayName')[0]
                                if str(name).casefold() == 'antigravity':
                                    candidates.append(Path(winreg.QueryValueEx(entry, 'InstallLocation')[0]))
                        except OSError:
                            continue
            except OSError:
                pass
    found = {}
    for root in candidates:
        if (root / 'Antigravity.exe').is_file():
            found[path_key(root.resolve())] = root.resolve()
    if not found:
        raise ValueError('未找到 Antigravity，请使用 --app-dir "软件安装目录" 指定位置。')
    if len(found) > 1:
        raise ValueError('发现多个安装目录，请用 --app-dir 选择一个：\n' + '\n'.join(map(str, found.values())))
    return next(iter(found.values()))


def scan_roots(folders, extra):
    roots = list(folders.values())
    if os.environ.get('APPDATA'):
        roots.append(str(Path(os.environ['APPDATA']) / 'Microsoft/Internet Explorer/Quick Launch'))
    roots.extend(validate_scan_roots(extra))
    return list({path_key(p): Path(p).expanduser().resolve() for p in roots if p}.values())


METADATA_PREFIX = '# Antigravity-Proxy-Metadata: '


def regular_bytes(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
        raise ValueError('拒绝修改符号链接、重解析点或非普通文件：' + str(path))
    return path.read_bytes()


def validate_scan_roots(roots):
    result = {}
    for value in roots:
        path = Path(os.path.expandvars(str(value))).expanduser().resolve()
        if not path.is_dir():
            raise ValueError('自定义快捷方式目录不存在或不可访问，未开始修改：' + str(path))
        result[path_key(path)] = str(path)
    return list(result.values())


def read_launcher_scan_roots(app_dir):
    """Read data from a comment, never execute an installed launcher."""
    path = Path(app_dir) / 'Antigravity-Proxy.ps1'
    if not path.exists():
        return []
    lines = regular_bytes(path).decode('utf-8-sig').splitlines()
    matches = [line[len(METADATA_PREFIX):] for line in lines if line.startswith(METADATA_PREFIX)]
    if not matches:
        return []  # Legacy launchers require --scan-root for custom locations.
    if len(matches) != 1:
        raise ValueError('代理启动器包含重复的目录记录，未开始修改。')
    try:
        data = json.loads(matches[0])
        roots = data['scan_roots']
        if data.get('format') != 1 or not isinstance(roots, list) or any(
                not isinstance(item, str) or not Path(item).is_absolute() for item in roots):
            raise ValueError('Invalid metadata')
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('代理启动器中的快捷方式目录记录无效，未开始修改。') from error
    return validate_scan_roots(roots)


def launcher_ps1_bytes(scan_directories):
    metadata = {'format': 1, 'scan_roots': validate_scan_roots(scan_directories)}
    source = METADATA_PREFIX + json.dumps(metadata, ensure_ascii=True, separators=(',', ':')) + '\n' + LAUNCHER_PS1
    return source.replace('\n', '\r\n').encode('utf-8-sig')


def check_execution_policy():
    policy = run_powershell({'action': 'policy'})
    effective = policy.get('effective', '')
    if effective not in ('RemoteSigned', 'Unrestricted', 'Bypass'):
        raise ValueError('PowerShell 执行策略为 {}，无法运行此未签名的本地代理启动器；未写入文件或修改快捷方式。'
                         '请先按你或组织的安全要求配置允许的脚本执行方式，再重试。脚本不会修改或绕过执行策略。'.format(effective or '未知'))
    return effective


def find_shortcuts(roots):
    found, errors = {}, []
    for root in roots:
        if not root.is_dir():
            continue
        for current, directories, files in os.walk(str(root), followlinks=False, onerror=lambda e: errors.append(str(e))):
            kept = []
            for name in directories:
                lower = name.lower()
                if lower in {'.git', '.venv', 'node_modules', '$recycle.bin', 'system volume information', 'antigravity-proxy-backups'} or lower.startswith('antigravity-proxy-backup-'):
                    continue
                try:
                    attributes = getattr((Path(current) / name).lstat(), 'st_file_attributes', 0)
                    if not attributes & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
                        kept.append(name)
                except OSError as error:
                    errors.append(str(error))
            directories[:] = kept
            for name in files:
                if name.lower().endswith('.lnk'):
                    link = Path(current) / name
                    found[path_key(link)] = str(link)
    return sorted(found.values()), errors


def shortcut_arguments(original):
    if not original:
        return ''
    encoded = base64.b64encode(original.encode('utf-8')).decode('ascii')
    return '-ShortcutArgsBase64 ' + encoded


def make_plan(links, app_dir):
    executable = app_dir / 'Antigravity.exe'
    launcher = app_dir / 'Antigravity-Proxy.cmd'
    plans, ready, warnings = [], [], []
    for link in links:
        target = path_key(link['target'])
        original_icon = link.get('icon', '')
        # WScript.Shell represents the default target icon as ',0'.
        icon = original_icon if original_icon.split(',', 1)[0].strip() else str(executable) + ',0'
        if target == path_key(executable):
            arguments = shortcut_arguments(link.get('arguments', ''))
        elif target == path_key(launcher):
            arguments = link.get('arguments', '')
            if arguments and not re.fullmatch(r'-ShortcutArgsBase64 [A-Za-z0-9+/=]+', arguments):
                warnings.append('已有启动器快捷方式带有未知参数，保留不动：' + link['path'])
                continue
            if icon == original_icon:
                ready.append(link['path'])
                continue
        else:
            # Match by destination, never by the shortcut's display name.
            continue
        plans.append({
            'path': link['path'], 'target': str(launcher), 'arguments': arguments,
            'icon': icon,
            'working_directory': link.get('working_directory') or str(app_dir),
            'snapshot_hash': link.get('snapshot_hash'),
        })
    return plans, ready, warnings


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(path, data):
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.antigravity-proxy-', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def deploy_launchers(updates, original):
    """Rollback an interrupted two-file update using only in-memory old bytes."""
    attempted = []
    try:
        for path, data in updates.items():
            current = regular_bytes(path) if path.exists() else None
            if current != original[path]:
                raise ValueError('启动文件在扫描后已被修改：' + str(path))
            # Record before replacement: Ctrl+C may arrive after os.replace but
            # before atomic_write returns to its caller.
            attempted.append(path)
            atomic_write(path, data)
            print('[已部署] ' + str(path))
    except BaseException as error:
        rollback_errors = []
        for path in reversed(attempted):
            try:
                current = regular_bytes(path) if path.exists() else None
                if current == original[path]:
                    continue  # Replacement did not happen.
                if current != updates[path]:
                    raise ValueError('启动文件又被修改，保留当前内容')
                old = original[path]
                if old is None:
                    path.unlink()
                else:
                    atomic_write(path, old)
            except BaseException as rollback_error:
                rollback_errors.append('{}：{}'.format(path, rollback_error))
        detail = '\n回退未完成，请核对：' + '\n'.join(rollback_errors) if rollback_errors else '；本次已写入的启动文件已回退。'
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            print('[中断]' + detail)
            raise
        raise RuntimeError('代理启动文件部署失败：' + str(error) + detail) from error


def personal_menu_plan(folders, app_dir):
    if not folders.get('StartMenu'):
        raise ValueError('无法确定当前用户开始菜单目录。')
    menu = Path(folders['StartMenu']) / 'Programs'
    target = menu / 'Antigravity (Proxy).lnk'
    number = 2
    while target.exists():
        target = menu / ('Antigravity (Proxy {}).lnk'.format(number))
        number += 1
    return {'path': str(target), 'target': str(app_dir / 'Antigravity-Proxy.cmd'),
            'arguments': '', 'icon': str(app_dir / 'Antigravity.exe') + ',0',
            'working_directory': str(app_dir)}


def write_shortcut(plan):
    current = Path(plan['path'])
    current_hash = sha256(regular_bytes(current)) if current.exists() else None
    expected_hash = plan.get('snapshot_hash')
    if current_hash != expected_hash:
        raise RuntimeError('快捷方式在扫描后已被修改，保留当前内容。请重新运行脚本。')
    current.parent.mkdir(parents=True, exist_ok=True)
    run_powershell(dict(plan, action='write', before_hash=expected_hash))
    print('[已修复] ' + plan['path'])


def install(args):
    app_dir = discover_install(args.app_dir)
    policy = check_execution_policy()
    extra_roots = validate_scan_roots(read_launcher_scan_roots(app_dir) + list(args.scan_root))
    folders = run_powershell({'action': 'folders'})
    roots = scan_roots(folders, extra_roots)
    print('[安装目录] ' + str(app_dir))
    print('[执行策略] ' + policy + '（只读检查，不修改系统设置）')
    for root in roots:
        print('[扫描目录] ' + str(root))
    paths, warnings = find_shortcuts(roots)
    snapshot = run_powershell({'action': 'read', 'paths': paths})
    warnings.extend(snapshot['errors'])
    plans, ready, plan_warnings = make_plan(snapshot['links'], app_dir)
    warnings.extend(plan_warnings)
    print('[扫描结果] {} 个快捷方式；需要修复 {} 个；已配置 {} 个。'.format(len(paths), len(plans), len(ready)))
    menu_roots = [path_key(folders[name]) + '\\' for name in ('StartMenu', 'AllUsersStartMenu') if folders.get(name)]

    def has_menu_entry(paths_to_check):
        return any(any(path_key(path).startswith(root) for root in menu_roots) for path in paths_to_check)

    if not has_menu_entry([plan['path'] for plan in plans] + ready):
        plans.append(personal_menu_plan(folders, app_dir))
    content = {
        # Install the PS1 first so the CMD never points at a missing new script.
        app_dir / 'Antigravity-Proxy.ps1': launcher_ps1_bytes(extra_roots),
        app_dir / 'Antigravity-Proxy.cmd': LAUNCHER_CMD.replace('\n', '\r\n').encode('ascii'),
    }
    original = {path: regular_bytes(path) if path.exists() else None for path in content}
    updates = {path: data for path, data in content.items() if original[path] != data}
    for path in updates:
        print('[计划部署] ' + str(path))
    for plan in plans:
        print('[计划修复] {} -> {}'.format(plan['path'], plan['target']))
    for warning in warnings:
        print('[注意] ' + warning)
    if args.dry_run:
        print('[预览结束] 没有写入文件或修改快捷方式；公共开始菜单入口修改失败时将尝试创建个人入口。')
        return 2 if warnings else 0
    if not updates and not plans:
        print('[完成] 启动文件及已扫描的快捷方式都已配置，无需重复修改。')
        return 2 if warnings else 0

    # Reject concurrent edits before any deployment. The bridge checks again.
    for plan in plans:
        path = Path(plan['path'])
        current_hash = sha256(regular_bytes(path)) if path.exists() else None
        if current_hash != plan.get('snapshot_hash'):
            raise ValueError('快捷方式在扫描后已被修改，未开始写入：' + str(path))
    deploy_launchers(updates, original)
    failures = len(warnings)
    successful = list(ready)
    attempted = set()
    for plan in plans:
        attempted.add(path_key(plan['path']))
        try:
            write_shortcut(plan)
            successful.append(plan['path'])
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            failures += 1
            print('[失败] {}：{}'.format(plan['path'], error))
    # An inaccessible public entry is not a working search entry.
    if not has_menu_entry(successful):
        try:
            fallback = personal_menu_plan(folders, app_dir)
            if path_key(fallback['path']) not in attempted:
                write_shortcut(fallback)
                successful.append(fallback['path'])
                print('[个人入口] 公共入口不可用，已创建当前用户开始菜单入口。')
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            failures += 1
            print('[个人入口失败] ' + str(error))
    run_powershell({'action': 'notify'})
    print('[完成] 修改已保存；不创建备份或日志。移除代理请运行 Cleanup-Proxy-Shortcuts.py。')
    print('[说明] 不会结束正在运行的 Antigravity；新代理设置在下次完全退出后启动时生效。')
    if failures:
        print('[注意] 部分入口未处理。共享目录若提示拒绝访问，请以管理员身份重试；自定义目录可用 --scan-root 补充。')
    return 2 if failures else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='创建 Antigravity 系统代理启动器并修复 .lnk 快捷方式，不创建备份；自定义扫描目录记录在 PS1 注释中。')
    parser.add_argument('--app-dir', help='手动指定包含 Antigravity.exe 的安装目录')
    parser.add_argument('--scan-root', action='append', default=[], help='额外递归扫描目录，可重复使用')
    parser.add_argument('--dry-run', action='store_true', help='仅预览，不修改文件')
    args = parser.parse_args(argv)
    if sys.platform != 'win32':
        parser.error('此脚本仅支持 Windows。')
    try:
        return install(args)
    except KeyboardInterrupt:
        print('[中断] 用户取消操作。已完成的快捷方式仍保留；可重新运行脚本继续处理。')
        return 130
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
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
