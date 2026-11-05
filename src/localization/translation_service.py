"""Headless dictionary/review operations shared by CLI and future manager UI.

Responses never contain provider configuration or credentials. Importing this
module does not read user data, migrate files, open a GUI or contact a provider.
"""
import datetime
import json
import os
from pathlib import Path
import tempfile

from builtin_dictionary import load_builtin_dictionary
from translation_config import (ConflictError, DataError, UserStore, MAX_FILE_BYTES,
                                CANDIDATES_FILE, _source, _text, _trim, _bump,
                                _regular, validate_dictionary, validate_candidates)


class DictionaryService:
    def __init__(self, store=None, builtin=None):
        self.store = store if store is not None else UserStore()
        self._builtin = builtin

    def _defaults(self):
        if self._builtin is None:
            self._builtin = load_builtin_dictionary()
        return self._builtin

    @staticmethod
    def _versions(state):
        return {'dictionaryRevision': state['dictionary']['revision'],
                'candidatesRevision': state['candidates']['revision']}

    def list_entries(self, query=''):
        if not isinstance(query, str):
            raise DataError('查询条件必须为文本。')
        state = self.store.read_state()
        defaults = self._defaults()
        personal = state['dictionary']['entries']
        query = query.casefold()
        entries = []
        for source in sorted(set(defaults) | set(personal)):
            item = personal.get(source)
            translation = item['translation'] if item is not None else defaults[source]
            if query and query not in source.casefold() and query not in translation.casefold():
                continue
            entries.append({'original': source, 'translation': translation,
                            'source': item['source'] if item is not None else 'builtin',
                            'defaultTranslation': defaults.get(source),
                            'hasOverride': item is not None})
        return dict(self._versions(state), entries=entries)

    def pending(self):
        state = self.store.read_state()
        candidates = state['candidates']
        return dict(self._versions(state),
                    entries=[dict(item, original=source)
                             for source, item in sorted(candidates['entries'].items())],
                    rejected=[dict(item, original=source)
                              for source, item in sorted(candidates['rejected'].items())])

    def import_dictionary(self, path, revision):
        if type(revision) is not int or revision < 0:
            raise ConflictError('请先重新加载并提供当前版本号。')
        path = Path(path)
        _regular(path)
        with path.open('rb') as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise DataError('导入文件超过 4 MiB。')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise DataError('导入文件包含重复键。')
                result[key] = value
            return result
        try:
            value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique)
        except (UnicodeError, ValueError):
            raise DataError('导入文件不是有效的词典 JSON。') from None
        if (not isinstance(value, dict) or set(value) != {'schemaVersion', 'kind', 'entries'}
                or type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
                or value['kind'] != 'dragongirl-dictionary'
                or not isinstance(value['entries'], dict) or len(value['entries']) > 10000):
            raise DataError('请选择由管理器导出的词典文件。')
        entries = value['entries']
        if any(not _source(source) or not _text(target) for source, target in entries.items()):
            raise DataError('导入词条的原文或译文无效。')
        with self.store.locked():
            state = self.store._read_state_locked(self.store._now())
            dictionary, candidates = state['dictionary'], state['candidates']
            if dictionary['revision'] != revision:
                raise ConflictError('词典已变化，请重新加载后重试。')
            if entries:
                timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
                for source, target in entries.items():
                    dictionary['entries'][source] = dict(translation=_trim(target), source='manual',
                                                         context='ui', updatedAt=timestamp)
                    dictionary['tombstones'].pop(source, None)
                    self.store._invalidate(candidates, source)
                dictionary['revision'] = _bump(dictionary['revision'])
                candidates['revision'] = _bump(candidates['revision'])
                validate_dictionary(dictionary)
                validate_candidates(candidates)
                self.store._commit({'personal-dictionary.json': dictionary, CANDIDATES_FILE: candidates})
            return dict(self._versions(state), imported=len(entries))

    def export_dictionary(self, path):
        target = Path(path).absolute()
        # A save dialog must never turn dictionary export into user-store damage.
        resolved = target.resolve()
        data_root = self.store.directory.resolve()
        if resolved == data_root or data_root in resolved.parents:
            raise DataError('词典导出位置必须在用户数据目录之外。')
        if target.exists() or target.is_symlink():
            _regular(target)
        _regular(target.parent, directory=True)
        state = self.store.read_state()
        value = dict(schemaVersion=1, kind='dragongirl-dictionary',
                     entries={source: item['translation'] for source, item in
                              sorted(state['dictionary']['entries'].items())})
        encoded = json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')
        if len(encoded) > MAX_FILE_BYTES:
            raise DataError('导出词典超过 4 MiB。')
        descriptor, temporary = tempfile.mkstemp(prefix='.dictionary-export-', dir=str(target.parent))
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            if target.exists() or target.is_symlink():
                _regular(target)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return dict(self._versions(state), exported=len(value['entries']))

    def execute(self, action, source=None, translation=None, revision=None, query='', path=None):
        """Return structured status; CLI and GUI need not parse console prose."""
        try:
            if action in ('set', 'restore-default', 'accept', 'reject', 'unblock'):
                if not isinstance(source, str) or not source.strip():
                    raise DataError('原文不能为空。')
                if type(revision) is not int or revision < 0:
                    raise ConflictError('请先重新加载并提供当前版本号。')
            if action == 'set' and not isinstance(translation, str):
                raise DataError('译文必须为文本。')
            if action == 'accept' and translation is not None and not isinstance(translation, str):
                raise DataError('译文必须为文本。')
            if action == 'list':
                result = self.list_entries(query)
            elif action == 'pending':
                result = self.pending()
            elif action in ('set', 'restore-default'):
                if revision is None:
                    raise ConflictError('请先查看词典并提供当前版本号。')
                if action == 'set':
                    dictionary = self.store.set_entry(source, translation, expected_revision=revision)
                else:
                    dictionary = self.store.delete_entry(source, expected_revision=revision)
                result = {'dictionaryRevision': dictionary['revision']}
            elif action in ('accept', 'reject', 'unblock'):
                if revision is None:
                    raise ConflictError('请先查看待确认译文并提供当前版本号。')
                if action == 'accept':
                    state = self.store.accept_candidate(source, revision, translation=translation)
                elif action == 'reject':
                    state = self.store.reject_candidate(source, revision)
                else:
                    state = self.store.unblock(source, revision)
                result = self._versions(state)
            elif action == 'cleanup':
                result = self._versions(self.store.cleanup())
            elif action == 'import-dictionary':
                result = self.import_dictionary(path, revision)
            elif action == 'export-dictionary':
                result = self.export_dictionary(path)
            else:
                raise DataError('不支持的词典操作。')
            return dict(result, ok=True)
        except ConflictError as error:
            return {'ok': False, 'code': 'conflict', 'message': str(error)}
        except DataError as error:
            return {'ok': False, 'code': 'invalid_data', 'message': str(error)}
        except ValueError:
            return {'ok': False, 'code': 'invalid_catalog',
                    'message': '内置词典资源无效，请恢复完整的程序资源。'}
        except OSError:
            return {'ok': False, 'code': 'storage_unavailable',
                    'message': '文件操作失败，请检查权限、空间与锁状态。'}
        except TypeError:
            return {'ok': False, 'code': 'invalid_arguments', 'message': '操作参数无效。'}
