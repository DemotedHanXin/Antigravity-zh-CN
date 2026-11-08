"""Small local JSON storage helpers; writes replace a complete validated file."""
import json
import os
from pathlib import Path
import tempfile
from contextlib import contextmanager


def data_directory():
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'AntigravityZhCN'


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('JSON 含重复字段：' + key)
        result[key] = value
    return result


def read_json_bytes(path, max_bytes=4 * 1024 * 1024):
    with Path(path).open('rb') as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError('JSON 文件超过允许的大小')
    return raw


def parse_json(raw):
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_object)


def read_json(path, max_bytes=4 * 1024 * 1024):
    return parse_json(read_json_bytes(path, max_bytes))


@contextmanager
def file_lock(path):
    """Hold an OS lock across check-and-replace, released even on process exit.

    The one-byte lock file remains so every process locks the same file object.
    It contains no dictionary data and is not a backup or a log.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b'\0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('另一个助手窗口正在保存词典，请稍后重试') from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def atomic_write_json(path, data):
    path = Path(path)
    encoded = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        return encoded
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_settings(data_dir=None):
    path = Path(data_dir or data_directory()) / 'settings.json'
    if not path.exists():
        return {}
    data = read_json(path, 128 * 1024)
    if not isinstance(data, dict):
        raise ValueError('设置文件必须是 JSON 对象；原文件已保留')
    return data


def save_settings(settings, data_dir=None):
    if not isinstance(settings, dict):
        raise ValueError('设置必须是 JSON 对象')
    atomic_write_json(Path(data_dir or data_directory()) / 'settings.json', settings)
