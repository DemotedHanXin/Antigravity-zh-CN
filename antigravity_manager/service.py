"""Structured manager operations. Importing this module has no side effects on data."""
import copy
import datetime
import importlib.util
import shutil
import subprocess
import sys
import threading
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'localization'
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from translation_config import ConflictError, DataError, PROVIDERS, UserStore, validate_config
from translation_integration import resource_root
from translation_service import DictionaryService


def _settings_module():
    spec = importlib.util.spec_from_file_location('manager_probe_settings', SOURCE / 'Translation-Settings.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def public_config(config):
    """Whitelist fields; never pass credentials (including encrypted blobs) to UI."""
    return dict(revision=config['revision'], enabled=config['enabled'], provider=config['provider'],
                providers={name: dict(baseUrl=config['providers'][name]['baseUrl'],
                                      model=config['providers'][name]['model'],
                                      hasKey=bool(config['providers'][name]['apiKey'])) for name in PROVIDERS},
                limits=copy.deepcopy(config['limits']))


class ManagerService:
    def __init__(self, data_dir=None, store=None, installation=None):
        self.store = store if store is not None else UserStore(directory=data_dir)
        self.dictionary = DictionaryService(self.store)
        self.installation = installation
        self._lock = threading.Lock()
        self._events = []
        self._connection = {'status': 'not_tested', 'revision': None}

    def _installer(self):
        if self.installation is None:
            from installation_service import InstallationService
            self.installation = InstallationService()
        return self.installation

    def _save_config(self, config, revision, keys=None):
        if type(revision) is not int or revision < 0:
            raise ConflictError('请先重新加载配置。')
        current = self.store.read_config()
        if current['revision'] != revision:
            raise ConflictError('配置已被其他程序修改，请重新加载后保存。')
        if (not isinstance(config, dict) or set(config) != {'revision', 'enabled', 'provider', 'providers', 'limits'}
                or not isinstance(config['providers'], dict) or set(config['providers']) != set(PROVIDERS)):
            raise DataError('配置字段不完整。')
        keys = {} if keys is None else keys
        if not isinstance(keys, dict) or not set(keys).issubset(PROVIDERS):
            raise DataError('密钥更新参数无效。')
        candidate = copy.deepcopy(current)
        candidate.update(enabled=config['enabled'], provider=config['provider'], limits=copy.deepcopy(config['limits']))
        for name in PROVIDERS:
            profile = config['providers'][name]
            if not isinstance(profile, dict) or set(profile) != {'baseUrl', 'model', 'hasKey'}:
                raise DataError('提供商配置字段无效。')
            candidate['providers'][name].update(baseUrl=profile['baseUrl'], model=profile['model'])
            if name in keys:
                candidate['providers'][name]['apiKey'] = keys[name]
        validate_config(candidate)
        saved = self.store.save_config(candidate, expected_revision=revision)
        self._connection = {'status': 'not_tested', 'revision': None}
        return {'ok': True, 'config': public_config(saved), 'message': '配置已保存。'}

    def _probe(self, revision, confirmed=False):
        if confirmed is not True:
            return {'ok': False, 'code': 'confirmation_required', 'message': '请确认使用已保存配置发送固定测试文案。'}
        config = self.store.read_config()
        if type(revision) is not int or config['revision'] != revision:
            raise ConflictError('配置已变化，请重新加载后再测试。')
        selected = config['providers'][config['provider']]
        if not all(selected.get(name, '').strip() for name in ('baseUrl', 'model', 'apiKey')):
            raise DataError('测试前请保存提供商地址、模型和密钥。')
        settings = _settings_module()
        bundled_node = Path(getattr(sys, '_MEIPASS', SOURCE.parents[1])) / 'node' / 'node.exe'
        node = str(bundled_node) if bundled_node.is_file() else shutil.which('node')
        probe = resource_root() / 'probe.cjs'
        if not node or not probe.is_file():
            status = 'unavailable'
        else:
            command = [node, str(probe), '--confirm-network', '--revision', str(revision),
                       '--data-dir', str(self.store.directory.resolve())]
            status = settings.run_confirmed_probe(command)
        # A completed request does not certify edits made while it was running.
        if self.store.read_config()['revision'] != revision:
            status = 'configuration_changed'
        self._connection = {'status': status, 'revision': revision}
        return {'ok': status == 'connected', 'code': status,
                'message': settings.PROBE_STATUSES[status], 'connection': dict(self._connection)}

    def _execute(self, action, **kwargs):
        if action in ('list', 'pending', 'set', 'restore-default', 'accept', 'reject', 'unblock',
                      'cleanup', 'import-dictionary', 'export-dictionary'):
            return self.dictionary.execute(action, **kwargs)
        if action == 'config':
            return {'ok': True, 'config': public_config(self.store.read_config())}
        if action == 'save-config':
            return self._save_config(**kwargs)
        if action == 'probe':
            return self._probe(**kwargs)
        if action == 'status':
            result = self._installer().execute('status', **kwargs)
            # Installation and config health are independent, and are displayed separately.
            try:
                config = self.store.read_config()
                result['config'] = {'enabled': config['enabled'], 'provider': config['provider'],
                                    'revision': config['revision']}
                result['connection'] = (dict(self._connection) if self._connection['revision'] == config['revision']
                                        else {'status': 'not_tested', 'revision': None})
                result['configurationStatus'] = 'ready'
            except (DataError, OSError):
                result['configurationStatus'] = 'unavailable'
                result['connection'] = {'status': 'not_tested', 'revision': None}
            return result
        if action in ('apply', 'restore', 'launch'):
            return self._installer().execute(action, **kwargs)
        if action == 'diagnostics':
            return {'ok': True, 'events': copy.deepcopy(self._events)}
        raise DataError('不支持的管理操作。')

    def execute(self, action, **kwargs):
        """Serialize operations and expose only safe, structured diagnostics."""
        with self._lock:
            try:
                result = self._execute(action, **kwargs)
            except ConflictError as error:
                result = {'ok': False, 'code': 'conflict', 'message': str(error)}
            except DataError as error:
                result = {'ok': False, 'code': 'invalid_data', 'message': str(error)}
            except (OSError, subprocess.SubprocessError):
                result = {'ok': False, 'code': 'operation_failed', 'message': '操作未完成，请检查文件权限、运行依赖及数据锁。'}
            except (ValueError, TypeError, KeyError):
                result = {'ok': False, 'code': 'invalid_arguments', 'message': '操作参数或数据格式无效。'}
            if action != 'diagnostics':
                allowed_actions = ('list', 'pending', 'set', 'restore-default', 'accept', 'reject', 'unblock',
                                   'cleanup', 'import-dictionary', 'export-dictionary', 'config', 'save-config',
                                   'probe', 'status', 'apply', 'restore', 'launch')
                event = {'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         'action': action if action in allowed_actions else 'unknown',
                         'ok': result['ok'], 'code': result.get('code', 'ok')}
                if action in ('apply', 'restore', 'launch'):
                    event['steps'] = [dict(step=item['step'], status=item['status'])
                                      for item in result.get('steps', [])
                                      if item.get('step') in ('prepare', 'validate', 'stop', 'activate', 'rollback', 'cleanup', 'launch')
                                      and item.get('status') in ('completed', 'incomplete', 'requested')]
                    event['filesChanged'] = result.get('filesChanged') is True
                    event['restartRequired'] = result.get('restartRequired') is True
                    event['message'] = ('操作完成，请核对目标应用。' if result['ok'] else
                                        '操作未完成；保留原版归档和暂存目录，核对权限、占用及恢复状态。')
                self._events.append(event)
                self._events = self._events[-200:]
            return result
