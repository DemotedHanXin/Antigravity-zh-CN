"""Fail-closed Electron bridge packaging; no application compatibility is assumed.

Only reviewed, bundled profiles can enable the bridge. Fingerprint reports are
not authorization profiles, and the CLI cannot enable an unreviewed profile.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys

from antigravity_common import _contained, _no_link

RUNTIME_FILES = ('main.cjs', 'providers.cjs', 'network.cjs', 'storage.cjs', 'bootstrap.cjs')
REGISTRY = 'compatibility.json'
DYNAMIC_BINDING = 'antigravity-local-hub-v1'
BINDING_FILES = {'dist/utils.js', 'dist/languageServer.js', 'dist/constants.js'}
HUB_ANCHOR = '    hubWindows.add(win);'
HUB_PRELOAD = "preload: path_1.default.join(__dirname, 'preload.js')"
HUB_HOOK = "    try { require('../.dragongirl/bootstrap.cjs').registerHubWindow(win, url, path_1.default.join(__dirname, 'preload.js')); } catch (_) {}"
UI_CONTEXTS = {'toolbar', 'settings', 'navigation', 'menu', 'button', 'label'}
UI_ATTRIBUTES = {'title', 'placeholder', 'aria-label'}


def resource_root():
    """Find repository resources or PyInstaller data, regardless of the cwd."""
    bundle = getattr(sys, '_MEIPASS', None)
    root = Path(bundle) if bundle else Path(__file__).resolve().parents[2]
    return root / 'localization_runtime'


def _read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def _validate_paths(paths):
    if not isinstance(paths, dict) or not paths:
        raise ValueError('兼容配置缺少文件指纹')
    for name, digest in paths.items():
        if not isinstance(name, str):
            raise ValueError('兼容配置路径无效')
        pure = PurePosixPath(name)
        if (pure.is_absolute() or '..' in pure.parts or '\\' in name or ':' in name
                or '\x00' in name or not name or pure.as_posix() != name
                or any(part.endswith((' ', '.')) for part in pure.parts)):
            raise ValueError('兼容配置路径越界或无效：' + name)
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('兼容配置摘要无效')


def _file_digest(root, relative):
    # Validate before touching the filesystem; both roots have independent scope.
    _validate_paths({relative: '0' * 64})
    root = Path(root)
    _no_link(root)
    path = _contained(root, relative)
    if not path.is_file():
        raise ValueError('缺少指纹文件：' + relative)
    return _digest(path)


def fingerprints(stage, ui_files=(), resources_root=None, resource_files=()):
    """Read-only evidence collection on an extracted app, never stops an app."""
    stage = Path(stage)
    package = _read_json(_contained(stage, 'package.json'))
    if not isinstance(package, dict):
        raise ValueError('package.json 必须为 JSON 对象')
    main = package.get('main', 'index.js')
    if not isinstance(main, str):
        raise ValueError('应用 main 必须为相对文件路径')
    paths = ['package.json', main, 'dist/preload.js'] + list(ui_files)
    files = {}
    for relative in paths:
        files[relative] = _file_digest(stage, relative)
    if resource_files and resources_root is None:
        raise ValueError('检查外部资源指纹必须显式提供 resources 目录')
    report = {'name': package.get('name'), 'version': package.get('version'),
            'main': main, 'moduleType': package.get('type', 'commonjs'),
            'files': files, 'bridgeVerified': False,
            'note': '指纹不是兼容证明；需验证可信窗口、preload 和 UI 安全区域。'}
    if resources_root is not None:
        report['resourcesFiles'] = {relative: _file_digest(resources_root, relative)
                                    for relative in resource_files}
    return report


def _validate_routes(routes):
    if (not isinstance(routes, list) or not 1 <= len(routes) <= 32
            or any(not isinstance(p, str) or re.fullmatch(r'/(?:[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*)?', p) is None for p in routes)
            or len(set(routes)) != len(routes)):
        raise ValueError('页面白名单必须包含 1 至 32 个唯一的精确路径')


def _validate_policy(policy, binding=None):
    if (not isinstance(policy, dict) or policy.get('verified') is not True
            or not isinstance(policy.get('rules'), list) or not policy['rules']):
        raise ValueError('兼容配置缺少已审核 UI 白名单')
    if binding is not None or 'paths' in policy:
        _validate_routes(policy.get('paths'))
        if binding is not None and set(policy['paths']) != set(binding['paths']):
            raise ValueError('UI 页面白名单必须与动态窗口绑定路径一致')

    def selector(value):
        return (isinstance(value, str) and bool(value.strip()) and len(value) <= 2048
                and not any(ord(c) < 32 for c in value))

    if 'excludeSelectors' in policy:
        excluded = policy['excludeSelectors']
        if not isinstance(excluded, list) or any(not selector(item) for item in excluded):
            raise ValueError('UI 排除区域配置无效')
    for rule in policy['rules']:
        if (not isinstance(rule, dict) or not selector(rule.get('selector'))
                or not isinstance(rule.get('contextKind'), str) or rule['contextKind'] not in UI_CONTEXTS
                or ('text' in rule and type(rule['text']) is not bool)):
            raise ValueError('UI 白名单规则无效')
        attributes = rule.get('attributes', [])
        if (not isinstance(attributes, list)
                or any(not isinstance(value, str) or value not in UI_ATTRIBUTES for value in attributes)
                or len(set(attributes)) != len(attributes)
                or (rule.get('text') is not True and not attributes)):
            raise ValueError('UI 白名单缺少有效的文本或属性目标')
        if binding is not None or 'sourceTexts' in rule:
            sources = rule.get('sourceTexts')
            if (not isinstance(sources, list) or not sources
                    or any(not isinstance(value, str) or not 1 <= len(value) <= 160
                           or value != value.strip() or re.fullmatch(r'[\x20-\x7e]+', value) is None
                           or re.search(r'[A-Za-z]', value) is None for value in sources)
                    or len(set(sources)) != len(sources)):
                raise ValueError('UI 规则必须包含唯一的固定英文短文案，不能使用空白或非字符串来源')


def _validate_profile(profile):
    if not isinstance(profile, dict) or profile.get('schemaVersion') != 1:
        raise ValueError('兼容配置版本无效')
    if profile.get('verified') is not True or profile.get('moduleType') != 'commonjs':
        raise ValueError('只接受已审核的 CommonJS 兼容配置')
    for field in ('id', 'name', 'version', 'main', 'preload'):
        if not isinstance(profile.get(field), str) or not profile[field]:
            raise ValueError('兼容配置缺少字段：' + field)
    paths = profile.get('files')
    if not isinstance(paths, dict) or not {'package.json', profile['main'], profile['preload']}.issubset(paths):
        raise ValueError('兼容配置缺少入口指纹')
    _validate_paths(paths)
    # Dynamic Hub profiles bind UI provenance to its separately packaged server.
    binding = profile.get('windowBinding')
    if binding is not None:
        if (not isinstance(binding, dict) or set(binding) != {'kind', 'paths'}
                or binding.get('kind') != DYNAMIC_BINDING or 'trustedUrls' in profile):
            raise ValueError('动态窗口绑定无效或与静态 URL 冲突')
        route_paths = binding.get('paths')
        _validate_routes(route_paths)
        if profile['preload'] != 'dist/preload.js':
            raise ValueError('当前动态窗口绑定仅支持已审核的 dist/preload.js')
        if not BINDING_FILES.issubset(paths):
            raise ValueError('动态窗口绑定缺少应用模块指纹')
        resources = profile.get('resourcesFiles')
        _validate_paths(resources)
        ui = profile.get('uiResources')
        if (not isinstance(ui, list) or 'bin/language_server.exe' not in ui
                or any(not isinstance(p, str) or p not in resources for p in ui)):
            raise ValueError('动态窗口绑定缺少 UI 服务来源指纹')
    else:
        # Static profiles remain supported for existing reviewed integrations.
        ui = profile.get('uiFiles')
        if not isinstance(ui, list) or not ui or any(not isinstance(p, str) or p not in paths for p in ui):
            raise ValueError('兼容配置缺少 UI 来源指纹')
        urls = profile.get('trustedUrls')
        if not isinstance(urls, list) or not urls or any(not isinstance(u, str) or not u.startswith(('https://', 'file://', 'app://')) or '*' in u for u in urls):
            raise ValueError('必须指定精确可信页面 URL')
        if 'resourcesFiles' in profile or 'uiResources' in profile:
            raise ValueError('静态窗口配置不接受动态资源绑定字段')
    _validate_policy(profile.get('policy'), binding)


def select_profile(stage, profiles=None, resources_root=None):
    """Profiles argument is an internal testing seam, not a user CLI switch."""
    if profiles is None:
        registry = _read_json(resource_root() / REGISTRY)
        if not isinstance(registry, dict) or registry.get('schemaVersion') != 1 or not isinstance(registry.get('profiles'), list):
            raise ValueError('桥接兼容性注册表无效')
        profiles = registry['profiles']
    package = _read_json(_contained(Path(stage), 'package.json'))
    if not isinstance(package, dict):
        raise ValueError('package.json 必须为 JSON 对象')
    matches = []
    for profile in profiles:
        _validate_profile(profile)
        if (package.get('name'), package.get('version'), package.get('main', 'index.js'), package.get('type', 'commonjs')) != (profile['name'], profile['version'], profile['main'], 'commonjs'):
            continue
        try:
            if not all(_file_digest(stage, relative) == digest for relative, digest in profile['files'].items()):
                continue
            if profile.get('windowBinding') is not None:
                if resources_root is None:
                    continue
                if not all(_file_digest(resources_root, relative) == digest
                           for relative, digest in profile['resourcesFiles'].items()):
                    continue
            matches.append(profile)
        except FileNotFoundError:
            continue
        except ValueError as error:
            if str(error).startswith('缺少指纹文件：'):
                continue
            raise
    if len(matches) > 1:
        raise ValueError('匹配多个桥接配置，拒绝猜测')
    return matches[0] if matches else None


def preload_extension(profile):
    """Inserted inside the legacy translator closure, never exports to page JS."""
    dom_source = (resource_root() / 'dom.js').read_text(encoding='utf-8')
    policy = json.dumps(profile['policy'], ensure_ascii=True)
    return """
  // DragonGirl isolated preload bridge (verified profile only).
  try {
    const __dgModule = { exports: {} };
    (function(module, exports) {
""" + dom_source + """
    })(__dgModule, __dgModule.exports);
    const { ipcRenderer: __dgIpc } = require('electron');
    let __dgSnapshot = { enabled: false, configRevision: -1, dictionaryRevision: -1, pageEpoch: -1, entries: {} };
    const __dgTranslator = __dgModule.exports.createDOMTranslator({
      document, MutationObserver,
      syncTranslate: (text) => {
        const value = translateText(text);
        return { value, matched: value !== text || Object.prototype.hasOwnProperty.call(dictionary, text.trim()) };
      },
      policy: """ + policy + """,
      getSnapshot: () => __dgSnapshot,
      bridge: { translate: (envelope) => __dgIpc.invoke('dragongirl:v1:translate', envelope) }
    });
    let __dgRefreshRunning = false;
    let __dgDisposed = false;
    async function __dgRefresh() {
      if (__dgRefreshRunning || __dgDisposed) return;
      __dgRefreshRunning = true;
      try {
        const next = await __dgIpc.invoke('dragongirl:v1:snapshot', {version:1});
        if (__dgDisposed) return;
        if (!next || next.version !== 1 || typeof next.enabled !== 'boolean' ||
            ![next.configRevision, next.dictionaryRevision, next.cacheEpoch].every(n => Number.isSafeInteger(n) && n >= 0) ||
            !Number.isSafeInteger(next.pageEpoch) || next.pageEpoch < 1 ||
            !next.entries || typeof next.entries !== 'object' || Array.isArray(next.entries) ||
            Object.keys(next.entries).length > 10000 ||
            Object.entries(next.entries).some(([key, value]) => !key || key.length > 500 ||
              ['__proto__', 'constructor', 'prototype'].includes(key) || typeof value !== 'string' || value.length > 2000)) {
          throw new Error('Invalid snapshot');
        }
        const changed = next.configRevision !== __dgSnapshot.configRevision ||
          next.dictionaryRevision !== __dgSnapshot.dictionaryRevision ||
          next.cacheEpoch !== __dgSnapshot.cacheEpoch || next.enabled !== __dgSnapshot.enabled ||
          next.pageEpoch !== __dgSnapshot.pageEpoch;
        __dgSnapshot = next;
        if (changed) { __dgTranslator.refresh(); __dgTranslator.scan(document.body); }
      } catch (_) {
        __dgSnapshot = { enabled: false, configRevision: -1, dictionaryRevision: -1, pageEpoch: -1, entries: {} };
        __dgTranslator.invalidate();
      } finally { __dgRefreshRunning = false; }
    }
    function __dgStart() { __dgTranslator.start(); __dgRefresh(); }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', __dgStart, {once:true});
    else __dgStart();
    const __dgTimer = setInterval(__dgRefresh, 1500);
    window.addEventListener('pagehide', () => {
      __dgDisposed = true; clearInterval(__dgTimer); __dgTranslator.stop();
    }, {once:true});
  } catch (_) { /* No unrestricted fallback: leave the original UI unchanged. */ }
"""


def prepare_bridge(stage, profile):
    """Modify only a validated staging tree; caller owns activation/rollback."""
    stage = Path(stage)
    destination = stage / '.dragongirl'
    if destination.exists() or destination.is_symlink():
        raise ValueError('应用已有 .dragongirl 路径，拒绝覆盖')
    source = resource_root()
    for name in RUNTIME_FILES:
        if not (source / name).is_file():
            raise ValueError('缺少桥接资源：' + name)
    destination.mkdir()
    for name in RUNTIME_FILES:
        shutil.copyfile(source / name, destination / name)
    if profile.get('windowBinding') is not None:
        window_path = _contained(stage, 'dist/utils.js')
        content = window_path.read_text(encoding='utf-8')
        if content.count(HUB_ANCHOR) != 1 or content.count(HUB_PRELOAD) != 1 or HUB_HOOK in content:
            raise ValueError('目标窗口注册位置不是唯一预期结构，未激活桥接')
        window_path.write_text(content.replace(HUB_ANCHOR, HUB_ANCHOR + '\n' + HUB_HOOK, 1), encoding='utf-8')
    package_path = stage / 'package.json'
    package = _read_json(package_path)
    package['main'] = '.dragongirl/bootstrap.cjs'
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    installed_profile = dict(profile)
    installed_profile['runtimeIntegrity'] = {
        relative: _file_digest(stage, relative)
        for relative in sorted(set(profile['files']) | {'.dragongirl/' + name for name in RUNTIME_FILES})
    }
    (destination / 'profile.json').write_text(json.dumps(installed_profile, ensure_ascii=True), encoding='utf-8')
