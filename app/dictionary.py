"""Exact-text dictionary catalog and validated personal overrides.

The builtin JSON is a checked extraction of the CLI engine's literal maps.
Runtime rules remain read-only in the shared engine. No JavaScript is executed
to load, edit, import or export dictionary data.
"""
import copy
from datetime import datetime, timezone
import hashlib
from pathlib import Path

from .storage import atomic_write_json, data_directory, file_lock, parse_json, read_json, read_json_bytes

MAX_ENTRIES = 10000
MAX_TEXT = 8000
ENTRY_FIELDS = {'id', 'scope', 'source', 'target', 'enabled', 'category', 'note'}
SYSTEM_RULES = (
    {'name': '动态计数与提示', 'example': '99% left → 剩余 99%', 'note': '系统规则，只读；精确自定义词条优先。'},
    {'name': '链接与跨节点提示', 'example': '云资源说明、内联提示', 'note': '保留交互节点，不开放脚本或正则编辑。'},
    {'name': '原生托盘与更新弹窗', 'example': 'Show Antigravity → 显示 Antigravity', 'note': '依赖应用文件结构的系统规则，只读。'},
)


def entry_id(scope, source):
    return hashlib.sha256((scope + '\0' + source).encode('utf-8')).hexdigest()[:24]


def validate_document(data):
    if not isinstance(data, dict) or set(data) - {'schemaVersion', 'revision', 'entries'}:
        raise ValueError('词典只接受 schemaVersion、revision 和 entries 字段')
    if type(data.get('schemaVersion')) is not int or data['schemaVersion'] != 1:
        raise ValueError('不支持的词典 schemaVersion，当前为 1')
    revision = data.get('revision', 0)
    if type(revision) is not int or revision < 0:
        raise ValueError('词典 revision 必须是非负整数')
    entries = data.get('entries')
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise ValueError('词典 entries 必须是数组，且不超过 10000 条')
    checked, keys = [], set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - ENTRY_FIELDS:
            raise ValueError('词条含未知字段；不允许代码、正则或脚本字段')
        scope, source, target = entry.get('scope'), entry.get('source'), entry.get('target')
        if scope not in ('ui', 'menu'):
            raise ValueError('词条用途只支持 ui 或 menu')
        for label, text in (('原文', source), ('译文', target)):
            if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT or '\0' in text:
                raise ValueError(label + '必须是 1–8000 字符的非空文本，不能含 NUL')
            try:
                text.encode('utf-8')
            except UnicodeEncodeError as exc:
                raise ValueError(label + '包含无效 Unicode 字符') from exc
        if source != source.strip():
            raise ValueError('原文不能含首尾空白；匹配时会保留界面的首尾空白')
        enabled = entry.get('enabled', True)
        if type(enabled) is not bool:
            raise ValueError('enabled 必须是布尔值')
        key = (scope, source)
        if key in keys:
            raise ValueError('词典有重复的用途和原文：' + source)
        keys.add(key)
        identifier = entry_id(scope, source)
        if 'id' in entry and entry['id'] != identifier:
            raise ValueError('词条 id 与用途和原文不一致')
        result = dict(id=identifier, scope=scope, source=source, target=target, enabled=enabled)
        for field in ('category', 'note'):
            value = entry.get(field, '')
            if not isinstance(value, str) or len(value) > 1000 or '\0' in value:
                raise ValueError(field + '必须是最多 1000 字符的文本')
            try:
                value.encode('utf-8')
            except UnicodeEncodeError as exc:
                raise ValueError(field + '包含无效 Unicode 字符') from exc
            result[field] = value
        checked.append(result)
    return {'schemaVersion': 1, 'revision': revision, 'entries': checked}


def load_builtin():
    data = read_json(Path(__file__).parent / 'resources' / 'builtin-dictionary.json')
    return validate_document(data)['entries']


class DictionaryStore:
    def __init__(self, data_dir=None):
        self.path = Path(data_dir or data_directory()) / 'custom-dictionary.json'
        self._builtin = {(e['scope'], e['source']): e for e in load_builtin()}
        self._data = {'schemaVersion': 1, 'revision': 0, 'entries': []}
        self.error = ''
        self._loaded_bytes = None
        self._loaded_stat = None
        if self.path.exists():
            try:
                info = self.path.stat()
                self._loaded_stat = (info.st_size, info.st_mtime_ns, info.st_ino)
                self._loaded_bytes = read_json_bytes(self.path)
                self._data = validate_document(parse_json(self._loaded_bytes))
            except (OSError, ValueError, UnicodeError) as exc:
                self.error = '用户词典无法读取，原文件已保留；请使用有效 JSON 恢复：' + str(exc)

    @property
    def revision(self):
        return self._data['revision']

    def assert_writable(self):
        if self.error:
            raise ValueError(self.error)

    def entries(self):
        combined = {key: dict(value, origin='builtin') for key, value in self._builtin.items()}
        for entry in self._data['entries']:
            key = (entry['scope'], entry['source'])
            combined[key] = dict(entry, origin='override' if key in self._builtin else 'custom')
        return copy.deepcopy(sorted(combined.values(), key=lambda e: (e['scope'], e['source'].casefold())))

    def snapshot(self):
        self.assert_writable()
        return copy.deepcopy(self._data)

    def _save(self, entries):
        self.assert_writable()
        with file_lock(self.path.with_suffix('.lock')):
            current = read_json_bytes(self.path) if self.path.exists() else None
            if current != self._loaded_bytes:
                raise ValueError('用户词典已被另一个窗口或程序修改，请重新打开助手后再保存')
            updated = validate_document({'schemaVersion': 1, 'revision': self.revision + 1, 'entries': entries})
            written = atomic_write_json(self.path, updated)
            self._data = updated
            self._loaded_bytes = written

    def set_entry(self, scope, source, target, enabled=True):
        self.assert_writable()
        entry = validate_document({'schemaVersion': 1, 'entries': [dict(scope=scope, source=source, target=target, enabled=enabled)]})['entries'][0]
        existing = next((e for e in self._data['entries'] if (e['scope'], e['source']) == (scope, source)), None)
        if existing:
            entry.update({field: existing[field] for field in ('category', 'note')})
        entries = [e for e in self._data['entries'] if (e['scope'], e['source']) != (scope, source)]
        entries.append(entry)
        self._save(entries)

    def reset_entry(self, scope, source):
        self.assert_writable()
        self._save([e for e in self._data['entries'] if (e['scope'], e['source']) != (scope, source)])

    def preview_import(self, path):
        data = validate_document(read_json(path))
        existing = {(e['scope'], e['source']) for e in self._data['entries']}
        conflicts = [e for e in data['entries'] if (e['scope'], e['source']) in existing]
        return {'data': data, 'conflicts': conflicts, 'added': len(data['entries']) - len(conflicts)}

    def import_data(self, data, policy='keep'):
        self.assert_writable()
        if policy not in ('keep', 'overwrite'):
            raise ValueError('冲突策略必须为 keep 或 overwrite')
        incoming = validate_document(data)
        entries = {(e['scope'], e['source']): e for e in self._data['entries']}
        changed = 0
        for entry in incoming['entries']:
            key = (entry['scope'], entry['source'])
            if key not in entries or (policy == 'overwrite' and entries[key] != entry):
                entries[key] = entry
                changed += 1
        if changed:
            self._save(list(entries.values()))
        return changed

    def export(self, path):
        atomic_write_json(path, self.snapshot())

    def recover_from_import(self, path):
        """Explicit recovery only: preserve the unreadable file before replacement."""
        data = validate_document(read_json(path))
        if not self.error:
            return self.import_data(data, policy='overwrite')
        backup = self.path.with_name(self.path.name + '.corrupt-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        with file_lock(self.path.with_suffix('.lock')):
            if self._loaded_bytes is not None:
                unchanged = self.path.exists() and read_json_bytes(self.path) == self._loaded_bytes
            else:
                info = self.path.stat() if self.path.exists() else None
                unchanged = ((info.st_size, info.st_mtime_ns, info.st_ino) if info else None) == self._loaded_stat
            if not unchanged:
                raise ValueError('词典文件已被另一个窗口或程序修改，请重新打开助手后再恢复')
            if self.path.exists():
                self.path.rename(backup)
            try:
                written = atomic_write_json(self.path, data)
            except BaseException:
                if backup.exists() and not self.path.exists():
                    backup.rename(self.path)
                raise
            self._data = data
            self._loaded_bytes = written
            self.error = ''
        return len(data['entries'])
