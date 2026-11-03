"""Prepare and run a disposable Windows M1 acceptance copy; never launch the source."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import struct
import subprocess
import sys
import urllib.request
from urllib.parse import urlsplit

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / 'src' / 'localization'))
import antigravity_common as common

ENTRY = 'm1-entry.cjs'
AUDIT = 'm1-ui-audit.cjs'
SERVICE_CONTROL = 'm1-service-control.cjs'
DATA_DIRS = ('home', 'local', 'roaming', 'electron', 'session', 'logs', 'temp', 'evidence')


def regular(path, directory=False):
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) &
            getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024) or
            not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))):
        raise ValueError('Refusing a link or unexpected file type: ' + str(path))
    return path


def lab_root(value):
    path = Path(value).absolute()
    # Restrict this helper to direct, explicitly named disposable repository children.
    if path.parent.resolve() != REPOSITORY or not path.name.startswith('.m1-lab'):
        raise ValueError('--lab must be a direct repository child named .m1-lab or .m1-lab-*')
    if path.name != '.m1-lab' and not path.name.startswith('.m1-lab-'):
        raise ValueError('Invalid lab name')
    if path.exists():
        regular(path, directory=True)
    return path


def check_tree(path):
    regular(path, directory=True)
    for current, dirs, files in os.walk(path, followlinks=False):
        for name in dirs:
            regular(Path(current) / name, directory=True)
        for name in files:
            regular(Path(current) / name)


def hash_file(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def ensure_data(root):
    root.mkdir(exist_ok=True)
    regular(root, directory=True)
    for name in DATA_DIRS:
        folder = root / name
        folder.mkdir(exist_ok=True)
        regular(folder, directory=True)
    storage = root / 'electron' / 'app_storage.json'
    if storage.exists():
        regular(storage)
        values = json.loads(storage.read_text(encoding='utf-8'))
        if not isinstance(values, dict):
            raise ValueError('Invalid isolated app_storage.json')
    else:
        values = {}
    values.update({'autoCheckForUpdates': 'false', 'runInBackground': 'false',
                   'ide-install-wizard-shown': 'true'})
    storage.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding='utf-8')


def installation(root):
    install = regular(root / 'install', directory=True)
    regular(install / 'Antigravity.exe')
    regular(install / 'resources', directory=True)
    regular(install / 'resources' / 'app', directory=True)
    return install


def prepare(args):
    root = lab_root(args.lab)
    if (root / 'install').exists():
        raise ValueError('The isolated install already exists; choose a new --lab directory')
    source = Path(args.source).resolve()
    if source == root or source in root.parents or root in source.parents:
        raise ValueError('Source and lab must not overlap')
    check_tree(source)
    executable = regular(source / 'Antigravity.exe')
    resources = source / 'resources'
    archives = [p for p in (resources / 'app.asar', resources / 'app.asar.disabled') if p.exists()]
    if len(archives) != 1:
        raise ValueError('Expected exactly one original app.asar or app.asar.disabled')
    validated = common.validate_asar(archives[0], resources / 'app.asar.unpacked')
    with validated['archive'].open('rb') as stream:
        package = json.loads(common._read_entry(stream, validated['records']['package.json'], 'bytes'))
    if package.get('version') != args.version:
        raise ValueError('Source archive version does not match --version')
    with executable.open('rb') as stream:
        stream.seek(0x3c)
        offset = struct.unpack('<I', stream.read(4))[0]
        stream.seek(offset)
        if stream.read(4) != b'PE\0\0' or struct.unpack('<H', stream.read(2))[0] != 0x8664:
            raise ValueError('Expected a Windows x64 executable')
    root.mkdir(exist_ok=True)

    def ignore(directory, names):
        directory = Path(directory)
        if directory == source:
            return [name for name in names if name.casefold().startswith(('antigravity-proxy.', 'uninstall'))]
        if directory == resources:
            return [name for name in names if name in ('app', 'app.asar', 'app.asar.disabled')]
        return []

    target = root / 'install'
    # No dirs_exist_ok: a partial copy is retained for diagnosis, never overwritten.
    shutil.copytree(source, target, ignore=ignore)
    archive = target / 'resources' / 'app.asar.disabled'
    shutil.copy2(validated['archive'], archive)
    common.extract_asar(archive, target / 'resources' / 'app', target / 'resources' / 'app.asar.unpacked')
    ensure_data(root)
    evidence = {'version': package['version'], 'architecture': 'x64', 'source': str(source),
                'archiveSha256': hash_file(validated['archive']),
                'languageServerSha256': hash_file(resources / 'bin' / 'language_server.exe'),
                'originalMain': package.get('main'), 'archiveEntries': len(validated['records'])}
    (root / 'prepared.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print('Prepared isolated copy: ' + str(root))


def manual_proxy_environment():
    """Read only Windows manual settings, never inherited proxy/credential values."""
    import winreg

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Internet Settings')
    except FileNotFoundError:
        return {}
    except OSError:
        raise ValueError('Cannot read Windows proxy settings; login was not started') from None
    with key:
        def setting(name, default):
            try:
                return winreg.QueryValueEx(key, name)[0]
            except FileNotFoundError:
                return default
            except OSError:
                raise ValueError('Cannot read Windows proxy settings; login was not started') from None
        if setting('AutoConfigURL', '') or setting('AutoDetect', 0):
            raise ValueError('PAC/automatic proxy discovery is unsupported; use a manual HTTP proxy or direct mode')
        enabled = setting('ProxyEnable', 0)
        if enabled not in (0, 1):
            raise ValueError('Invalid Windows manual proxy switch')
        if not enabled:
            return {}
        server = setting('ProxyServer', '')
        if not isinstance(server, str) or not server.strip():
            raise ValueError('Windows manual proxy is enabled but its server is missing')
        if '=' in server or ';' in server:
            entries = server.split(';')
            if any('=' not in entry or not all(part.strip() for part in entry.split('=', 1))
                   for entry in entries if entry):
                raise ValueError('Invalid Windows manual proxy configuration')
    # This API reads the registry directly and does not merge process proxy variables.
    proxies = urllib.request.getproxies_registry()
    if not proxies or any(key not in ('http', 'https', 'ftp') for key in proxies):
        raise ValueError('Unsupported Windows proxy type; use a manual HTTP proxy')
    result = {}
    for protocol in ('http', 'https'):
        address = proxies.get(protocol)
        if address is None:
            continue
        try:
            parsed = urlsplit(address)
            port = parsed.port
            valid = (parsed.scheme == 'http' and parsed.hostname and not parsed.username
                     and parsed.password is None and not parsed.query and not parsed.fragment
                     and parsed.path in ('', '/') and port != 0
                     and not any(c.isspace() for c in address) and '\\' not in address)
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise ValueError('Only unauthenticated manual HTTP proxies are supported; proxy details were not logged')
        result[protocol.upper() + '_PROXY'] = address
    if not result:
        raise ValueError('Windows manual proxy has no supported HTTP/HTTPS destination mapping')
    return result


def child_environment(root, allow_login=False):
    # No inherited credentials, proxy variables, development URLs or Electron flags.
    keep = ('SystemRoot', 'WINDIR', 'ComSpec', 'PATHEXT', 'OS',
            'NUMBER_OF_PROCESSORS', 'PROCESSOR_ARCHITECTURE')
    source = {key.upper(): value for key, value in os.environ.items()}
    env = {name: source[name.upper()] for name in keep if name.upper() in source}
    windows = Path(source.get('SYSTEMROOT', r'C:\Windows'))
    env['SystemRoot'] = str(windows)
    env['PATH'] = ';'.join(str(windows / suffix) for suffix in ('System32', '', r'System32\Wbem', r'System32\WindowsPowerShell\v1.0'))
    home = root / 'home'
    env.update(USERPROFILE=str(home), HOME=str(home), HOMEDRIVE=home.drive,
               HOMEPATH=str(home)[len(home.drive):], APPDATA=str(root / 'roaming'),
               LOCALAPPDATA=str(root / 'local'), TEMP=str(root / 'temp'), TMP=str(root / 'temp'),
               ANTIGRAVITY_M1_LAB=str(root), NO_PROXY='127.0.0.1,localhost,::1',
               no_proxy='127.0.0.1,localhost,::1')
    if allow_login:
        env.update(manual_proxy_environment())
        env['ANTIGRAVITY_M1_LOGIN'] = '1'
    return env


def package_backup(root, package_path, refresh):
    current = regular(package_path).read_bytes()
    package = json.loads(current)
    if not isinstance(package, dict):
        raise ValueError('Invalid isolated package.json')

    def validate_main(value, require_file=True):
        entry = value.get('main') if isinstance(value, dict) else None
        if not isinstance(entry, str) or not entry or entry == ENTRY:
            raise ValueError('Original package has no valid main entry')
        resolved = (package_path.parent / entry).resolve()
        if package_path.parent.resolve() not in resolved.parents:
            raise ValueError('Original main entry escapes isolated application')
        if require_file:
            regular(resolved)

    backup = root / 'launch-package.json'
    if backup.exists():
        saved = regular(backup).read_bytes()
        original = json.loads(saved)
        # A reset/reinstall can legitimately remove the old entry. Archived
        # metadata must be well formed, but only the entry we will use must exist.
        validate_main(original, require_file=False)
        if package.get('main') == ENTRY:
            expected = dict(original, main=ENTRY)
            if package != expected:
                raise ValueError('Wrapped package differs from the preserved original backup')
            validate_main(original)
            return saved
        if current == saved:
            validate_main(original)
            return saved
        if not refresh:
            raise ValueError('Package changed; inspect it, then use --refresh-package to archive and refresh the backup')
        validate_main(package)
        history = root / 'package-backups'
        history.mkdir(exist_ok=True)
        regular(history, directory=True)
        name = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ.json')
        with (history / name).open('xb') as stream:
            stream.write(saved)
    elif package.get('main') == ENTRY:
        raise ValueError('Wrapped package has no preserved original; refusing to guess its entry')
    validate_main(package)
    backup.write_bytes(current)
    return current


def request_stop(root):
    installation(root)
    marker = root / 'stop'
    if marker.exists():
        regular(marker)
    marker.write_text('stop\n', encoding='ascii')


def request_capture(root):
    """Queue one user-requested audit; this command never starts or inspects UI."""
    root = lab_root(root)
    regular(root, directory=True)
    installation(root)
    regular(root / 'evidence', directory=True)
    marker = root / 'capture-request.json'
    try:
        marker.lstat()
    except FileNotFoundError:
        pass
    else:
        regular(marker)
        raise ValueError('An audit request is already pending; it was not overwritten')
    request_id = secrets.token_hex(16)
    result = root / 'evidence' / ('ui-' + request_id + '.json')
    try:
        result.lstat()
    except FileNotFoundError:
        pass
    else:
        regular(result)
        raise ValueError('The audit result identifier already exists; retry capture')
    temporary = root / ('.capture-request-' + request_id + '.tmp')
    # Publish a complete JSON file atomically, without replacing a concurrent request.
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump({'schemaVersion': 1, 'id': request_id}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        if os.name == 'nt':
            # Windows rename is atomic and refuses an existing destination.
            os.rename(str(temporary), str(marker))
        else:
            # POSIX rename would overwrite; a hard link provides exclusive publication.
            os.link(str(temporary), str(marker))
    except FileExistsError:
        raise ValueError('An audit request was queued concurrently; it was not overwritten') from None
    finally:
        try:
            regular(temporary).unlink()
        except FileNotFoundError:
            pass
    return result


def request_service_restart(root, from_report):
    """Publish one bound restart request; only the running harness acts on it."""
    root = lab_root(root)
    regular(root, directory=True)
    installation(root)
    evidence = regular(root / 'evidence', directory=True)
    report_path = Path(from_report)
    match = re.fullmatch(r'ui-([a-f0-9]{32})\.json', report_path.name)
    if not report_path.is_absolute() or report_path.parent != evidence or not match:
        raise ValueError('--from-report must name a ui report directly inside this lab evidence directory')

    def bounded_read(path, limit):
        regular(path)
        with path.open('rb') as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Evidence or launcher record exceeds its size limit')
        return data

    def positive_integer(value, maximum=9007199254740991):
        return type(value) is int and 1 <= value <= maximum

    def pid_record(path):
        data = bounded_read(path, 32)
        if not re.fullmatch(rb'[1-9][0-9]{0,15}\s*', data):
            raise ValueError('Invalid isolated launcher process record')
        number = int(data)
        if not positive_integer(number):
            raise ValueError('Invalid isolated launcher process record')
        return number, data

    raw = bounded_read(report_path, 256 * 1024)
    try:
        report = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError('Invalid UI evidence JSON') from None
    if (not isinstance(report, dict) or type(report.get('schemaVersion')) is not int or
            report['schemaVersion'] != 1 or report.get('requestId') != match.group(1) or
            report.get('status') != 'ok' or type(report.get('preloadErrors')) is not int or
            report['preloadErrors'] != 0):
        raise ValueError('Expected a successful UI report without preload errors')
    bridge = report.get('bridge')
    if (not isinstance(bridge, dict) or bridge.get('mode') != 'controlled-success' or
            not positive_integer(bridge.get('authorizedSnapshots'))):
        raise ValueError('Restart requires an authorized controlled-success report')
    captured = report.get('capturedAt')
    try:
        if not isinstance(captured, str) or len(captured) > 64:
            raise ValueError()
        captured = datetime.datetime.fromisoformat(captured.replace('Z', '+00:00'))
        if captured.tzinfo is None or captured.utcoffset() is None:
            raise ValueError()
        age = (datetime.datetime.now(datetime.timezone.utc) - captured).total_seconds()
    except (ValueError, TypeError, OverflowError):
        raise ValueError('UI evidence must include a valid timezone-aware capture time') from None
    if not 0 <= age <= 300:
        raise ValueError('UI evidence is stale or from the future; capture the current home page again')
    lifecycle = report.get('lifecycle')
    if not isinstance(lifecycle, dict):
        raise ValueError('UI evidence lacks the current lifecycle contract; restart the updated harness and capture again')
    session_id = lifecycle.get('sessionId')
    service = lifecycle.get('service')
    if (not isinstance(session_id, str) or not re.fullmatch(r'[a-f0-9]{32}', session_id) or
            not positive_integer(lifecycle.get('appPid')) or not isinstance(service, dict) or
            not positive_integer(service.get('generation')) or not positive_integer(service.get('pid')) or
            not positive_integer(service.get('port'), 65535) or service['pid'] == lifecycle['appPid']):
        raise ValueError('Invalid isolated service lifecycle evidence')
    windows = report.get('windows')
    if not isinstance(windows, list) or len(windows) != 1 or not isinstance(windows[0], dict):
        raise ValueError('Restart requires exactly one eligible home window')
    window = windows[0]
    security, ui = window.get('security'), window.get('ui')
    route = ui.get('route') if isinstance(ui, dict) else None
    if (not positive_integer(window.get('windowId')) or type(window.get('port')) is not int or
            window['port'] != service['port'] or not isinstance(security, dict) or
            security.get('contextIsolation') is not True or security.get('sandbox') is not True or
            security.get('nodeIntegration') is not False or not isinstance(route, dict) or
            route.get('path') != '/' or route.get('hasQuery') is not False or route.get('hasHash') is not False):
        raise ValueError('Restart requires a safe home window without query or fragment state')
    launcher_pid, launcher_raw = pid_record(root / 'launch.lock')
    app_pid, app_raw = pid_record(root / 'pid')
    if app_pid != lifecycle['appPid'] or launcher_pid == app_pid:
        raise ValueError('UI evidence does not match the isolated launcher process records')
    try:
        (root / 'stop').lstat()
    except FileNotFoundError:
        pass
    else:
        raise ValueError('The isolated launcher is stopping; no restart request was queued')
    marker = root / 'restart-service-request.json'
    try:
        marker.lstat()
    except FileNotFoundError:
        pass
    else:
        regular(marker)
        raise ValueError('A service restart request is already pending; it was not overwritten')
    request_id = secrets.token_hex(16)
    result = evidence / ('service-restart-' + request_id + '.json')
    claim = evidence / ('service-restart-' + request_id + '.claim.json')
    for path in (result, claim):
        try:
            path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise ValueError('The service restart identifier already exists; no request was queued')
    # Recheck the input records immediately before exclusive publication. The
    # running harness independently rechecks session, child identity and window.
    if (bounded_read(report_path, 256 * 1024) != raw or
            pid_record(root / 'launch.lock')[1] != launcher_raw or
            pid_record(root / 'pid')[1] != app_raw):
        raise ValueError('UI evidence or launcher records changed; capture again before retrying')
    request = {'schemaVersion': 1, 'id': request_id, 'sessionId': session_id,
               'expectedGeneration': service['generation'], 'expectedPid': service['pid'],
               'expectedPort': service['port'], 'expectedWindowId': window['windowId']}
    temporary = root / ('.restart-service-request-' + request_id + '.tmp')
    created = False
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            created = True
            json.dump(request, stream)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == 'nt':
            os.rename(str(temporary), str(marker))
        else:
            os.link(str(temporary), str(marker))
    except FileExistsError:
        raise ValueError('A service restart request was queued concurrently; it was not overwritten') from None
    finally:
        if created:
            try:
                regular(temporary).unlink()
            except FileNotFoundError:
                pass
    return result


def launch(args):
    if os.name != 'nt':
        raise ValueError('Launching the real acceptance copy requires Windows')
    root = lab_root(args.lab)
    install = installation(root)
    # Validate proxy/environment and assets before changing any package or backup.
    env = child_environment(root, args.allow_login)
    env['ANTIGRAVITY_M1_TRANSLATION_TEST'] = getattr(args, 'translation_test', 'disabled')
    assets = [regular(Path(__file__).with_name(name)) for name in (ENTRY, AUDIT, SERVICE_CONTROL)]
    lock = root / 'launch.lock'
    # A stale lock is intentionally not stolen: inspect processes before manual removal.
    try:
        descriptor = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ValueError('The isolated launcher lock already exists. Stop the previous launcher with Ctrl+C '
                         'and wait for exit, or use m1_lab.py stop. If no launcher remains, report the lock '
                         'for process verification; do not delete it blindly.') from None
    try:
        with os.fdopen(descriptor, 'w', encoding='ascii') as stream:
            stream.write(str(os.getpid()))
        ensure_data(root)
        package_path = install / 'resources' / 'app' / 'package.json'
        saved = package_backup(root, package_path, args.refresh_package)
        for asset in assets:
            destination = package_path.parent / asset.name
            if destination.exists():
                regular(destination)
            shutil.copy2(asset, destination)
        package = json.loads(saved)
        package['main'] = ENTRY
        package_path.write_text(json.dumps(package, indent=2), encoding='utf-8')
        marker = root / 'stop'
        if marker.exists():
            regular(marker).unlink()
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        log_path = root / 'evidence' / ('launch-' + stamp + '.log')
        with log_path.open('xb') as log:
            if args.allow_login:
                log.write(b'User-operated login mode: native stdout/stderr capture disabled.\n')
                log.flush()
            process = subprocess.Popen([str(install / 'Antigravity.exe'), '--wsl-distro='],
                                       cwd=str(install), env=env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL if args.allow_login else log,
                                       stderr=subprocess.DEVNULL if args.allow_login else subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
            (root / 'pid').write_text(str(process.pid), encoding='ascii')
            print('Isolated PID: {}; log: {}'.format(process.pid, log_path), flush=True)
            forced = False
            try:
                process.wait(timeout=args.duration)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                request_stop(root)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    # Only this helper's still-running child and its descendants are targeted.
                    forced = True
                    taskkill = Path(env['SystemRoot']) / 'System32' / 'taskkill.exe'
                    subprocess.run([str(taskkill), '/PID', str(process.pid), '/T', '/F'],
                                   stdout=log, stderr=subprocess.STDOUT, check=False,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                    process.wait(timeout=15)
            print('Isolated exit code: {}; forced tree stop: {}'.format(process.returncode, forced))
            if process.returncode != 0 or forced:
                return 1
        return 0
    finally:
        regular(lock).unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'launch', 'stop', 'capture', 'restart-service'):
        command = commands.add_parser(name)
        command.add_argument('--lab', default=str(REPOSITORY / '.m1-lab'))
        if name == 'prepare':
            command.add_argument('--source', required=True, help='Source install directory, read only')
            command.add_argument('--version', default='2.28.2')
        if name == 'restart-service':
            command.description = ('Queue a user-requested, single isolated language-service termination '
                                   'to test the application automatic recovery. No process is changed by this CLI.')
            command.add_argument('--from-report', required=True,
                                 help='Absolute path to a current controlled-success home UI report from this lab')
        if name == 'launch':
            command.add_argument('--translation-test', choices=('disabled', 'success', 'failure'), default='disabled',
                                 help='Controlled lab responses only; never uses an external AI provider')
            command.add_argument('--duration', type=int, default=60, help='Seconds before requesting graceful stop (default: 60)')
            command.add_argument('--refresh-package', action='store_true')
            command.add_argument('--allow-login', action='store_true',
                                 help='Allow user-operated login and manual system HTTP proxy; never submits login or AI requests')
    args = parser.parse_args(argv)
    if args.command == 'launch' and not 1 <= args.duration <= 3600:
        parser.error('--duration must be between 1 and 3600 seconds')
    try:
        if args.command == 'prepare':
            prepare(args)
        elif args.command == 'launch':
            return launch(args)
        elif args.command == 'capture':
            result = request_capture(args.lab)
            print('Queued fixed-UI audit request only; no application was started.')
            print('Result will be written by the updated running harness: ' + str(result))
        elif args.command == 'restart-service':
            result = request_service_restart(args.lab, args.from_report)
            print('Queued a single isolated service restart test; this CLI did not change any process.')
            print('The running harness will recheck the captured session and exact child before acting.')
            print('Result will be written by the running harness: ' + str(result))
        else:
            request_stop(lab_root(args.lab))
            print('Requested stop for isolated lab only')
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('M1 lab error: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
