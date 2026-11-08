"""Native Qt workflows with isolated user data and a disposable ASAR fixture."""
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QPushButton
    from app.ui import MainWindow
    from app import services
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

from test_localization import make_archive

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(QT_AVAILABLE, 'PySide6 is required for desktop UI tests')
class DesktopUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        cls.application.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.desktop-ui-test-', dir=ROOT)
        self.root = Path(self.temp.name)
        self.install = self.root / '安装目录'
        resources = self.install / 'resources'
        resources.mkdir(parents=True)
        (self.install / 'Antigravity.exe').write_bytes(b'never launched')
        make_archive(resources / 'app.asar')
        self.window = MainWindow(data_dir=self.root / 'data', app_dir=self.install, autoload=False)
        self.window.show()
        QTest.qWait(20)

    def tearDown(self):
        self.wait_idle()
        self.window.dictionary_page.dirty = False
        self.window.close()
        self.window.deleteLater()
        self.application.processEvents()
        self.temp.cleanup()

    def wait_idle(self, timeout=10):
        deadline = time.monotonic() + timeout
        while self.window.busy and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(self.window.busy, 'Qt worker did not finish')
        self.application.processEvents()

    @staticmethod
    def click_text(widget, text):
        matches = [button for button in widget.findChildren(QPushButton) if button.text() == text]
        if len(matches) != 1:
            raise AssertionError('button not unique: ' + text)
        QTest.mouseClick(matches[0], Qt.MouseButton.LeftButton)

    def test_real_patch_restore_via_window_worker_and_confirmations(self):
        self.window.refresh_installation()
        self.wait_idle()
        self.assertEqual(self.window.installation.state, 'original')
        self.assertTrue(self.window.patch_button.isEnabled())
        patcher = services._module('Antigravity-Patcher')
        restorer = services._module('Restore')
        with mock.patch.object(patcher, 'stop_application') as stop, \
                mock.patch.object(restorer, 'stop_application'), \
                mock.patch.object(services.common, 'launch_application') as launch, \
                mock.patch('app.ui.confirm', return_value=True):
            self.window.patch()
            self.assertTrue(self.window.busy)
            self.wait_idle()
            self.assertEqual(self.window.installation.state, 'localized')
            self.assertIn('已记录应用', self.window.pending.text())
            stop.assert_called_once()
            launch.assert_not_called()
            # An equal revision is insufficient when another profile/import
            # supplied different dictionary content.
            self.window.installation.dictionary_hash = '0' * 64
            self.window.update_dictionary_status()
            self.assertIn('尚未确认', self.window.pending.text())
            self.window.restore()
            self.wait_idle()
            self.assertEqual(self.window.installation.state, 'original')
            self.assertIn('恢复英文', self.window.session.toPlainText())
            launch.assert_not_called()

    def test_busy_task_blocks_second_task_navigation_and_close(self):
        release = threading.Event()
        completed = []
        self.window.run_task('阻塞任务', lambda progress: release.wait(5), completed.append)
        try:
            self.assertFalse(self.window.pages.isEnabled())
            self.assertFalse(self.window.sidebar.isEnabled())
            self.assertTrue(self.window.progress.isVisible())
            forbidden = mock.Mock()
            self.window.run_task('不能重入', forbidden, forbidden)
            self.window.navigate(1)
            self.assertEqual(self.window.pages.currentIndex(), 0)
            event = QCloseEvent()
            self.window.closeEvent(event)
            self.assertFalse(event.isAccepted())
            forbidden.assert_not_called()
        finally:
            release.set()
        self.wait_idle()
        self.assertEqual(completed, [True])
        self.assertTrue(self.window.pages.isEnabled())
        self.assertTrue(self.window.sidebar.isEnabled())
        self.assertFalse(self.window.progress.isVisible())

    def test_worker_error_releases_busy_state_and_does_not_call_success(self):
        def fail(_):
            raise RuntimeError('模拟失败')
        success = mock.Mock()
        self.window.run_task('错误测试', fail, success)
        self.wait_idle()
        success.assert_not_called()
        self.assertIn('模拟失败', self.window.activity.text())
        self.assertTrue(self.window.pages.isEnabled())

    def test_empty_worker_exception_is_still_failure(self):
        def fail(_):
            raise RuntimeError()
        success = mock.Mock()
        self.window.run_task('无文本错误', fail, success)
        self.wait_idle()
        success.assert_not_called()
        self.assertIn('未完成', self.window.activity.text())

    def test_dictionary_add_search_save_and_unsaved_navigation_guard(self):
        self.window.resize(1280, 820)
        self.window.navigate(1)
        page = self.window.dictionary_page
        self.click_text(page, '添加词条')
        QTest.keyClicks(page.source, 'Exact UI Sample')
        page.target.setPlainText('准确的界面译文')
        self.assertTrue(page.dirty)
        with mock.patch.object(page, 'maybe_leave', return_value=False):
            self.window.navigate(0)
        self.assertEqual(self.window.pages.currentIndex(), 1)
        self.click_text(page, '保存修改')
        self.assertFalse(page.dirty)
        self.assertEqual(self.window.store.revision, 1)
        self.assertTrue(self.window.store.path.is_file())
        page.search.setText('准确的界面')
        self.assertEqual(page.model.rowCount(), 1)
        self.assertEqual(page.model.entries[0]['source'], 'Exact UI Sample')
        self.assertIn('已保存', self.window.pending.text())
        self.assertNotIn('已记录应用', self.window.pending.text())

    def test_search_refresh_keeps_unsaved_editor_and_cancelled_selection(self):
        self.window.navigate(1)
        page = self.window.dictionary_page
        first, second = page.model.entries[:2]
        page.table.setCurrentIndex(page.model.index(0, 0))
        page.target.setPlainText('尚未保存的译文')
        page.search.setText(second['source'])
        self.assertTrue(page.dirty)
        self.assertEqual(page.target.toPlainText(), '尚未保存的译文')
        with mock.patch.object(page, 'maybe_leave', return_value=False):
            page.table.setCurrentIndex(page.model.index(0, 0))
        self.assertEqual(page.current['source'], first['source'])
        self.assertEqual(page.target.toPlainText(), '尚未保存的译文')

    def test_compact_dictionary_retains_editor_and_returns_to_table(self):
        self.window.resize(720, 480)
        self.window.navigate(1)
        QTest.qWait(20)
        page = self.window.dictionary_page
        self.assertTrue(page.list_panel.isVisible())
        self.assertFalse(page.editor.isVisible())
        page.table.setCurrentIndex(page.model.index(0, 0))
        QTest.qWait(10)
        self.assertTrue(page.editor.isVisible())
        self.assertFalse(page.list_panel.isVisible())
        self.assertTrue(page.back.isVisible())
        self.click_text(page, '返回列表')
        self.assertTrue(page.list_panel.isVisible())
        self.assertFalse(page.editor.isVisible())
        self.window.resize(1400, 900)
        QTest.qWait(20)
        self.assertTrue(page.list_panel.isVisible())
        self.assertTrue(page.editor.isVisible())

    def test_invalid_dictionary_input_stays_in_editor_without_writing(self):
        self.window.navigate(1)
        page = self.window.dictionary_page
        page.add_entry()
        page.source.setPlainText('  illegal leading whitespace')
        page.target.setPlainText('不写入')
        self.assertFalse(page.save_entry())
        self.assertTrue(page.dirty)
        self.assertFalse(self.window.store.path.exists())
        self.assertTrue(page.validation.text())

    def test_scanning_directory_edit_invalidates_visible_preview(self):
        result = services.TaskResult('success', 'proxy_preview', '测试预览', details=['不会修改实际快捷方式'])
        self.window.render_result(result)
        self.assertEqual(self.window.preview_action, 'proxy_setup')
        self.assertTrue(self.window.proxy_execute.isEnabled())
        self.window.scan_roots.setPlainText(str(self.root / 'other'))
        self.assertIsNone(self.window.preview_action)
        self.assertFalse(self.window.proxy_execute.isEnabled())


if __name__ == '__main__':
    unittest.main()
