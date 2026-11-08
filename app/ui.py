"""Native Windows application shell. Business mutations run in one worker."""
import json
import hashlib
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QStackedWidget, QComboBox, QCheckBox, QPlainTextEdit,
    QFileDialog, QProgressBar, QGridLayout, QMessageBox)

from .dictionary import DictionaryStore
from .storage import load_settings, save_settings, data_directory
from .services import AppService
from .workers import Task
from .theme import Artwork, apply_theme, high_contrast
from .widgets import label, button, row, card, scroll, error, confirm
from .dictionary_view import DictionaryPage
from .onboarding import InstallationWizard

STATE_NAMES = {'original': '英文原版', 'localized': '已汉化', 'conflict': '归档冲突，需处理',
               'invalid': '文件检查未通过', 'missing': '尚未找到安装'}
ACTION_NAMES = {'patch': '应用汉化', 'restore': '恢复英文', 'proxy_preview': '代理修复预览',
    'proxy_setup': '修复代理启动', 'proxy_remove_preview': '移除代理预览',
    'proxy_remove': '移除代理启动', 'launch': '启动 Antigravity'}


class MainWindow(QMainWindow):
    def __init__(self, data_dir=None, app_dir=None, autoload=True):
        super().__init__()
        self.data_dir = Path(data_dir) if data_dir else data_directory()
        self.settings_error = ''
        try:
            self.settings = load_settings(self.data_dir)
        except (OSError, ValueError) as exc:
            self.settings = {}
            self.settings_error = str(exc)
        self.store = DictionaryStore(self.data_dir)
        self.service = AppService(self.data_dir)
        self.installation = None
        self.path = str(app_dir or self.settings.get('app_dir', ''))
        self.first_run_pending = autoload and not self.path
        self.task = None
        self.busy = False
        self.preview_action = None
        self.setWindowTitle('Antigravity 中文助手')
        self.setMinimumSize(620, 420)
        available = QApplication.primaryScreen().availableGeometry()
        size = self.settings.get('window_size', [1280, 820])
        if not isinstance(size, list) or len(size) != 2 or not all(isinstance(n, int) for n in size):
            size = [1280, 820]
        self.resize(min(max(720, size[0]), int(available.width()*.92)),
                    min(max(480, size[1]), int(available.height()*.92)))
        self.background = Artwork()
        self.setCentralWidget(self.background)
        outer = QHBoxLayout(self.background)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.sidebar = QWidget()
        self.sidebar.setObjectName('sidebar')
        nav_layout = QVBoxLayout(self.sidebar)
        nav_layout.setContentsMargins(16, 28, 16, 20)
        nav_layout.setSpacing(10)
        self.brand = label('ANTIGRAVITY\n中文助手', 'heading')
        nav_layout.addWidget(self.brand)
        nav_layout.addSpacing(28)
        self.nav_buttons = []
        self.nav_names = ['概览', '翻译词典', '代理启动', '恢复与帮助']
        for index, name in enumerate(self.nav_names):
            btn = button(name, lambda checked=False, i=index: self.navigate(i), 'nav')
            btn.setCheckable(True)
            btn.setToolTip(name)
            self.nav_buttons.append(btn)
            nav_layout.addWidget(btn)
        nav_layout.addStretch()
        self.nav_note = label('本地运行\n你的译文，由你决定。', 'muted')
        nav_layout.addWidget(self.nav_note)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem('跟随系统', 'system')
        self.theme_combo.addItem('浅色 · 日间', 'light')
        self.theme_combo.addItem('深色 · 夜间', 'dark')
        self.theme_combo.setAccessibleName('外观主题')
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(self.settings.get('theme', 'system'))))
        nav_layout.addWidget(self.theme_combo)
        outer.addWidget(self.sidebar)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self.pages = QStackedWidget()
        right_layout.addWidget(self.pages, 1)
        outer.addWidget(right, 1)
        self._overview()
        self.dictionary_page = DictionaryPage(self.store)
        self.pages.addWidget(self.dictionary_page)
        self.dictionary_page.saved.connect(self.update_dictionary_status)
        self._proxy()
        self._help()
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        right_layout.addWidget(self.progress)
        self.activity = label('准备就绪', 'muted')
        self.activity.setContentsMargins(24, 10, 24, 10)
        right_layout.addWidget(self.activity)
        self.theme_combo.currentIndexChanged.connect(self.change_appearance)
        QApplication.styleHints().colorSchemeChanged.connect(self.change_appearance)
        self.change_appearance(save=False)
        self.navigate(0)
        self.update_dictionary_status()
        if self.store.error:
            self.activity.setText('用户词典损坏，原文件已保留。请到“恢复与帮助”重新导入。')
        if autoload:
            QTimer.singleShot(0, self.refresh_installation)

    def _page(self, title, subtitle):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(label(title, 'title'))
        layout.addWidget(label(subtitle, 'muted'))
        self.pages.addWidget(scroll(widget))
        return widget, layout

    def _overview(self):
        self.home, layout = self._page('你的中文工作台', '本地管理 · 安心修改 · 随时还原')
        self.hero = label('中文界面，\n从这里开始。', 'hero')
        layout.addWidget(self.hero)
        layout.addSpacing(8)
        self.home_content = QWidget()
        content = QVBoxLayout(self.home_content)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(16)
        installation, info = card('Antigravity 安装')
        self.install_label = label('正在等待检查…')
        self.path_label = label('选择安装后，检查文件结构与原版归档。', 'muted')
        info.addWidget(self.install_label)
        info.addWidget(self.path_label)
        info.addLayout(row(button('选择安装', self.choose_installation), button('重新检查', self.refresh_installation)))
        self.compatibility = label('', 'muted')
        info.addWidget(self.compatibility)
        content.addWidget(installation)
        self.pending = label('')
        content.addWidget(self.pending)
        self.cards = QGridLayout()
        self.cards.setSpacing(16)
        self.local_card, local = card('界面汉化')
        self.local_state = label('尚未检查')
        local.addWidget(self.local_state)
        local.addWidget(label('完整验证原版归档，在暂存目录生成中文界面。', 'muted'))
        self.patch_button = button('预览并应用汉化', self.patch, 'primary')
        self.patch_button.setEnabled(False)
        local.addWidget(self.patch_button)
        local.addWidget(button('编辑词典', lambda: self.navigate(1)))
        self.proxy_card, proxy = card('代理启动')
        self.proxy_state = label('尚未检查')
        proxy.addWidget(self.proxy_state)
        proxy.addWidget(label('读取系统代理，修复启动入口。配置状态与网络连通性分别判断。', 'muted'))
        proxy.addWidget(button('检查代理启动', lambda: self.navigate(2)))
        self.cards.addWidget(self.local_card, 0, 0)
        self.cards.addWidget(self.proxy_card, 0, 1)
        content.addLayout(self.cards)
        result, result_layout = card('最近操作')
        self.result_label = label('尚无操作。检测安装不会修改任何安装文件。', 'muted')
        result_layout.addWidget(self.result_label)
        result_layout.addLayout(row(button('查看会话详情', lambda: self.navigate(3)), button('启动 Antigravity', lambda: self.execute('launch'))))
        content.addWidget(result)
        content.addStretch()
        layout.addWidget(self.home_content)
        layout.addStretch()

    def _proxy(self):
        _, layout = self._page('代理启动', '预览入口变化，再执行修复。代理客户端仍由你自行管理。')
        frame, detail = card('当前配置')
        self.system_proxy = label('尚未读取系统代理 · 未测试连接')
        self.proxy_install = label('选择安装后检查代理启动文件。', 'muted')
        detail.addWidget(self.system_proxy)
        detail.addWidget(self.proxy_install)
        detail.addWidget(label('不修改全局系统代理。PAC、纯 SOCKS 等配置不属于此工具的自动修复范围。', 'muted'))
        layout.addWidget(frame)
        frame, detail = card('快捷方式与其他位置')
        detail.addWidget(label('默认检查桌面、开始菜单等位置。其他快捷方式目录每行填写一个；不填写则使用默认位置。', 'muted'))
        self.scan_roots = QPlainTextEdit()
        self.scan_roots.setMaximumHeight(100)
        self.scan_roots.setAccessibleName('其他快捷方式扫描目录，每行一个')
        detail.addWidget(self.scan_roots)
        self.scan_roots.textChanged.connect(self.invalidate_preview)
        detail.addWidget(button('添加扫描目录', self.add_scan_root))
        detail.addLayout(row(button('预览修复', lambda: self.execute('proxy_preview')),
                             button('预览移除', lambda: self.execute('proxy_remove_preview'))))
        self.proxy_plan = QPlainTextEdit()
        self.proxy_plan.setReadOnly(True)
        self.proxy_plan.setMinimumHeight(180)
        self.proxy_plan.setAccessibleName('代理快捷方式预览详情')
        self.proxy_plan.setPlaceholderText('预览后在这里显示将处理的快捷方式、启动文件与错误。')
        detail.addWidget(self.proxy_plan)
        self.proxy_execute = button('请先预览操作', self.apply_proxy, 'primary')
        self.proxy_execute.setEnabled(False)
        detail.addWidget(self.proxy_execute)
        layout.addWidget(frame)
        layout.addStretch()

    def _help(self):
        _, layout = self._page('恢复与帮助', '保留你的词典，清楚了解每一步。')
        frame, detail = card('恢复英文界面')
        self.restore_state = label('选择安装后检查恢复来源。')
        detail.addWidget(self.restore_state)
        detail.addWidget(label('恢复英文与移除代理启动是两个独立操作。恢复英文不会删除你的自定义词典，也不会自动启动 Antigravity。', 'muted'))
        self.restore_button = button('预览并恢复英文', self.restore, 'danger')
        self.restore_button.setEnabled(False)
        detail.addWidget(self.restore_button)
        layout.addWidget(frame)
        frame, detail = card('当前会话与诊断')
        self.session = QPlainTextEdit()
        self.session.setReadOnly(True)
        self.session.setMinimumHeight(150)
        self.session.setAccessibleName('当前会话操作详情')
        detail.addWidget(self.session)
        detail.addWidget(button('导出脱敏诊断', self.export_diagnostics))
        detail.addWidget(label('详情仅保留在本次会话；导出报告过滤个人路径、代理地址及凭证。', 'muted'))
        layout.addWidget(frame)
        frame, detail = card('外观与本地数据')
        self.artwork_check = QCheckBox('显示日夜插画')
        self.artwork_check.setChecked(self.settings.get('artwork', True) is not False)
        detail.addWidget(self.artwork_check)
        detail.addWidget(label('文字大小'))
        self.font_combo = QComboBox()
        for text, scale in [('100%', 1.0), ('115%', 1.15), ('130%', 1.3)]:
            self.font_combo.addItem(text, scale)
        self.font_combo.setCurrentIndex(max(0, self.font_combo.findData(self.settings.get('font_scale', 1.0))))
        self.font_combo.setAccessibleName('文字大小')
        detail.addWidget(self.font_combo)
        detail.addWidget(label('主题'))
        help_theme = QComboBox()
        help_theme.setModel(self.theme_combo.model())
        help_theme.setCurrentIndex(self.theme_combo.currentIndex())
        help_theme.setAccessibleName('帮助页外观主题')
        help_theme.currentIndexChanged.connect(self.theme_combo.setCurrentIndex)
        self.theme_combo.currentIndexChanged.connect(help_theme.setCurrentIndex)
        detail.addWidget(help_theme)
        detail.addWidget(label('界面不使用过渡动画；系统高对比度模式优先，自动关闭插画。', 'muted'))
        self.storage_note = label(f'词典及偏好保存位置：{self.data_dir}', 'muted')
        detail.addWidget(self.storage_note)
        if self.store.error:
            detail.addWidget(label(self.store.error))
            detail.addWidget(button('从有效词典恢复', self.recover_dictionary))
        if self.settings_error:
            detail.addWidget(label('偏好文件无法读取，已保留原文件：' + self.settings_error))
        layout.addWidget(frame)
        frame, detail = card('使用前了解')
        detail.addWidget(label('1. 选择安装目录，检查归档与版本。\n2. 保存 Antigravity 中的工作，再预览并应用汉化。\n3. 完成后由你主动启动；修改词典后需要重新应用。'))
        detail.addWidget(label('文件结构通过不代表所有版本已验证兼容。缺少有效原版、出现归档冲突时，请先修复官方安装。代理修复完成后，完整退出 Antigravity，再从修复的入口启动。', 'muted'))
        detail.addWidget(label('Antigravity 中文助手 0.1.0 · Windows 测试版\n基于 MIMICTE / Antigravity-zh-CN，沿用 MIT 许可。PySide6 / Qt 为 LGPLv3 动态库；许可文件随包提供。', 'muted'))
        layout.addWidget(frame)
        layout.addStretch()
        self.artwork_check.toggled.connect(self.change_appearance)
        self.font_combo.currentIndexChanged.connect(self.change_appearance)

    def change_appearance(self, *args, save=True):
        self.background.theme = apply_theme(QApplication.instance(), self.theme_combo.currentData(), self.font_combo.currentData())
        self.background.enabled = self.artwork_check.isChecked()
        self.background.update()
        self.adjust_layout()
        if save:
            self.persist_settings()

    def persist_settings(self):
        # A malformed settings file is never silently overwritten.
        if self.settings_error:
            return
        self.settings.update(theme=self.theme_combo.currentData(), artwork=self.artwork_check.isChecked(),
                             font_scale=self.font_combo.currentData(), app_dir=self.path,
                             window_size=[self.width(), self.height()])
        try:
            save_settings(self.settings, self.data_dir)
        except (OSError, ValueError) as exc:
            self.activity.setText('偏好保存失败：' + str(exc))

    def navigate(self, index):
        if self.busy or self.pages.currentIndex() == 1 and index != 1 and not self.dictionary_page.maybe_leave():
            return
        self.pages.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.background.overview = index == 0
        self.background.update()
        if index == 2:
            self.run_task('读取系统代理', lambda progress: self.service.proxy_status(), self.render_proxy_status)

    def render_proxy_status(self, status):
        self.system_proxy.setText(str(status.get('label', '未识别')) + ' · ' + status.get('connection', '未测试连接'))

    def run_task(self, title, function, callback):
        if self.busy:
            return
        self.busy = True
        self.pages.setEnabled(False)
        self.sidebar.setEnabled(False)
        self.progress.show()
        self.activity.setText(title + '… 当前任务结束前请勿关闭窗口。')
        self._task_result = None
        self._task_error = None
        self.task = Task(function, self)
        self.task.progress.connect(self.activity.setText)
        self.task.completed.connect(lambda result: setattr(self, '_task_result', result))
        self.task.failed.connect(lambda message: setattr(self, '_task_error', message))
        def finished():
            self.busy = False
            self.pages.setEnabled(True)
            self.sidebar.setEnabled(True)
            self.progress.hide()
            self.task.deleteLater()
            self.task = None
            if self._task_error is not None:
                message = self._task_error or '任务异常退出，请重新检查安装并查看会话详情。'
                self.activity.setText('操作未完成：' + message)
                self.session.appendPlainText(title + '\n' + message)
            else:
                self.activity.setText(title + '完成')
                callback(self._task_result)
        self.task.finished.connect(finished)
        self.task.start()

    def choose_installation(self):
        path = QFileDialog.getExistingDirectory(self, '选择包含 Antigravity.exe 的安装目录', self.path)
        if path:
            self.path = path
            self.invalidate_preview()
            self.refresh_installation()

    def refresh_installation(self):
        self.run_task('检查安装与原版归档', lambda progress: self.service.inspect(self.path or None), self.render_installation)

    def render_installation(self, installation):
        self.installation = installation
        if installation.path:
            self.path = installation.path
            self.persist_settings()
        state = STATE_NAMES.get(installation.state, installation.state)
        self.install_label.setText(f'Antigravity · {installation.version} · {state}')
        self.path_label.setText(self.path or '未找到唯一安装。点击“选择安装”，指定包含 Antigravity.exe 的目录。')
        self.compatibility.setText(installation.message + ('\n' + '\n'.join(installation.warnings) if installation.warnings else ''))
        self.local_state.setText(state)
        proxy = {'absent': '未配置代理入口', 'installed': '代理启动文件已配置', 'incomplete': '代理启动文件不完整'}.get(installation.proxy, installation.proxy)
        self.proxy_state.setText(proxy + ' · 未测试连接')
        self.proxy_install.setText(proxy)
        self.patch_button.setEnabled(installation.can_patch and not self.store.error)
        self.restore_button.setEnabled(installation.can_restore)
        self.restore_state.setText('原版归档检查通过，可预览恢复。' if installation.can_restore else '当前不可恢复：' + installation.message)
        self.update_dictionary_status()
        if self.first_run_pending:
            self.first_run_pending = False
            if not installation.path or installation.state == 'missing':
                QTimer.singleShot(0, self.show_onboarding)

    def show_onboarding(self):
        wizard = InstallationWizard(self.service, self.path, self)
        if wizard.exec() == wizard.DialogCode.Accepted:
            self.path = wizard.selected_path
            self.refresh_installation()

    def update_dictionary_status(self):
        if self.store.error:
            text = '词典文件无法读取 · 原文件保留，请在帮助页从有效词典恢复'
        elif (self.installation and self.installation.state == 'localized'
              and self.installation.applied_revision == self.store.revision
              and self.installation.dictionary_hash == hashlib.sha256(json.dumps(
                  self.store.snapshot(), ensure_ascii=False, sort_keys=True, separators=(',', ':')
              ).encode('utf-8')).hexdigest()):
            text = f'当前词典修订 {self.store.revision} · 安装中已记录应用，界面效果请启动后核验'
        else:
            text = f'词典修订 {self.store.revision} · 已保存，尚未确认应用到当前安装'
        self.pending.setText(text)
        self.dictionary_page.pending.setText(text)

    def patch(self):
        if not self.installation or not self.installation.can_patch or self.store.error:
            return
        if confirm(self, '应用汉化预览', f'目标安装：{self.path}\n词典修订：{self.store.revision}\n\n将验证原版归档、暂存生成中文界面，再关闭所选 Antigravity 并切换安装文件。原版归档会保留；完成后不自动启动。\n\n请先保存 Antigravity 中的工作。', '已保存工作，应用汉化'):
            self.execute('patch')

    def restore(self):
        if self.installation and self.installation.can_restore and confirm(self, '恢复英文预览', f'目标安装：{self.path}\n\n将恢复当前安装的英文界面；你的自定义词典会保留。请先保存 Antigravity 中的工作。完成后不自动启动。', '已保存工作，恢复英文'):
            self.execute('restore')

    def execute(self, action):
        if not self.path:
            error(self, '请先在概览中选择 Antigravity 安装目录。')
            return
        roots = [line.strip() for line in self.scan_roots.toPlainText().splitlines() if line.strip()]
        try:
            snapshot = self.store.snapshot() if action == 'patch' else None
        except ValueError as exc:
            error(self, str(exc))
            return
        self.run_task(ACTION_NAMES[action], lambda progress: self.service.execute(action, self.path, overlays=snapshot,
                      scan_roots=roots, progress=progress), self.render_result)

    def render_result(self, result):
        status = {'success': '完成', 'partial': '部分完成', 'failed': '未完成', 'cancelled': '已取消'}.get(result.status, result.status)
        text = f"{datetime.now():%H:%M} · {ACTION_NAMES.get(result.action, result.action)} · {status}\n{result.message}\n{result.next_step}"
        self.result_label.setText(text)
        self.activity.setText(result.message)
        self.session.appendPlainText(text + '\n' + '\n'.join(result.details) + '\n')
        if result.installation:
            self.render_installation(result.installation)
        if result.action in ('proxy_preview', 'proxy_remove_preview'):
            self.proxy_plan.setPlainText(text + '\n\n' + '\n'.join(result.details))
            self.preview_action = ('proxy_setup' if result.action == 'proxy_preview' else 'proxy_remove') if result.ok else None
            self.proxy_execute.setText('确认修复代理入口' if self.preview_action == 'proxy_setup' else '确认移除代理入口' if self.preview_action else '请修正问题后重新预览')
            self.proxy_execute.setEnabled(self.preview_action is not None)
        elif result.action.startswith('proxy_'):
            self.proxy_plan.setPlainText(text + '\n\n' + '\n'.join(result.details))
            self.invalidate_preview()

    def invalidate_preview(self):
        self.preview_action = None
        self.proxy_execute.setEnabled(False)
        self.proxy_execute.setText('请先预览操作')

    def apply_proxy(self):
        if self.preview_action and confirm(self, '确认代理入口变化', '将按上方预览修改当前安装的启动文件及快捷方式。执行前会再次检查预览是否变化。\n\n不会修改全局代理，也不会关闭 Antigravity。', '执行已预览操作'):
            self.execute(self.preview_action)

    def add_scan_root(self):
        path = QFileDialog.getExistingDirectory(self, '选择额外快捷方式目录')
        if path:
            self.scan_roots.appendPlainText(path)

    def export_diagnostics(self):
        path, _ = QFileDialog.getSaveFileName(self, '导出脱敏诊断', 'antigravity-diagnostics.json', 'JSON (*.json)')
        if path:
            try:
                Path(path).write_text(json.dumps(self.service.diagnostics(), ensure_ascii=False, indent=2), encoding='utf-8')
                self.activity.setText('脱敏诊断已导出。')
            except OSError as exc:
                error(self, str(exc))

    def recover_dictionary(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择有效词典恢复', '', 'JSON (*.json)')
        if path and confirm(self, '恢复用户词典', '损坏原文件会另存保留，再用选择的有效词典恢复编辑。', '恢复词典'):
            try:
                self.store.recover_from_import(path)
                self.dictionary_page.refresh()
                self.update_dictionary_status()
                self.storage_note.setText('词典已恢复，损坏文件已另存保留。')
                if self.installation:
                    self.render_installation(self.installation)
            except (ValueError, OSError) as exc:
                error(self, str(exc))

    def adjust_layout(self):
        compact = self.width() < 900
        self.sidebar.setFixedWidth(100 if compact else 208)
        self.brand.setText('中文\n助手' if compact else 'ANTIGRAVITY\n中文助手')
        self.nav_note.setVisible(not compact)
        self.theme_combo.setVisible(not compact)
        for i, btn in enumerate(self.nav_buttons):
            btn.setText(['概览', '词典', '代理', '帮助'][i] if compact else self.nav_names[i])
        wide_art = self.width() >= 1280 and self.artwork_check.isChecked() and not high_contrast()
        self.home_content.setMaximumWidth(min(760, max(560, self.width()-208-340-48)) if wide_art else 980)
        single = self.home_content.width() < 600
        self.cards.addWidget(self.proxy_card, 1 if single else 0, 0 if single else 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'artwork_check'):
            self.adjust_layout()

    def closeEvent(self, event):
        if self.busy:
            self.activity.setText('任务仍在执行。为避免中断文件切换，请等待任务结束再关闭。')
            event.ignore()
        elif not self.dictionary_page.maybe_leave():
            event.ignore()
        else:
            self.persist_settings()
            event.accept()
