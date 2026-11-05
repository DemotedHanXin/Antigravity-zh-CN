"""Offscreen widget/service tests; never launch Antigravity or call a provider."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import tempfile
import time
import unittest
from unittest.mock import patch

from source_paths import ROOT
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
QT_AVAILABLE = importlib.util.find_spec('PySide6') is not None
if QT_AVAILABLE:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    from antigravity_manager.ui import ManagerWindow


def config():
    return {'revision': 7, 'enabled': False, 'provider': 'openai',
            'providers': {name: {'baseUrl': 'https://api.example.com', 'model': name + '-test', 'hasKey': name == 'openai'}
                          for name in ('openai', 'gemini', 'claude', 'compatible')},
            'limits': {'concurrency': 2, 'batchSize': 8, 'batchCharacters': 2000,
                       'textLength': 160, 'timeoutMs': 15000, 'requestsPerMinute': 12,
                       'queueSize': 128, 'sessionRequests': 100}}


class FakeService:
    def __init__(self):
        self.calls = []
        self.responses = {}
        self.gate = None

    def execute(self, action, **kwargs):
        self.calls.append((action, copy.deepcopy(kwargs), threading.get_ident()))
        if self.gate:
            self.gate.wait(3)
        if action in self.responses:
            return copy.deepcopy(self.responses[action])
        if action in ('config', 'save-config'):
            return {'ok': True, 'config': config()}
        if action == 'list':
            return {'ok': True, 'dictionaryRevision': 3, 'candidatesRevision': 1,
                    'entries': [{'original': 'Home', 'translation': '首页', 'source': 'manual'}]}
        if action == 'pending':
            return {'ok': True, 'dictionaryRevision': 3, 'candidatesRevision': 9,
                    'entries': [{'original': 'Queue', 'translation': '队列', 'expiresAt': int(time.time() * 1000) + 500000}],
                    'rejected': [{'original': 'Automation', 'rejectedAt': 1234000}]}
        if action == 'diagnostics':
            return {'ok': True, 'events': [{'time': 'now', 'action': 'config', 'ok': True, 'code': 'ok'}]}
        return {'ok': True}


@unittest.skipUnless(QT_AVAILABLE, 'Install requirements-manager.txt to run offscreen GUI tests')
class ManagerUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.service = FakeService()
        self.window = ManagerWindow(self.service, app_dir='test-install', autoload=False)
        self.window.cleanup_timer.stop()
        self.window.expiry_timer.stop()
        self.warning = patch.object(QMessageBox, 'warning', return_value=QMessageBox.StandardButton.Ok).start()
        self.info = patch.object(QMessageBox, 'information', return_value=QMessageBox.StandardButton.Ok).start()
        self.confirm = patch.object(self.window, '_confirm', return_value=True).start()

    def tearDown(self):
        if self.service.gate:
            self.service.gate.set()
        self.wait_done()
        self.window.config_dirty = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        patch.stopall()

    def wait_done(self, timeout=5):
        deadline = time.monotonic() + timeout
        while self.window.task is not None and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.003)
        self.assertIsNone(self.window.task, 'worker did not finish')
        self.app.processEvents()

    def load_config(self):
        self.window.load_config()
        self.wait_done()

    def test_initialization_is_lazy_and_six_pages_exist(self):
        self.assertEqual(self.service.calls, [])
        self.assertEqual(self.window.pages.count(), 6)
        self.assertEqual(self.window.api_key.echoMode(), self.window.api_key.EchoMode.Password)

    def test_loading_config_never_returns_key_or_calls_provider(self):
        self.load_config()
        self.assertEqual(self.window.api_key.text(), '')
        self.assertTrue(self.window.config_draft['providers']['openai']['hasKey'])
        self.assertFalse(self.window.config_dirty)
        self.assertEqual([call[0] for call in self.service.calls], ['config'])

    def test_keys_preserve_clear_and_switch_provider(self):
        self.load_config()
        self.window._save_config()
        self.wait_done()
        self.assertEqual(self.service.calls[-1][1]['keys'], {})
        self.window.api_key.setText('fake-openai-secret')
        self.window.provider.setCurrentIndex(1)
        self.window.clear_key.setChecked(True)
        self.window.provider.setCurrentIndex(0)
        self.assertEqual(self.window.api_key.text(), 'fake-openai-secret')
        self.window._save_config()
        self.wait_done()
        kwargs = self.service.calls[-1][1]
        self.assertEqual(kwargs['keys'], {'openai': 'fake-openai-secret', 'gemini': ''})
        self.assertEqual(kwargs['revision'], 7)
        self.assertNotIn('apiKey', str(kwargs['config']))
        self.assertEqual(self.window.api_key.text(), '')
        self.assertEqual(self.window.key_edits, {})

    def test_conflict_keeps_unsaved_config_and_password(self):
        self.load_config()
        self.window.api_key.setText('fake-draft')
        self.window._dirty()
        self.service.responses['save-config'] = {'ok': False, 'code': 'conflict', 'message': '配置已变化。'}
        self.window._save_config()
        self.wait_done()
        self.assertEqual(self.window.api_key.text(), 'fake-draft')
        self.assertTrue(self.window.config_dirty)
        self.warning.assert_called_once()

    def test_dirty_config_blocks_network_and_confirmed_test_has_revision(self):
        self.load_config()
        self.window.enabled.setChecked(True)
        self.window._probe()
        self.assertEqual(len(self.service.calls), 1)
        self.window._show_config({'ok': True, 'config': config()})
        self.window._probe()
        self.wait_done()
        self.assertEqual(self.service.calls[-1][:2], ('probe', {'revision': 7, 'confirmed': True}))

    def test_worker_keeps_event_loop_responsive_and_serializes_actions(self):
        self.service.gate = threading.Event()
        ticks = []
        timer = QTimer()
        timer.setInterval(1)
        timer.timeout.connect(lambda: ticks.append(True))
        timer.start()
        self.assertTrue(self.window.run_action('cleanup'))
        self.assertFalse(self.window.run_action('probe'))
        self.assertFalse(self.window.pages.isEnabled())
        end = time.monotonic() + .05
        while time.monotonic() < end:
            self.app.processEvents()
            time.sleep(.002)
        self.assertTrue(ticks)
        self.assertNotEqual(self.service.calls[0][2], threading.get_ident())
        self.service.gate.set()
        self.wait_done()
        timer.stop()
        self.assertTrue(self.window.pages.isEnabled())

    def test_close_during_job_defers_without_terminating_worker(self):
        self.service.gate = threading.Event()
        self.window.run_action('cleanup')
        task = self.window.task
        self.window.close()
        self.assertTrue(self.window._close_pending)
        self.assertIs(self.window.task, task)
        self.service.gate.set()
        self.wait_done()
        self.assertFalse(self.window._close_pending)

    def test_cleanup_and_expiry_refresh_keep_candidate_edit_and_config(self):
        self.load_config()
        self.window.load_pending()
        self.wait_done()
        self.window.pending_table.selectRow(0)
        self.window.review_translation.setText('编辑中的队列')
        self.window.model.setText('unsaved-model')
        self.window._dirty()
        self.window._scheduled_cleanup()
        self.wait_done()
        self.window._refresh_expiries()
        self.assertEqual(self.window.review_translation.text(), '编辑中的队列')
        self.assertEqual(self.window.model.text(), 'unsaved-model')
        self.assertEqual(self.window.candidates_revision, 9)
        self.assertTrue(self.window.config_dirty)

    def test_failure_during_deferred_close_is_displayed_and_window_stays_open(self):
        self.service.gate = threading.Event()
        self.service.responses['restore'] = {'ok': False, 'message': '还原未完成。', 'filesChanged': True}
        self.window.run_action('restore', self.window._install_finished)
        self.window.close()
        self.assertTrue(self.window._close_pending)
        self.service.gate.set()
        self.wait_done()
        self.assertFalse(self.window._close_pending)
        self.assertIn('还原未完成', self.window.operation_result.text())
        self.assertIn('文件已变化', self.window.operation_result.text())
        self.warning.assert_called_once()

    def test_autodetected_installation_becomes_explicit_target(self):
        self.window.app_path.clear()
        self.window._show_status({'ok': True, 'installation': {'path': 'auto-install', 'component': 'outdated'}})
        self.assertEqual(self.window.app_path.text(), 'auto-install')
        self.assertIn('需要更新', self.window.overview.toPlainText())

    def test_review_uses_displayed_revision_and_edited_translation(self):
        self.window.load_pending()
        self.wait_done()
        self.window.pending_table.selectRow(0)
        self.window.review_translation.setText('人工队列')
        self.window._review('accept')
        self.wait_done()
        call = next(call for call in self.service.calls if call[0] == 'accept')
        self.assertEqual(call[1], {'source': 'Queue', 'translation': '人工队列', 'revision': 9})
        self.window.rejected_table.selectRow(0)
        self.window._unblock()
        self.wait_done()
        call = next(call for call in self.service.calls if call[0] == 'unblock')
        self.assertEqual(call[1], {'source': 'Automation', 'revision': 9})

    def test_expired_review_failure_preserves_edit_for_manual_recovery(self):
        self.window.load_pending()
        self.wait_done()
        self.window.pending_table.selectRow(0)
        self.window.review_translation.setText('人工草稿')
        self.service.responses['accept'] = {'ok': False, 'code': 'conflict', 'message': '候选已经到期。'}
        self.window._review('accept')
        self.wait_done()
        self.assertEqual(self.window.review_translation.text(), '人工草稿')
        self.assertEqual(self.window.review_source.text(), 'Queue')

    def test_dictionary_selection_and_revision_pass_through(self):
        self.window.load_dictionary()
        self.wait_done()
        self.window.dictionary_table.selectRow(0)
        self.window.translation.setText('主页')
        self.window._save_entry()
        self.wait_done()
        call = next(call for call in self.service.calls if call[0] == 'set')
        self.assertEqual(call[1], {'source': 'Home', 'translation': '主页', 'revision': 3})

    def test_dictionary_reload_cannot_rebase_stale_editor_draft(self):
        self.window.load_dictionary()
        self.wait_done()
        self.window.dictionary_table.selectRow(0)
        self.window.translation.setText('旧的草稿')
        self.window.load_dictionary()
        self.wait_done()
        self.assertEqual(self.window.source.text(), '')
        self.assertEqual(self.window.translation.text(), '')

    def test_install_requires_explicit_path_and_confirmation(self):
        self.window.app_path.clear()
        self.window._install('apply')
        self.assertEqual(self.service.calls, [])
        self.window.app_path.setText('isolated-install')
        self.confirm.return_value = False
        self.window._install('apply')
        self.assertEqual(self.service.calls, [])
        self.confirm.return_value = True
        self.window._install('restore')
        self.wait_done()
        self.assertEqual(self.service.calls[0][:2], ('restore', {'app_dir': 'isolated-install', 'confirmed': True}))

    def test_failed_status_and_arbitrary_exception_are_safe(self):
        self.service.responses['status'] = {'ok': False, 'installation': None, 'message': '未发现安装。'}
        self.window.refresh_status()
        self.wait_done()
        self.assertIn('未发现安装', self.window.overview.toPlainText())
        with patch.object(self.service, 'execute', side_effect=RuntimeError('fake-secret-never-render')):
            self.window.run_action('cleanup')
            self.wait_done()
        self.assertNotIn('fake-secret', self.window.statusBar().currentMessage())

    def test_real_service_roundtrip_uses_only_isolated_state(self):
        from antigravity_manager.service import ManagerService
        test_root = ROOT / '.m3-lab-ui-tests'
        test_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=test_root) as directory:
            self.window.service = ManagerService(data_dir=Path(directory) / 'data')
            self.load_config()
            self.assertFalse(self.window.enabled.isChecked())
            self.window.model.setText('isolated-test-model')
            self.window._dirty()
            self.window._save_config()
            self.wait_done()
            self.assertFalse(self.window.config_dirty)
            self.window.query.setText('Manager Test Source')
            self.window.load_dictionary()
            self.wait_done()
            self.window.source.setText('Manager Test Source')
            self.window.translation.setText('管理器测试词条')
            self.window._save_entry()
            self.wait_done()
            self.assertEqual(self.window.dictionary_table.rowCount(), 1)
            self.assertEqual(self.window.dictionary_table.item(0, 1).text(), '管理器测试词条')
            exported = Path(directory) / 'dictionary.json'
            self.window.run_action('export-dictionary', path=str(exported))
            self.wait_done()
            content = json.loads(exported.read_text(encoding='utf-8'))
            self.assertEqual(content['entries'], {'Manager Test Source': '管理器测试词条'})
            self.assertNotIn('providers', content)
            self.assertEqual(self.warning.call_count, 0)

    def test_install_steps_and_partial_results_remain_visible_after_refresh(self):
        result = {'ok': False, 'message': '清理未完成，请保留暂存目录。',
                  'filesChanged': True, 'restartRequired': True,
                  'steps': [{'step': 'activate', 'status': 'completed'},
                            {'step': 'cleanup', 'status': 'incomplete'}]}
        self.window._install_finished(result)
        self.window._show_status({'ok': True, 'installation': {'component': 'not_installed'}})
        self.assertIn('切换安装文件：完成', self.window.operation_result.text())
        self.assertIn('清理暂存目录：未完成', self.window.operation_result.text())
        self.assertIn('安装文件已变化', self.window.operation_result.text())
        self.window._show_diagnostics({'ok': True, 'events': [dict(result, time='now', action='restore', code='cleanup_incomplete')]})
        self.assertIn('清理暂存目录：未完成', self.window.log.toPlainText())
        self.assertIn('请保留暂存目录', self.window.log.toPlainText())


if __name__ == '__main__':
    unittest.main()
