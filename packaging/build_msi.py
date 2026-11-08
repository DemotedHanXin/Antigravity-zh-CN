"""Build a per-user MSI with Python 3.12's Windows Installer bindings.

No installation is performed. All files come from the already-smoked frozen
directory. User dictionaries and target Antigravity files are never MSI assets.
"""
from pathlib import Path
import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
import warnings

warnings.filterwarnings('ignore', message="'msilib' is deprecated", category=DeprecationWarning)
import msilib
from msilib import schema, sequence

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.1.0'
NAMESPACE = uuid.UUID('7e373aaf-0b86-4c72-a4e9-10a85f60efd1')
UPGRADE_CODE = '{CF80CA35-AE70-4377-863F-D470A4D76E55}'


def guid(value):
    return '{' + str(uuid.uuid5(NAMESPACE, value)).upper() + '}'


def identifier(prefix, value):
    return prefix + hashlib.sha256(value.encode('utf-8')).hexdigest()[:30]


def rows(db, table, fields):
    query = ', '.join('`' + field + '`' for field in fields)
    view = db.OpenView(f'SELECT {query} FROM `{table}`')
    view.Execute(None)
    found = []
    while record := view.Fetch():
        found.append(tuple(record.GetString(i + 1) for i in range(len(fields))))
    view.Close()
    return found


def execute(db, sql):
    view = db.OpenView(sql)
    view.Execute(None)
    view.Close()


def set_codepage(path, temporary):
    """The stdlib omits Database.Import; call the same Windows Installer API."""
    codepage = temporary / 'codepage.idt'
    codepage.write_text('\n\n936\t_ForceCodepage\n', encoding='ascii')
    msi = ctypes.WinDLL('msi')
    msi.MsiOpenDatabaseW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    msi.MsiDatabaseImportW.argtypes = [ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_wchar_p]
    msi.MsiDatabaseCommit.argtypes = [ctypes.c_uint]
    msi.MsiCloseHandle.argtypes = [ctypes.c_uint]
    handle = ctypes.c_uint()
    result = msi.MsiOpenDatabaseW(str(path), ctypes.c_void_p(1), ctypes.byref(handle))
    if result:
        raise OSError(result, 'Cannot open MSI for localization')
    try:
        result = msi.MsiDatabaseImportW(handle, str(temporary), codepage.name)
        if result:
            raise OSError(result, 'Cannot set MSI code page')
        result = msi.MsiDatabaseCommit(handle)
        if result:
            raise OSError(result, 'Cannot commit MSI code page')
    finally:
        msi.MsiCloseHandle(handle)


def dialogs(db):
    msilib.add_data(db, 'TextStyle', [('Normal', 'Microsoft YaHei UI', 9, 0, 0)])
    msilib.add_data(db, 'Property', [('DefaultUIFont', 'Normal')])
    welcome = msilib.Dialog(db, 'WelcomeDlg', 50, 50, 370, 220, 3,
                           '[ProductName] 安装', 'Install', 'Install', 'Cancel')
    welcome.text('Title', 20, 20, 330, 30, 3, '安装 Antigravity 中文助手')
    welcome.text('Details', 20, 60, 330, 100, 3,
                 '将安装到当前用户的本地程序目录，并创建开始菜单入口。\r\n\r\n'
                 '安装助手不会自动汉化 Antigravity 或修改代理。'
                 '升级和卸载保留个人词典与设置。')
    welcome.pushbutton('Install', 200, 180, 70, 20, 3, '安装', 'Cancel').event('EndDialog', 'Return')
    welcome.pushbutton('Cancel', 280, 180, 70, 20, 3, '取消', 'Install').event('EndDialog', 'Exit')
    maintenance = msilib.Dialog(db, 'MaintenanceDlg', 50, 50, 370, 220, 3,
                               '[ProductName]', 'Repair', 'Repair', 'Cancel')
    maintenance.text('Details', 20, 30, 330, 100, 3,
                     '助手已经安装。可以修复程序文件或卸载助手。\r\n\r\n'
                     '个人词典、设置和 Antigravity 安装均会保留。')
    repair = maintenance.pushbutton('Repair', 120, 180, 70, 20, 3, '修复', 'Remove')
    repair.event('[REINSTALL]', 'ALL', ordering=1)
    repair.event('[REINSTALLMODE]', 'amus', ordering=2)
    repair.event('EndDialog', 'Return', ordering=3)
    remove = maintenance.pushbutton('Remove', 200, 180, 70, 20, 3, '卸载', 'Cancel')
    remove.event('[REMOVE]', 'ALL', ordering=1)
    remove.event('EndDialog', 'Return', ordering=2)
    maintenance.pushbutton('Cancel', 280, 180, 70, 20, 3, '取消', 'Repair').event('EndDialog', 'Exit')
    for name, message in (
        ('ExitDialog', '操作已完成。个人词典和设置会保留。'),
        ('FatalError', '安装未完成。请检查磁盘空间和目录权限后重试。'),
        ('UserExit', '操作已取消。'),
    ):
        dialog = msilib.Dialog(db, name, 50, 50, 370, 180, 3, '[ProductName]', 'Finish', 'Finish', 'Finish')
        dialog.text('Result', 20, 30, 330, 90, 3, message)
        dialog.pushbutton('Finish', 280, 140, 70, 20, 3, '关闭', 'Finish').event('EndDialog', 'Return')
    msilib.add_data(db, 'InstallUISequence', [
        ('WelcomeDlg', 'NOT Installed', 1210),
        ('MaintenanceDlg', 'Installed AND NOT REMOVE', 1220),
    ])


def _build_database(payload, output):
    payload, output = Path(payload).resolve(), Path(output).resolve()
    if not (payload / 'AntigravityZhCN.exe').is_file():
        raise ValueError('Build the frozen onedir application first.')
    if not output.is_relative_to(ROOT / 'dist') or output.suffix != '.msi':
        raise ValueError('MSI output must be under this workspace dist directory.')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = ROOT / 'build' / 'tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ['TEMP'] = os.environ['TMP'] = str(temporary)
    db = msilib.init_database(str(output), schema, 'Antigravity ZhCN',
                             guid('product:' + VERSION), VERSION, 'Antigravity-zh Contributors')
    # Set the database code page before introducing any translated strings.
    del db
    set_codepage(output, temporary)
    db = msilib.OpenDatabase(str(output), msilib.MSIDBOPEN_TRANSACT)
    execute(db, "UPDATE `Property` SET `Value`='Antigravity 中文助手' WHERE `Property`='ProductName'")
    execute(db, "UPDATE `Property` SET `Value`='2052' WHERE `Property`='ProductLanguage'")
    summary = db.GetSummaryInformation(20)
    summary.SetProperty(msilib.PID_TEMPLATE, 'x64;2052')
    summary.SetProperty(msilib.PID_PAGECOUNT, 500)
    summary.SetProperty(msilib.PID_WORDCOUNT, 10)  # compressed + no elevation
    summary.SetProperty(msilib.PID_CODEPAGE, 936)
    summary.Persist()
    msilib.add_tables(db, sequence)
    for table in ('InstallExecuteSequence', 'InstallUISequence'):
        execute(db, f"UPDATE `{table}` SET `Sequence`=300 WHERE `Action`='LaunchConditions'")
    execute(db, "UPDATE `InstallExecuteSequence` SET `Sequence`=1510 WHERE `Action`='RemoveExistingProducts'")
    msilib.add_data(db, 'Property', [
        ('UpgradeCode', UPGRADE_CODE), ('INSTALLLEVEL', '1'),
        ('ARPCOMMENTS', '本地汉化、词典和代理启动助手；卸载保留用户数据。'),
        ('ARPNOMODIFY', '1'), ('ARPURLINFOABOUT', 'https://github.com/DemotedHanXin/Antigravity-zh-CN'),
        ('SecureCustomProperties', 'OLDPRODUCTS;NEWERPRODUCTS'),
    ])
    msilib.add_data(db, 'Upgrade', [
        (UPGRADE_CODE, None, VERSION, None, 1, None, 'OLDPRODUCTS'),
        (UPGRADE_CODE, VERSION, None, None, 2, None, 'NEWERPRODUCTS'),
    ])
    msilib.add_data(db, 'LaunchCondition', [
        # Windows Installer reports VersionNT64=603 on Windows 10 and 11.
        ('VersionNT64 >= 603', '需要现代 64 位 Windows；本版本在 Windows 11 上验证。'),
        ('NOT ALLUSERS', '此安装包仅支持为当前用户安装。'),
        ('NOT NEWERPRODUCTS', '已安装更高版本的助手，请使用该版本。'),
    ])
    cabinet = msilib.CAB('application.cab')
    feature = msilib.Feature(db, 'Application', 'Antigravity 中文助手', '程序和运行依赖', 1)
    feature.set_current()
    msilib._directories.clear()
    target = msilib.Directory(db, cabinet, None, str(payload), 'TARGETDIR', 'SourceDir', 0)
    local = msilib.Directory(db, cabinet, target, '', 'LocalAppDataFolder', '.', 0)
    programs = msilib.Directory(db, cabinet, local, '', 'LocalPrograms', 'Programs', 0)
    install = msilib.Directory(db, cabinet, programs, '', 'INSTALLDIR', 'AntigravityZhCN', 0)
    directories = {Path('.'): install}
    expected = {}
    for source in sorted(payload.rglob('*')):
        if not source.is_file():
            continue
        relative = source.relative_to(payload)
        if source.is_symlink() or not source.resolve().is_relative_to(payload):
            raise ValueError('Refusing linked files outside the package.')
        current = Path('.')
        for part in relative.parts[:-1]:
            next_path = current / part
            if next_path not in directories:
                base = directories[current]
                directories[next_path] = msilib.Directory(
                    db, cabinet, base, part, identifier('D_', next_path.as_posix()),
                    base.make_short(part) + '|' + part, 0)
            current = next_path
        directory = directories[relative.parent]
        key = relative.as_posix()
        component = identifier('C_', key)
        directory.start_component(component, feature, 0, source.name, guid('file:' + key))
        file_id = directory.add_file(source.name)
        expected[file_id] = {'path': key, 'size': source.stat().st_size,
                             'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    menu = msilib.Directory(db, cabinet, target, '', 'ProgramMenuFolder', '.', 0)
    msilib.add_data(db, 'Component', [
        ('MenuComponent', guid('start-menu'), menu.logical, 260, None, 'MenuRegistry'),
    ])
    msilib.add_data(db, 'FeatureComponents', [('Application', 'MenuComponent')])
    msilib.add_data(db, 'Registry', [('MenuRegistry', 1, 'Software\\AntigravityZhCN\\Installer',
                                     'StartMenu', '#1', 'MenuComponent')])
    msilib.add_data(db, 'Shortcut', [('StartMenu', menu.logical, 'AGZHCN|Antigravity 中文助手',
                                    'MenuComponent', '[INSTALLDIR]AntigravityZhCN.exe', None,
                                    'Antigravity 中文助手', None, None, None, 1, 'INSTALLDIR')])
    dialogs(db)
    cab_path = ROOT / 'build' / 'application.cab'
    if cab_path.exists():
        cab_path.unlink()
    msilib.FCICreate(str(cab_path), cabinet.files)
    msilib.add_data(db, 'Media', [(1, cabinet.index, None, '#' + cabinet.name, None, None)])
    msilib.add_stream(db, cabinet.name, str(cab_path))
    db.Commit()
    del db
    return output, expected, cab_path, temporary


def build(payload, output):
    output, expected, cab_path, temporary = _build_database(payload, output)
    report = validate(output, expected)
    # Verify every compressed byte without registering or installing the MSI.
    with tempfile.TemporaryDirectory(prefix='msi-cab-', dir=temporary) as extraction:
        expanded = subprocess.run(['expand.exe', '-F:*', str(cab_path), extraction],
                                  capture_output=True)
        if expanded.returncode:
            raise RuntimeError('MSI cabinet extraction failed: ' + str(expanded.returncode))
        for file_id, info in expected.items():
            actual = Path(extraction) / file_id
            if hashlib.sha256(actual.read_bytes()).hexdigest() != info['sha256']:
                raise RuntimeError('MSI cabinet content mismatch: ' + info['path'])
    report['cabinetContentHashesVerified'] = True
    (ROOT / 'build' / 'msi-validation.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return output


def validate(path, expected):
    """Read back the generated database and verify its install/uninstall scope."""
    db = msilib.OpenDatabase(str(path), msilib.MSIDBOPEN_READONLY)
    properties = dict(rows(db, 'Property', ('Property', 'Value')))
    files = rows(db, 'File', ('File', 'FileSize'))
    components = rows(db, 'Component', ('Component', 'Directory_', 'KeyPath'))
    assert len(files) == len(expected) and {key for key, _ in files} == expected.keys()
    assert all(int(size) == expected[key]['size'] for key, size in files)
    assert 'ALLUSERS' not in properties
    assert properties['UpgradeCode'] == UPGRADE_CODE
    assert properties['ProductName'] == 'Antigravity 中文助手'
    assert len(components) == len(files) + 1
    assert not rows(db, 'CustomAction', ('Action',))
    assert not rows(db, 'RemoveRegistry', ('RemoveRegistry',))
    for _, _, _, directory, _ in rows(db, 'RemoveFile', ('FileKey', 'Component_', 'FileName', 'DirProperty', 'InstallMode')):
        assert directory.startswith('D_') or directory == 'INSTALLDIR'
    assert len(rows(db, 'Shortcut', ('Shortcut',))) == 1
    assert rows(db, 'Registry', ('Root', 'Key')) == [('1', 'Software\\AntigravityZhCN\\Installer')]
    assert rows(db, 'Media', ('Cabinet',)) == [('#application.cab',)]
    return {'fileCount': len(files), 'components': len(components), 'scope': 'per-user',
            'customActions': 0, 'userDataOwned': False, 'files': expected}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--payload', default=str(ROOT / 'dist' / 'AntigravityZhCN'))
    parser.add_argument('--output', default=str(ROOT / 'dist' / f'AntigravityZhCN-{VERSION}-Setup-x64.msi'))
    args = parser.parse_args()
    print(build(args.payload, args.output))
