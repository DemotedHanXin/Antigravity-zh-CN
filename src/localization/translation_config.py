# coding: utf-8
"""Versioned DragonGirl user data. No networking, imports, or install-tree writes.

Lock contract shared with localization_runtime/storage.cjs: exclusive mkdir of
.translation.lock; owner.json is diagnostic only. Never steal a stale lock.
"""
import copy
import base64
import datetime
import json
import ipaddress
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from urllib.parse import urlsplit
from credential_protection import CredentialError, WindowsProtector

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
MAX_JOURNAL_BYTES = 16 * 1024 * 1024
CANDIDATE_TTL_MS = 7 * 24 * 60 * 60 * 1000
MAX_TIMESTAMP_MS = 253402300799999
CANDIDATES_FILE = "pending-translations/state.json"
JOURNAL_FILE = ".translation-journal.json"
STATE_FILES = ("config.json", "personal-dictionary.json", CANDIDATES_FILE)
_MISSING = object()
# Union of ECMAScript trim and Python whitespace, explicitly shared with Node.
_EDGE_WHITESPACE = ('\u0009\u000a\u000b\u000c\u000d\u001c\u001d\u001e\u001f\u0020'
                    '\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006'
                    '\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff')


def _trim(value):
    return value.strip(_EDGE_WHITESPACE)


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
    return dict(schemaVersion=2, revision=0, enabled=False, autoSave=False,
                cacheEpoch=0, provider='openai',
                providers={name: dict(baseUrl=DEFAULT_URLS[name], model='', apiKey='')
                           for name in PROVIDERS}, limits=dict(DEFAULT_LIMITS))


def default_dictionary():
    return dict(schemaVersion=2, revision=0, entries={}, tombstones={})


def default_candidates():
    return dict(schemaVersion=2, revision=0, entries={}, rejected={}, epochs={})


def _integer(value, low=0, high=2**53-1):
    return type(value) is int and low <= value <= high


def _header(data, version=2):
    if not isinstance(data, dict) or data.get('schemaVersion') != version or type(data.get('schemaVersion')) is not int:
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


def validate_config(data, version=2):
    _header(data, version)
    if type(data.get('enabled')) is not bool or type(data.get('autoSave')) is not bool:
        raise DataError('启用状态必须是布尔值。')
    if version == 2 and data['autoSave'] is not False:
        raise DataError('AI 译文只能进入待确认列表，旧自动保存开关已停用。')
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
        if not all(_trim(current.get(name, '')) for name in ('baseUrl', 'model', 'apiKey')):
            raise DataError('开启 AI 前请填写当前提供商的地址、模型和密钥。')
    return data


def _text(value, maximum=2000):
    return isinstance(value, str) and bool(_trim(value)) and _units(value) <= maximum and '\x00' not in value


def validate_dictionary(data, version=2):
    _header(data, version)
    origins = ('manual', 'ai') if version == 1 else ('manual', 'accepted', 'legacy-ai')
    entries, tombstones = data.get('entries'), data.get('tombstones')
    if (not isinstance(entries, dict) or not isinstance(tombstones, dict)
            or len(entries) > 10000 or len(tombstones) > 10000):
        raise DataError('个人词典格式无效；原文件已保留。')
    for source, item in entries.items():
        if (not _source(source) or not isinstance(item, dict)
                or not _text(item.get('translation')) or item.get('source') not in origins
                or item.get('context') != 'ui' or not isinstance(item.get('updatedAt'), str)):
            raise DataError('个人词典条目无效；原文件已保留。')
    for source, revision in tombstones.items():
        if not _source(source) or not _integer(revision, 0, data['revision']):
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


def _source(value):
    return (_text(value, 500) and value == _trim(value)
            and value not in ('__proto__', 'constructor', 'prototype'))


def _finite_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise DataError('用户数据包含无效数值；原文件已保留。')
    if isinstance(value, dict):
        for item in value.values():
            _finite_json(item)
    elif isinstance(value, list):
        for item in value:
            _finite_json(item)
    return value


def validate_candidates(data):
    _header(data)
    for field in ('entries', 'rejected', 'epochs'):
        if not isinstance(data.get(field), dict) or len(data[field]) > 10000:
            raise DataError('待确认译文格式无效；原文件已保留。')
    if len(set(data['entries']) | set(data['rejected']) | set(data['epochs'])) > 10000:
        raise DataError('待确认译文跟踪的原文数量已达上限。')
    if set(data['entries']).intersection(data['rejected']):
        raise DataError('待确认译文与拒绝记录冲突。')
    for source, item in data['entries'].items():
        if (not _source(source) or not isinstance(item, dict)
                or set(item) != {'translation', 'createdAt', 'expiresAt', 'context'}
                or not _text(item.get('translation')) or item.get('context') != 'ui'
                or not _integer(item.get('createdAt'), 0, MAX_TIMESTAMP_MS - CANDIDATE_TTL_MS)
                or not _integer(item.get('expiresAt'), 0, MAX_TIMESTAMP_MS)
                or item['expiresAt'] - item['createdAt'] != CANDIDATE_TTL_MS):
            raise DataError('待确认译文条目无效。')
    for source, item in data['rejected'].items():
        if (not _source(source) or not isinstance(item, dict)
                or set(item) != {'rejectedAt'} or not _integer(item['rejectedAt'], 0, MAX_TIMESTAMP_MS)):
            raise DataError('拒绝记录无效。')
    for source, epoch in data['epochs'].items():
        if not _source(source) or not _integer(epoch):
            raise DataError('译文请求代次无效。')
    return data


def _bump(value):
    if not _integer(value, 0, 2**53 - 2):
        raise DataError('数据版本号已达上限。')
    return value + 1


class UserStore:
    def __init__(self, directory=None, lock_timeout=2.0, clock=None, protector=None):
        self.directory = Path(directory) if directory is not None else user_data_dir()
        self.lock_timeout = lock_timeout
        self.clock = clock or (lambda: time.time_ns() // 1_000_000)
        self.protector = protector if protector is not None else WindowsProtector()

    def _open_config(self, value, decrypt=True):
        """Disk v3 is separate from the v2 in-memory API consumed by callers."""
        if not isinstance(value, dict) or value.get('schemaVersion') != 3:
            return validate_config(value)
        _header(value, version=3)
        result = copy.deepcopy(value)
        result['schemaVersion'] = 2
        if result.pop('credentialProtection', None) != 'windows-dpapi-v1':
            raise DataError('密钥保护格式无效；原文件已保留。')
        if not isinstance(result.get('providers'), dict) or set(result['providers']) != set(PROVIDERS):
            raise DataError('提供商配置不完整。')
        for profile in result['providers'].values():
            if not isinstance(profile, dict) or set(profile) != {'baseUrl', 'model', 'apiKeyProtected'}:
                raise DataError('密钥保护格式无效；原文件已保留。')
            protected = profile.pop('apiKeyProtected')
            if not isinstance(protected, str) or len(protected) > 32768:
                raise DataError('密钥保护内容无效；原文件已保留。')
            try:
                if base64.b64encode(base64.b64decode(protected, validate=True)).decode('ascii') != protected:
                    raise ValueError()
            except ValueError:
                raise DataError('密钥保护内容无效；原文件已保留。') from None
            try:
                profile['apiKey'] = self.protector.unprotect(protected) if protected and decrypt else ('protected' if protected else '')
            except CredentialError:
                raise DataError('无法使用当前 Windows 用户解锁密钥；原文件已保留。') from None
        return validate_config(result)

    def _seal_config(self, value):
        if value.get('schemaVersion') == 3:
            self._open_config(value, decrypt=False)
            return value
        validate_config(value)
        if not any(profile['apiKey'] for profile in value['providers'].values()):
            return value
        result = {name: copy.deepcopy(value[name]) for name in default_config()}
        result.update(schemaVersion=3, credentialProtection='windows-dpapi-v1')
        for name, profile in value['providers'].items():
            try:
                protected = self.protector.protect(profile['apiKey']) if profile['apiKey'] else ''
            except CredentialError:
                raise DataError('无法使用当前 Windows 用户保护密钥；未写入明文。') from None
            result['providers'][name] = dict(baseUrl=profile['baseUrl'], model=profile['model'], apiKeyProtected=protected)
        self._open_config(result, decrypt=False)
        return result

    def _seal_images(self, images):
        result = copy.deepcopy(images)
        if 'config.json' in result:
            result['config.json'] = self._seal_config(result['config.json'])
        return result

    def _now(self, value=None):
        value = self.clock() if value is None else value
        if not _integer(value, 0, MAX_TIMESTAMP_MS - CANDIDATE_TTL_MS):
            raise DataError('当前时间无效。')
        return value

    def _prepare(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        _regular(self.directory, directory=True)
        if os.name != 'nt':
            os.chmod(self.directory, 0o700)

    def _parent(self, name, create=False):
        if name not in STATE_FILES + (JOURNAL_FILE,):
            raise DataError('不支持的用户数据路径。')
        _regular(self.directory, directory=True)
        parent = self.directory
        if name == CANDIDATES_FILE:
            parent /= 'pending-translations'
            if create:
                parent.mkdir(mode=0o700, exist_ok=True)
            if parent.exists() or parent.is_symlink():
                _regular(parent, directory=True)
        return parent

    def _read(self, name, default, validator, maximum=MAX_FILE_BYTES):
        path = self.directory / name
        self._parent(name)
        if not path.exists() and not path.is_symlink():
            return default()
        _regular(path)
        try:
            before = path.lstat()
            if before.st_size > maximum:
                raise DataError('用户数据文件过大；原文件已保留。')
            fd = os.open(str(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            with os.fdopen(fd, 'rb') as stream:
                actual = os.fstat(stream.fileno())
                if (not stat.S_ISREG(actual.st_mode) or actual.st_ino != before.st_ino
                        or actual.st_dev != before.st_dev or actual.st_size > maximum):
                    raise DataError('用户数据在读取期间发生变化，未继续读取。')
                raw = stream.read(maximum + 1)
                if len(raw) > maximum:
                    raise DataError('用户数据超过容量上限。')
                data = _finite_json(json.loads(raw.decode('utf-8')))
        except (ValueError, UnicodeError, RecursionError):
            raise DataError('无法解析用户数据；原文件已保留。') from None
        return validator(data)

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
            (lock / 'owner.json').write_text(json.dumps({'pid': os.getpid()}), encoding='utf-8')
            yield
        finally:
            owner = lock / 'owner.json'
            if owner.exists():
                owner.unlink()
            lock.rmdir()

    @staticmethod
    def _encoded(data, maximum=MAX_FILE_BYTES):
        try:
            encoded = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
        except (ValueError, UnicodeError, TypeError, RecursionError):
            raise DataError('用户数据无法安全编码；原文件已保留。') from None
        if len(encoded) > maximum:
            raise DataError('用户数据超过容量上限，未保存。')
        return encoded

    def _write(self, name, data, maximum=MAX_FILE_BYTES):
        parent = self._parent(name, create=True)
        path = self.directory / name
        if path.exists() or path.is_symlink():
            _regular(path)
        encoded = self._encoded(data, maximum)
        fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=str(parent))
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            self._sync_directory(parent)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _sync_directory(directory):
        if os.name != 'nt':
            descriptor = os.open(str(directory), os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def _validate_images(self, images):
        if not isinstance(images, dict) or not images or not set(images).issubset(STATE_FILES):
            raise DataError('恢复事务包含不支持的路径。')
        validators = dict(zip(STATE_FILES, (lambda value: self._open_config(value, decrypt=False), validate_dictionary, validate_candidates)))
        for name, value in images.items():
            validators[name](value)
            self._encoded(value)
            self._parent(name)
            path = self.directory / name
            if path.exists() or path.is_symlink():
                _regular(path)

    def _apply_images(self, images):
        for name in STATE_FILES:
            if name in images:
                self._write(name, images[name])
        (self.directory / JOURNAL_FILE).unlink()
        self._sync_directory(self.directory)

    def _recover(self):
        journal = self._read(JOURNAL_FILE, lambda: _MISSING, lambda value: value, MAX_JOURNAL_BYTES)
        if journal is _MISSING:
            return
        if (not isinstance(journal, dict) or set(journal) != {'schemaVersion', 'kind', 'id', 'files'}
                or type(journal.get('schemaVersion')) is not int or journal['schemaVersion'] != 1
                or journal.get('kind') != 'dragongirl-state-transaction'
                or not isinstance(journal.get('id'), str) or len(journal['id']) != 32
                or any(char not in '0123456789abcdef' for char in journal['id'])):
            raise DataError('恢复事务无效；文件已保留。')
        self._validate_images(journal['files'])
        if journal['files'].get('config.json', {}).get('schemaVersion') == 3:
            self._open_config(journal['files']['config.json'])
        protected = self._seal_images(journal['files'])
        if protected != journal['files']:
            journal['files'] = protected
            self._write(JOURNAL_FILE, journal, MAX_JOURNAL_BYTES)
        self._apply_images(journal['files'])

    def _commit(self, images):
        if not images:
            return
        images = self._seal_images(images)
        self._validate_images(images)
        journal = dict(schemaVersion=1, kind='dragongirl-state-transaction', id=uuid.uuid4().hex, files=images)
        self._encoded(journal, MAX_JOURNAL_BYTES)
        self._write(JOURNAL_FILE, journal, MAX_JOURNAL_BYTES)
        # The durable journal is the commit point. Failures after this point
        # leave it intact for deterministic roll-forward under the same lock.
        self._apply_images(images)

    @staticmethod
    def _invalidate(candidates, source):
        candidates['epochs'][source] = _bump(candidates['epochs'].get(source, 0))
        candidates['entries'].pop(source, None)

    def _read_state_locked(self, now):
        self._recover()
        config = self._read('config.json', default_config, lambda value: value)
        was_protected = isinstance(config, dict) and config.get('schemaVersion') == 3
        if was_protected:
            config = self._open_config(config)
        dictionary = self._read('personal-dictionary.json', default_dictionary, lambda value: value)
        candidates = self._read(CANDIDATES_FILE, default_candidates, validate_candidates)
        images = {}
        if isinstance(config, dict) and config.get('schemaVersion') == 1:
            validate_config(config, version=1)
            config['schemaVersion'] = 2
            config['autoSave'] = False
            config['revision'] = _bump(config['revision'])
            config['cacheEpoch'] = _bump(config['cacheEpoch'])
            images['config.json'] = config
        validate_config(config)
        if not was_protected and any(profile['apiKey'] for profile in config['providers'].values()):
            if 'config.json' not in images:
                config['revision'] = _bump(config['revision'])
                config['cacheEpoch'] = _bump(config['cacheEpoch'])
            images['config.json'] = config
        if isinstance(dictionary, dict) and dictionary.get('schemaVersion') == 1:
            validate_dictionary(dictionary, version=1)
            dictionary['schemaVersion'] = 2
            dictionary['revision'] = _bump(dictionary['revision'])
            for item in dictionary['entries'].values():
                if item['source'] == 'ai':
                    item['source'] = 'legacy-ai'
            images['personal-dictionary.json'] = dictionary
        validate_dictionary(dictionary)
        expired = [source for source, item in candidates['entries'].items() if now >= item['expiresAt']]
        for source in expired:
            self._invalidate(candidates, source)
        if expired:
            candidates['revision'] = _bump(candidates['revision'])
            images[CANDIDATES_FILE] = candidates
        if images and CANDIDATES_FILE not in images:
            # Migration establishes the independent candidate store as part of
            # the same transaction, without moving or expiring legacy entries.
            images[CANDIDATES_FILE] = candidates
        validate_candidates(candidates)
        self._commit(images)
        return dict(config=config, dictionary=dictionary, candidates=candidates)

    def read_state(self, now_ms=None):
        self._now(now_ms)
        if not self.directory.exists() and not self.directory.is_symlink():
            return dict(config=default_config(), dictionary=default_dictionary(), candidates=default_candidates())
        with self.locked():
            return self._read_state_locked(self._now(now_ms))

    def read_config(self):
        return self.read_state()['config']

    def read_dictionary(self):
        return self.read_state()['dictionary']

    def read_candidates(self, now_ms=None):
        return self.read_state(now_ms)['candidates']

    def save_config(self, data, expected_revision=None):
        candidate = validate_config(copy.deepcopy(data))
        with self.locked():
            current = self._read_state_locked(self._now())['config']
            if expected_revision is not None and current['revision'] != expected_revision:
                raise ConflictError('配置已被其他程序修改，请重新加载后再保存。')
            candidate['revision'] = _bump(current['revision'])
            self._commit({'config.json': candidate})
        return candidate

    def clear_cache(self):
        with self.locked():
            current = self._read_state_locked(self._now())['config']
            current['cacheEpoch'] = _bump(current['cacheEpoch'])
            current['revision'] = _bump(current['revision'])
            self._commit({'config.json': current})
        return current

    def set_entry(self, source, translation, expected_revision=None, origin='manual'):
        source = _trim(source) if isinstance(source, str) else source
        if origin != 'manual' or not _source(source) or not _text(translation):
            raise DataError('只允许手工编辑正式词条；AI 译文须先进入待确认列表。')
        with self.locked():
            state = self._read_state_locked(self._now())
            data, candidates = state['dictionary'], state['candidates']
            if expected_revision is not None and data['revision'] != expected_revision:
                raise ConflictError('词典已变化，请重新加载后重试。')
            data['entries'][source] = dict(translation=_trim(translation), source='manual',
                updatedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(), context='ui')
            data['tombstones'].pop(source, None)
            data['revision'] = _bump(data['revision'])
            self._invalidate(candidates, source)
            candidates['revision'] = _bump(candidates['revision'])
            self._commit({'personal-dictionary.json': data, CANDIDATES_FILE: candidates})
            return data

    def delete_entry(self, source, expected_revision=None):
        source = _trim(source) if isinstance(source, str) else source
        if not _source(source):
            raise DataError('原文无效。')
        with self.locked():
            state = self._read_state_locked(self._now())
            data, candidates = state['dictionary'], state['candidates']
            if expected_revision is not None and data['revision'] != expected_revision:
                raise ConflictError('词典已变化，请重新加载后重试。')
            data['revision'] = _bump(data['revision'])
            data['entries'].pop(source, None)
            data['tombstones'][source] = data['revision']
            self._invalidate(candidates, source)
            candidates['revision'] = _bump(candidates['revision'])
            self._commit({'personal-dictionary.json': data, CANDIDATES_FILE: candidates})
            return data

    def _review(self, source, expected_revision, action, translation, now_ms):
        source = _trim(source) if isinstance(source, str) else source
        if not _source(source) or not _integer(expected_revision):
            raise DataError('原文或待确认列表版本无效。')
        self._now(now_ms)
        with self.locked():
            now = self._now(now_ms)
            state = self._read_state_locked(now)
            # Reading/recovering the transaction may itself cross the deadline.
            # Decide acceptance using the live time at the decision point.
            now = self._now(now_ms)
            data, candidates = state['dictionary'], state['candidates']
            if candidates['revision'] != expected_revision:
                raise ConflictError('待确认列表已变化，请重新加载后重试。')
            images = {CANDIDATES_FILE: candidates}
            if action == 'accept':
                item = candidates['entries'].get(source)
                if item is None or now >= item['expiresAt'] or source in data['entries']:
                    raise ConflictError('候选已过期、移除或被正式词条替代。')
                value = item['translation'] if translation is None else translation
                if not _text(value):
                    raise DataError('译文无效。')
                data['entries'][source] = dict(translation=_trim(value), source='accepted',
                    updatedAt=datetime.datetime.fromtimestamp(now / 1000, datetime.timezone.utc).isoformat(), context='ui')
                data['tombstones'].pop(source, None)
                data['revision'] = _bump(data['revision'])
                images['personal-dictionary.json'] = data
            elif action == 'reject':
                candidates['rejected'][source] = {'rejectedAt': now}
            else:
                if source not in candidates['rejected']:
                    raise ConflictError('该文案没有拒绝记录。')
                candidates['rejected'].pop(source, None)
            self._invalidate(candidates, source)
            candidates['revision'] = _bump(candidates['revision'])
            self._commit(images)
            return state

    def accept_candidate(self, source, expected_candidates_revision, translation=None, now_ms=None):
        return self._review(source, expected_candidates_revision, 'accept', translation, now_ms)

    def reject_candidate(self, source, expected_candidates_revision, now_ms=None):
        return self._review(source, expected_candidates_revision, 'reject', None, now_ms)

    def unblock(self, source, expected_candidates_revision, now_ms=None):
        return self._review(source, expected_candidates_revision, 'unblock', None, now_ms)

    def cleanup(self, now_ms=None):
        return self.read_state(now_ms)
