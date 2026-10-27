"""Fail-closed Electron bridge packaging; no application compatibility is assumed.

Only reviewed, bundled profiles can enable the bridge. Fingerprint reports are
not authorization profiles, and the CLI cannot enable an unreviewed profile.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sys

from antigravity_common import _contained

RUNTIME_FILES = ('main.cjs', 'providers.cjs', 'storage.cjs', 'bootstrap.cjs')
REGISTRY = 'compatibility.json'


def resource_root():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'localization_runtime'


def _read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def fingerprints(stage, ui_files=()):
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
        path = _contained(stage, relative)
        if not path.is_file():
            raise ValueError('缺少指纹文件：' + relative)
        files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'name': package.get('name'), 'version': package.get('version'),
            'main': main, 'moduleType': package.get('type', 'commonjs'),
            'files': files, 'bridgeVerified': False,
            'note': '指纹不是兼容证明；需验证可信窗口、preload 和 UI 安全区域。'}


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
    for name, digest in paths.items():
        pure = PurePosixPath(name)
        if pure.is_absolute() or '..' in pure.parts or '\\' in name or not name:
            raise ValueError('兼容配置路径越界')
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('兼容配置摘要无效')
    # UI policy must be bound to actual renderer source, not just main/preload.
    ui = profile.get('uiFiles')
    if not isinstance(ui, list) or not ui or any(p not in paths for p in ui):
        raise ValueError('兼容配置缺少 UI 来源指纹')
    urls = profile.get('trustedUrls')
    if not isinstance(urls, list) or not urls or any(not isinstance(u, str) or not u.startswith(('https://', 'file://', 'app://')) or '*' in u for u in urls):
        raise ValueError('必须指定精确可信页面 URL')
    policy = profile.get('policy')
    if not isinstance(policy, dict) or policy.get('verified') is not True or not isinstance(policy.get('rules'), list) or not policy['rules']:
        raise ValueError('兼容配置缺少已审核 UI 白名单')


def select_profile(stage, profiles=None):
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
        if all(_contained(Path(stage), relative).is_file() and hashlib.sha256(_contained(Path(stage), relative).read_bytes()).hexdigest() == digest for relative, digest in profile['files'].items()):
            matches.append(profile)
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
    let __dgSnapshot = { enabled: false, configRevision: -1, dictionaryRevision: -1, entries: {} };
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
            !next.entries || typeof next.entries !== 'object' || Array.isArray(next.entries) ||
            Object.keys(next.entries).length > 10000 ||
            Object.entries(next.entries).some(([key, value]) => !key || key.length > 500 ||
              ['__proto__', 'constructor', 'prototype'].includes(key) || typeof value !== 'string' || value.length > 2000)) {
          throw new Error('Invalid snapshot');
        }
        const changed = next.configRevision !== __dgSnapshot.configRevision ||
          next.dictionaryRevision !== __dgSnapshot.dictionaryRevision ||
          next.cacheEpoch !== __dgSnapshot.cacheEpoch || next.enabled !== __dgSnapshot.enabled;
        __dgSnapshot = next;
        if (changed) { __dgTranslator.refresh(); __dgTranslator.scan(document.body); }
      } catch (_) {
        __dgSnapshot = { enabled: false, configRevision: -1, dictionaryRevision: -1, entries: {} };
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
  } catch (_) { /* Legacy dictionary remains available; no secrets are logged. */ }
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
    (destination / 'profile.json').write_text(json.dumps(profile, ensure_ascii=True), encoding='utf-8')
    package_path = stage / 'package.json'
    package = _read_json(package_path)
    package['main'] = '.dragongirl/bootstrap.cjs'
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
