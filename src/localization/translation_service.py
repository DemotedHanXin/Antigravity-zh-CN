"""Headless dictionary/review operations shared by CLI and future manager UI.

Responses never contain provider configuration or credentials. Importing this
module does not read user data, migrate files, open a GUI or contact a provider.
"""
from builtin_dictionary import load_builtin_dictionary
from translation_config import ConflictError, DataError, UserStore


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

    def execute(self, action, source=None, translation=None, revision=None, query=''):
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
