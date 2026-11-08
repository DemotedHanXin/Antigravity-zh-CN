"""The first-use wizard must inspect asynchronously without mutating installs."""
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
    from PySide6.QtWidgets import QApplication, QDialog, QWizard
    from app.onboarding import InstallationWizard
    from app.services import AppService, Installation
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

from test_localization import make_archive

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(QT_AVAILABLE, 'PySide6 is required for onboarding tests')
class OnboardingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        cls.application.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.onboarding-test-', dir=ROOT)
        self.root = Path(self.temp.name)
        self.install = self.root / '安装目录'
        resources = self.install / 'resources'
        resources.mkdir(parents=True)
        (self.install / 'Antigravity.exe').write_bytes(b'fixture only')
        make_archive(resources / 'app.asar')
        self.wizard = None

    def tearDown(self):
        if self.wizard:
            self.wait_idle()
            self.wizard.close()
            self.wizard.deleteLater()
            self.application.processEvents()
        self.temp.cleanup()

    def open(self, service, path=''):
        self.wizard = InstallationWizard(service, path)
        self.wizard.show()
        self.application.processEvents()

    def click(self, button):
        QTest.mouseClick(self.wizard.button(button), Qt.MouseButton.LeftButton)

    def wait_idle(self):
        deadline = time.monotonic() + 10
        while self.wizard.busy and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(self.wizard.busy)
        self.application.processEvents()

    def inventory(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def test_valid_fixture_passes_three_pages_without_install_writes(self):
        self.open(AppService(self.root / 'data'), str(self.install))
        before = self.inventory()
        self.assertEqual(self.wizard.currentId(), 0)
        self.click(QWizard.WizardButton.NextButton)
        self.wait_idle()
        self.assertEqual(self.wizard.currentId(), 1)
        self.assertTrue(self.wizard.inspect_page.isComplete())
        self.assertEqual(self.wizard.selected_path, str(self.install))
        self.click(QWizard.WizardButton.NextButton)
        self.assertEqual(self.wizard.currentId(), 2)
        self.click(QWizard.WizardButton.FinishButton)
        self.assertEqual(self.wizard.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(before, self.inventory())

    def test_missing_or_conflicting_install_cannot_finish_and_can_retry(self):
        service = mock.Mock()
        service.inspect.side_effect = [Installation(state='missing', message='未找到唯一安装'),
                                       Installation(path=str(self.install), state='original', can_patch=True)]
        self.open(service)
        self.click(QWizard.WizardButton.NextButton)
        self.wait_idle()
        service.inspect.assert_called_with(None)
        self.assertFalse(self.wizard.button(QWizard.WizardButton.NextButton).isEnabled())
        self.assertEqual(self.wizard.selected_path, '')
        self.click(QWizard.WizardButton.BackButton)
        self.wizard.choose_page.path_edit.setText(str(self.install))
        self.click(QWizard.WizardButton.NextButton)
        self.wait_idle()
        service.inspect.assert_called_with(str(self.install))
        self.assertTrue(self.wizard.button(QWizard.WizardButton.NextButton).isEnabled())

    def test_worker_is_off_gui_thread_and_busy_close_cannot_destroy_it(self):
        release = threading.Event()
        observed_thread = []
        def inspect(_):
            observed_thread.append(threading.get_ident())
            release.wait(5)
            return Installation(path=str(self.install), state='original', can_patch=True)
        service = mock.Mock()
        service.inspect.side_effect = inspect
        self.open(service, str(self.install))
        self.click(QWizard.WizardButton.NextButton)
        try:
            self.assertTrue(self.wizard.busy)
            for button in (QWizard.WizardButton.NextButton, QWizard.WizardButton.BackButton,
                           QWizard.WizardButton.CancelButton):
                self.assertFalse(self.wizard.button(button).isEnabled())
            event = QCloseEvent()
            self.wizard.closeEvent(event)
            self.assertFalse(event.isAccepted())
            self.wizard.reject()
            self.assertTrue(self.wizard.isVisible())
        finally:
            release.set()
        self.wait_idle()
        self.assertNotEqual(observed_thread[0], threading.get_ident())
        self.assertTrue(self.wizard.button(QWizard.WizardButton.BackButton).isEnabled())
        self.assertTrue(self.wizard.button(QWizard.WizardButton.CancelButton).isEnabled())

    def test_empty_worker_exception_is_displayed_and_does_not_enable_next(self):
        service = mock.Mock()
        service.inspect.side_effect = RuntimeError()
        self.open(service)
        self.click(QWizard.WizardButton.NextButton)
        self.wait_idle()
        self.assertFalse(self.wizard.inspect_page.isComplete())
        self.assertIn('未完成', self.wizard.inspect_page.details.toPlainText())
        self.assertEqual(self.wizard.selected_path, '')


if __name__ == '__main__':
    unittest.main()
