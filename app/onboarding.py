"""First-use guidance; every installation check is read-only and asynchronous."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
                              QLabel, QLineEdit, QPushButton, QFileDialog,
                              QPlainTextEdit, QProgressBar)

from .workers import Task


def _text(value):
    widget = QLabel(value)
    widget.setWordWrap(True)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget


class _ChoosePage(QWizardPage):
    def __init__(self, initial_path):
        super().__init__()
        self.setTitle('1 · 选择 Antigravity 安装')
        self.setSubTitle('找到需要管理的安装；你的词典保存在助手自己的数据目录。')
        layout = QVBoxLayout(self)
        layout.addWidget(_text('选择包含 Antigravity.exe 和 resources 的文件夹。留空可尝试自动查找；找到多个安装时，请选择其中一个。'))
        title = _text('安装目录')
        self.path_edit = QLineEdit(initial_path)
        self.path_edit.setPlaceholderText('留空自动查找，或选择安装目录')
        self.path_edit.setAccessibleName('Antigravity 安装目录')
        title.setBuddy(self.path_edit)
        layout.addWidget(title)
        row = QHBoxLayout()
        row.addWidget(self.path_edit, 1)
        self.browse = QPushButton('浏览…')
        self.browse.clicked.connect(self.choose)
        row.addWidget(self.browse)
        layout.addLayout(row)
        layout.addWidget(_text('下一步只读取并检查文件，不会汉化、还原或启动 Antigravity。'))
        layout.addStretch()

    def choose(self):
        directory = QFileDialog.getExistingDirectory(self, '选择 Antigravity 安装目录', self.path_edit.text())
        if directory:
            self.path_edit.setText(directory)


class _InspectPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.ready = False
        self.setTitle('2 · 检查安装状态')
        self.setSubTitle('校验原版归档和主入口，确认可执行的操作。')
        layout = QVBoxLayout(self)
        self.summary = _text('正在等待检查。')
        layout.addWidget(self.summary)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setAccessibleName('安装检查详情')
        self.details.setMinimumHeight(150)
        layout.addWidget(self.details)
        layout.addWidget(_text('检查不通过时，可返回选择其他安装。请保留现有归档与恢复目录。'))

    def initializePage(self):
        self.wizard().start_inspection()

    def isComplete(self):
        return self.ready


class _FinishPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle('3 · 准备开始')
        self.setSubTitle('完成引导后回到概览，由你选择具体操作。')
        layout = QVBoxLayout(self)
        self.selection = _text('')
        layout.addWidget(self.selection)
        layout.addWidget(_text('应用汉化或恢复英文前，先保存 Antigravity 中的工作。助手会在切换文件时关闭所选安装，完成后由你主动启动。'))
        layout.addWidget(_text('修改词典后，先保存，再重新应用汉化。代理启动有独立的预览、配置和移除入口；配置完成不代表网络连接已测试。'))
        layout.addStretch()

    def initializePage(self):
        self.selection.setText('已选择：' + self.wizard().selected_path)


class InstallationWizard(QWizard):
    def __init__(self, service, initial_path='', parent=None):
        super().__init__(parent)
        self.service = service
        self._selected_path = ''
        self.task = None
        self.busy = False
        self._result = None
        self._error = None
        self.setWindowTitle('欢迎使用 Antigravity 中文助手')
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(520, 400)
        self.resize(700, 520)
        self.setButtonText(QWizard.WizardButton.BackButton, '上一步')
        self.setButtonText(QWizard.WizardButton.NextButton, '下一步')
        self.setButtonText(QWizard.WizardButton.FinishButton, '完成引导')
        self.setButtonText(QWizard.WizardButton.CancelButton, '稍后再说')
        self.choose_page = _ChoosePage(str(initial_path or ''))
        self.inspect_page = _InspectPage()
        self.finish_page = _FinishPage()
        self.addPage(self.choose_page)
        self.addPage(self.inspect_page)
        self.addPage(self.finish_page)
        self.currentIdChanged.connect(self._sync_navigation)

    @property
    def selected_path(self):
        return self._selected_path

    def start_inspection(self):
        if self.busy:
            return
        self._selected_path = ''
        self._result = None
        self._error = None
        self.busy = True
        self.inspect_page.ready = False
        self.inspect_page.completeChanged.emit()
        self.inspect_page.summary.setText('正在检查文件，请稍候…')
        self.inspect_page.details.clear()
        self.inspect_page.progress.show()
        path = self.choose_page.path_edit.text().strip() or None
        self.task = Task(lambda progress: self.service.inspect(path), self)
        self.task.completed.connect(self._received)
        self.task.failed.connect(self._failed)
        self.task.finished.connect(self._finished)
        self.task.start()
        self._sync_navigation()

    def _sync_navigation(self, *_):
        self.button(QWizard.WizardButton.BackButton).setEnabled(not self.busy and self.currentId() > 0)
        self.button(QWizard.WizardButton.CancelButton).setEnabled(not self.busy)

    def _received(self, result):
        self._result = result

    def _failed(self, message):
        self._error = message or '检查未完成，请返回重新选择安装。'

    def _finished(self):
        self.busy = False
        task = self.task
        self.task = None
        task.deleteLater()
        page = self.inspect_page
        page.progress.hide()
        result = self._result
        if self._error is not None or result is None:
            page.summary.setText('安装检查未完成')
            page.details.setPlainText(self._error or '未收到检查结果，请返回重试。')
        else:
            usable = bool(result.path) and (result.can_patch or result.can_restore
                                           or result.state in ('original', 'localized'))
            page.ready = usable
            page.summary.setText('检查完成，可继续了解操作' if usable else '请返回选择安装或修复官方安装')
            lines = [result.path, '版本：' + result.version, result.message, *result.warnings]
            page.details.setPlainText('\n'.join(line for line in lines if line))
            if usable:
                self._selected_path = result.path
        page.completeChanged.emit()
        self._sync_navigation()

    def back(self):
        if self.busy:
            self.inspect_page.summary.setText('正在检查文件，完成后即可返回。')
            return
        super().back()

    def reject(self):
        if self.busy:
            self.inspect_page.summary.setText('正在检查文件，完成后即可关闭；本次检查不会修改安装。')
            return
        super().reject()

    def closeEvent(self, event):
        if self.busy:
            self.inspect_page.summary.setText('正在检查文件，完成后即可关闭；本次检查不会修改安装。')
            event.ignore()
        else:
            super().closeEvent(event)
