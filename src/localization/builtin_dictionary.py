"""Read the bundled, versioned static translation catalog without executing JS.

``load_builtin_catalog()`` returns all four data groups; dictionary managers can
use ``load_builtin_dictionary()`` for the exact-match DOM entries alone. Each
call returns fresh data. The default resource path follows the source/frozen
layout, never the current working directory or the user's settings directory.

Extraction retained JavaScript's last-definition-wins semantics: the original
683 dictionary definitions contain 7 repeated keys and produce 676 entries.
The original values, counts and hashes are recorded in
``tests/fixtures/builtin-baseline.json``. New catalog JSON rejects duplicate keys
so a future edit cannot silently shadow a translation.
"""
import json
from pathlib import Path

from translation_integration import resource_root


BUILTIN_FILENAME = 'builtin-dictionary.json'
MAPPING_GROUPS = ('dictionary', 'coreWords', 'menuTranslationMap')
CATALOG_FIELDS = {'schemaVersion', *MAPPING_GROUPS, 'textPrefixRules'}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('内置词典 JSON 含重复键：' + key)
        result[key] = value
    return result


def load_builtin_catalog(path=None):
    """Return schema 1 static data, or raise ValueError/OSError without fallback.

    ``path`` explicitly selects an alternate catalog for tooling/tests. When
    omitted, the catalog comes from the bundled ``localization_runtime`` folder.
    This function does not read or write personal dictionaries or configuration.
    """
    source = Path(path) if path is not None else resource_root() / BUILTIN_FILENAME
    data = json.loads(source.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
    if not isinstance(data, dict) or set(data) != CATALOG_FIELDS:
        raise ValueError('内置词典数据字段不完整或包含未知字段')
    if type(data['schemaVersion']) is not int or data['schemaVersion'] != 1:
        raise ValueError('不支持的内置词典 schemaVersion')
    for group in MAPPING_GROUPS:
        entries = data[group]
        if not isinstance(entries, dict) or not entries:
            raise ValueError('内置词典映射为空或格式错误：' + group)
        if any(not isinstance(key, str) or not key or
               not isinstance(value, str) or not value for key, value in entries.items()):
            raise ValueError('内置词典必须使用非空原文和译文字符串：' + group)
    rules = data['textPrefixRules']
    if not isinstance(rules, list) or not rules:
        raise ValueError('内置前缀规则为空或格式错误')
    for pair in rules:
        if (not isinstance(pair, list) or len(pair) != 2 or
                any(not isinstance(value, str) or not value for value in pair)):
            raise ValueError('内置前缀规则必须为有序的原文／译文字符串对')
    return data


def load_builtin_dictionary(path=None):
    """Return a fresh ``{source: translation}`` mapping for the exact DOM terms."""
    return load_builtin_catalog(path)['dictionary']
