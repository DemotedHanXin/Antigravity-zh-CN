# coding: utf-8
"""Versioned DragonGirl user data. No networking, imports, or install-tree writes.

Lock contract shared with localization_runtime/storage.cjs: exclusive mkdir of
.translation.lock; owner.json is diagnostic only. Never steal a stale lock.
"""
import copy
import datetime
import json
import ipaddress
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
from contextlib import contextmanager
from urllib.parse import urlsplit

PROVIDERS = ('openai', 'gemini', 'claude', 'compatible')
DEFAULT_URLS = {
    'openai': 'https://api.openai.com/v1',
    'gemini': 'https://generativelanguage.googleapis.com/v1beta',
    'claude': 'https://api.anthropic.com/v1',
    'compatible': '',
}
DEFAULT_LIMITS = dict(concurrency=2, batchSize=8, batchCharacters=2000,
                      textLength=160, timeoutMs=15000, requestsPerMinute=12,
                      queueSize=128, sessionRequests=100)
LIMIT_BOUNDS = {name: (1000 if name == 'timeoutMs' else 1, maximum)
                for name, maximum in DEFAULT_LIMITS.items()}
MAX_FILE_BYTES = 4 * 1024 * 1024


class DataError(ValueError):
    """Safe user-facing diagnostic that never includes file content or secrets."""


class ConflictError(DataError):
    pass


def user_data_dir(platform=None, environ=None, home=None):
    platform = platform or sys.platform
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    if platform == 'win32':
        base = environ.get('APPDATA')
        if not base or not Path(base).is_absolute():
            raise DataError('APPDATA 未设置，无法安全确定用户目录。')
        return Path(base) / 'Antigravity-zh-CN'
    if platform == 'darwin':
        return home / 'Library' / 'Application Support' / 'Antigravity-zh-CN'
    xdg = environ.get('XDG_CONFIG_HOME')
    return (Path(xdg) if xdg and Path(xdg).is_absolute() else home / '.config') / 'Antigravity-zh-CN'


def default_config():
    return dict(schemaVersion=1, revision=0, enabled=False, autoSave=False,
                cacheEpoch=0, provider='openai',
                providers={name: dict(baseUrl=DEFAULT_URLS[name], model='', apiKey='')
                           for name in PROVIDERS}, limits=dict(DEFAULT_LIMITS))


def default_dictionary():
    return dict(schemaVersion=1, revision=0, entries={}, tombstones={})


def _integer(value, low=0, high=2**53-1):
    return type(value) is int and low <= value <= high


def _header(data):
    if not isinstance(data, dict) or data.get('schemaVersion') != 1 or type(data.get('schemaVersion')) is not int:
        raise DataError('数据格式版本不支持；原文件已保留。')
    if not _integer(data.get('revision')):
        raise DataError('数据版本号无效；原文件已保留。')


def _units(value):
    try:
        return len(value.encode('utf-16-le')) // 2
    except UnicodeError:
        return 2**53


def validate_url(value, allow_empty=True):
    if not isinstance(value, str) or _units(value) > 2048:
        raise DataError('API 地址无效。')
    if not value and allow_empty:
        return
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise DataError('API 地址无效。') from None
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or any(c.isspace() for c in value)
            or '\\' in value or port == 0):
        raise DataError('仅接受无凭据、查询参数或片段的 HTTPS API 地址。')
    host = parsed.hostname.lower().rstrip('.')
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal', '.test', '.invalid')) or '.' not in host:
        raise DataError('API 地址必须是公共 HTTPS 主机，不支持本机或内网地址。')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise DataError('API 地址必须使用公共域名，不接受 IP 字面地址。')


def validate_config(data):
    _header(data)
    if type(data.get('enabled')) is not bool or type(data.get('autoSave')) is not bool:
        raise DataError('启用状态必须是布尔值。')
    if not _integer(data.get('cacheEpoch')) or data.get('provider') not in PROVIDERS:
        raise DataError('配置状态无效。')
    profiles = data.get('providers')
    if not isinstance(profiles, dict) or set(profiles) != set(PROVIDERS):
        raise DataError('提供商配置不完整。')
    for profile in profiles.values():
        if not isinstance(profile, dict):
            raise DataError('提供商配置无效。')
        validate_url(profile.get('baseUrl'))
        for field, maximum in (('model', 200), ('apiKey', 4096)):
            value = profile.get(field)
            if not isinstance(value, str) or _units(value) > maximum or any(ord(c) < 32 for c in value):
                raise DataError('模型或密钥字段无效。')
    limits = data.get('limits')
    if not isinstance(limits, dict) or set(limits) != set(LIMIT_BOUNDS):
        raise DataError('请求限制配置不完整。')
    for name, bounds in LIMIT_BOUNDS.items():
        if not _integer(limits[name], *bounds):
            raise DataError('请求限制超出安全范围。')
    if data['enabled']:
        current = profiles[data['provider']]
        if not all(current.get(name, '').strip() for name in ('baseUrl', 'model', 'apiKey')):
            raise DataError('开启 AI 前请填写当前提供商的地址、模型和密钥。')
    return data


def _text(value, maximum=2000):
    return isinstance(value, str) and bool(value.strip()) and _units(value) <= maximum and '\x00' not in value


def validate_dictionary(data):
    _header(data)
    entries, tombstones = data.get('entries'), data.get('tombstones')
    if (not isinstance(entries, dict) or not isinstance(tombstones, dict)
            or len(entries) > 10000 or len(tombstones) > 10000):
        raise DataError('个人词典格式无效；原文件已保留。')
    for source, item in entries.items():
        if (not _text(source, 500) or source in ('__proto__', 'constructor', 'prototype') or source != source.strip() or not isinstance(item, dict)
                or not _text(item.get('translation')) or item.get('source') not in ('manual', 'ai')
                or item.get('context') != 'ui' or not isinstance(item.get('updatedAt'), str)):
            raise DataError('个人词典条目无效；原文件已保留。')
    for source, revision in tombstones.items():
        if not _text(source, 500) or source != source.strip() or source in ('__proto__', 'constructor', 'prototype') or not _integer(revision, 0, data['revision']):
            raise DataError('个人词典删除记录无效；原文件已保留。')
    if set(entries).intersection(tombstones):
        raise DataError('个人词典存在冲突；原文件已保留。')
    return data


def _regular(path, directory=False):
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) &
            getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024)
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))):
        raise DataError('拒绝使用链接或非预期类型的用户数据文件。')


class UserStore:
    def __init__(self, directory=None, lock_timeout=2.0):
        self.directory = Path(directory) if directory is not None else user_data_dir()
        self.lock_timeout = lock_timeout

    def _prepare(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        _regular(self.directory, directory=True)
        if os.name != 'nt':
            os.chmod(self.directory, 0o700)

    def _read(self, name, default, validator):
        path = self.directory / name
        if self.directory.exists() or self.directory.is_symlink():
            _regular(self.directory, directory=True)
        if not path.exists() and not path.is_symlink():
            return default()
        _regular(self.directory, directory=True)
        _regular(path)
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                raise DataError('用户数据文件过大；原文件已保留。')
            before = path.lstat()
            fd = os.open(str(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            with os.fdopen(fd, 'rb') as stream:
                actual = os.fstat(stream.fileno())
                if (not stat.S_ISREG(actual.st_mode) or actual.st_ino != before.st_ino
                        or actual.st_dev != before.st_dev or actual.st_size > MAX_FILE_BYTES):
                    raise DataError('用户数据在读取期间发生变化，未继续读取。')
                raw = stream.read(MAX_FILE_BYTES + 1)
                if len(raw) > MAX_FILE_BYTES:
                    raise DataError('用户数据超过容量上限。')
                data = json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeError):
            raise DataError('无法解析用户数据；原文件已保留。') from None
        return validator(data)

    def read_config(self):
        return self._read('config.json', default_config, validate_config)

    def read_dictionary(self):
        return self._read('personal-dictionary.json', default_dictionary, validate_dictionary)

    @contextmanager
    def locked(self):
        self._prepare()
        lock = self.directory / '.translation.lock'
        deadline = time.monotonic() + self.lock_timeout
        while True:
            try:
                lock.mkdir(mode=0o700)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise ConflictError('用户数据正在使用或遗留锁存在；请关闭相关程序并核查锁，不会强行覆盖。') from None
                time.sleep(0.025)
        try:
            # Diagnostics only, no credential content and never used to steal locks.
            (lock / 'owner.json').write_text(json.dumps({'pid': os.getpid()}), encoding='utf-8')
            yield
        finally:
            owner = lock / 'owner.json'
            if owner.exists():
                owner.unlink()
            lock.rmdir()

    def _write(self, name, data):
        path = self.directory / name
        if path.exists() or path.is_symlink():
            _regular(path)
        encoded = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        if len(encoded) > MAX_FILE_BYTES:
            raise DataError('用户数据超过容量上限，未保存。')
        fd, temporary = tempfile.mkstemp(prefix='.' + name + '.', suffix='.tmp', dir=str(self.directory))
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            if os.name != 'nt':
                directory_fd = os.open(str(self.directory), os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def save_config(self, data, expected_revision=None):
        candidate = validate_config(copy.deepcopy(data))
        with self.locked():
            current = self.read_config()
            if expected_revision is not None and current['revision'] != expected_revision:
                raise ConflictError('配置已被其他程序修改，请重新加载后再保存。')
            candidate['revision'] = current['revision'] + 1
            validate_config(candidate)
            self._write('config.json', candidate)
        return candidate

    def clear_cache(self):
        with self.locked():
            current = self.read_config()
            current['cacheEpoch'] += 1
            current['revision'] += 1
            validate_config(current)
            self._write('config.json', current)
        return current

    def set_entry(self, source, translation, expected_revision=None, origin='manual'):
        source = source.strip()
        if origin not in ('manual', 'ai') or source in ('__proto__', 'constructor', 'prototype') or not _text(source, 500) or not _text(translation):
            raise DataError('原文和译文不能为空或超过长度限制。')
        with self.locked():
            data = self.read_dictionary()
            if expected_revision is not None and data['revision'] != expected_revision:
                raise ConflictError('词典已变化，请重新加载后重试。')
            if origin == 'ai':
                if expected_revision is None:
                    raise ConflictError('自动保存需要原始词典版本。')
                existing = data['entries'].get(source)
                if source in data['tombstones'] or (existing and existing['source'] == 'manual'):
                    return data
            data['entries'][source] = dict(translation=translation.strip(), source=origin,
                updatedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(), context='ui')
            data['tombstones'].pop(source, None)
            data['revision'] += 1
            validate_dictionary(data)
            self._write('personal-dictionary.json', data)
        return data

    def delete_entry(self, source, expected_revision=None):
        source = source.strip()
        if not _text(source, 500) or source in ('__proto__', 'constructor', 'prototype'):
            raise DataError('原文无效。')
        with self.locked():
            data = self.read_dictionary()
            if expected_revision is not None and data['revision'] != expected_revision:
                raise ConflictError('词典已变化，请重新加载后重试。')
            data['revision'] += 1
            data['entries'].pop(source, None)
            data['tombstones'][source] = data['revision']
            validate_dictionary(data)
            self._write('personal-dictionary.json', data)
        return data
