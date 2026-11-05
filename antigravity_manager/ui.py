"""PySide6 UI. All storage, installation and network work goes through a worker."""
import copy
import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QMainWindow,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .workers import ServiceTask


PROVIDER_LABELS = {'openai': 'OpenAI Responses', 'gemini': 'Gemini',
                   'claude': 'Claude', 'compatible': 'OpenAI Compatible'}
LIMITS = {
    'concurrency': ('并发请求', 1, 2), 'batchSize': ('每批条数', 1, 8),
    'batchCharacters': ('每批字符数', 1, 2000), 'textLength': ('单条长度', 1, 160),
    'timeoutMs': ('超时（毫秒）', 1000, 15000), 'requestsPerMinute': ('每分钟请求', 1, 12),
    'queueSize': ('队列上限', 1, 128), 'sessionRequests': ('本次会话请求上限', 1, 100),
}
ORIGINS = {'builtin': '内置', 'manual': '个人', 'accepted': '已采纳', 'legacy-ai': '历史 AI'}
STEP_LABELS = {'prepare': '准备并校验', 'validate': '校验归档', 'stop': '关闭目标应用',
               'activate': '切换安装文件', 'rollback': '回滚', 'cleanup': '清理暂存目录', 'launch': '启动应用'}
STEP_STATUSES = {'completed': '完成', 'incomplete': '未完成', 'requested': '已请求'}


def label(text):
    widget = QLabel(text)
    widget.setWordWrap(True)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget


def button(text, callback, layout):
    widget = QPushButton(text)
    widget.clicked.connect(callback)
    layout.addWidget(widget)
    return widget


def table(headers):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    widget.verticalHeader().setVisible(False)
    return widget


def fill_table(widget, rows):
    widget.setRowCount(0)
    widget.setRowCount(len(rows))
    for row, values in enumerate(rows):
        for col, value in enumerate(values):
            widget.setItem(row, col, QTableWidgetItem(str(value)))


class ManagerWindow(QMainWindow):
    def __init__(self, service, app_dir=None, autoload=True):
        super().__init__()
        self.service = service
        self.task = None
        self._callback = None
        self._close_pending = False
        self._loading = False
        self.config_draft = None
        self.config_dirty = False
        self.key_edits = {}
        self._provider = None
        self._last_status = None
        self.dictionary_revision = None
        self.candidates_revision = None
        self.pending_entries = []
        self.rejected_entries = []
        self.setWindowTitle('Antigravity 中文管理器 · DragonGirl')
        self.resize(1100, 780)
        self.setMinimumSize(880, 620)
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        self.navigation = QListWidget()
        self.navigation.addItems(['概览', '词典管理', '待确认译文', 'AI 设置', '代理与启动', '日志与诊断'])
        self.navigation.setFixedWidth(160)
        outer.addWidget(self.navigation)
        self.pages = QStackedWidget()
        outer.addWidget(self.pages, 1)
        self._overview_page(app_dir)
        self._dictionary_page()
        self._review_page()
        self._settings_page()
        self._proxy_page()
        self._diagnostics_page()
        self.navigation.currentRowChanged.connect(self._navigate)
        self.navigation.setCurrentRow(0)
        self.statusBar().showMessage('准备就绪')
        self.cleanup_timer = QTimer(self)
        self.cleanup_timer.setInterval(60000)
        self.cleanup_timer.timeout.connect(self._scheduled_cleanup)
        self.cleanup_timer.start()
        self.expiry_timer = QTimer(self)
        self.expiry_timer.setInterval(30000)
        self.expiry_timer.timeout.connect(self._refresh_expiries)
        self.expiry_timer.start()
        if autoload:
            QTimer.singleShot(0, lambda: self.refresh_status(after=self.load_config))

    def _page(self, title, subtitle):
        page = QWidget()
        layout = QVBoxLayout(page)
        title_label = label(title)
        font = title_label.font()
        font.setPointSize(19)
        font.setBold(True)
        title_label.setFont(font)
        layout.addWidget(title_label)
        layout.addWidget(label(subtitle))
        self.pages.addWidget(page)
        return layout

    def _overview_page(self, app_dir):
        layout = self._page('概览', '选择 Antigravity 安装，检查兼容状态并管理翻译组件。')
        row = QHBoxLayout()
        self.app_path = QLineEdit(app_dir or '')
        self.app_path.setPlaceholderText('Antigravity 安装目录；留空使用自动检测')
        self.app_path.setAccessibleName('Antigravity 安装目录')
        row.addWidget(self.app_path, 1)
        button('选择目录', self._choose_app, row)
        button('检查状态', self.refresh_status, row)
        layout.addLayout(row)
        self.overview = QPlainTextEdit()
        self.overview.setReadOnly(True)
        self.overview.setPlainText('尚未检查安装状态。')
        layout.addWidget(self.overview, 1)
        self.operation_result = label('')
        layout.addWidget(self.operation_result)
        actions = QHBoxLayout()
        button('应用汉化', lambda: self._install('apply'), actions)
        button('还原英文', lambda: self._install('restore'), actions)
        button('启动 Antigravity', self._launch, actions)
        layout.addLayout(actions)
        layout.addWidget(label('汉化和还原前请保存工作并退出目标应用。配置保存、API 连接、版本兼容与组件安装分别检查；关闭管理器不会关闭 Antigravity。'))

    def _dictionary_page(self):
        layout = self._page('词典管理', '个人词条优先于内置词典。导出仅包含个人词条，不含提供商配置或密钥。')
        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText('搜索原文或译文')
        self.query.returnPressed.connect(self.load_dictionary)
        row.addWidget(self.query, 1)
        button('搜索 / 刷新', self.load_dictionary, row)
        button('导入 JSON', self._import_dictionary, row)
        button('导出 JSON', self._export_dictionary, row)
        layout.addLayout(row)
        self.dictionary_table = table(['原文', '译文', '来源'])
        self.dictionary_table.itemSelectionChanged.connect(self._select_dictionary)
        layout.addWidget(self.dictionary_table, 1)
        form = QFormLayout()
        self.source = QLineEdit()
        self.translation = QLineEdit()
        form.addRow('原文', self.source)
        form.addRow('个人译文', self.translation)
        layout.addLayout(form)
        row = QHBoxLayout()
        button('保存个人词条', self._save_entry, row)
        button('恢复默认 / 删除个人词条', self._restore_entry, row)
        layout.addLayout(row)

    def _review_page(self):
        layout = self._page('待确认译文', '候选从首次生成起保留 7 天。采纳后进入个人词典；拒绝后不会再次补译，直到解除。')
        row = QHBoxLayout()
        button('刷新列表', self.load_pending, row)
        button('清理过期候选', lambda: self.run_action('cleanup', self._cleaned), row)
        layout.addLayout(row)
        self.pending_table = table(['原文', '候选译文', '剩余期限 / 到期时间（本地）'])
        self.pending_table.itemSelectionChanged.connect(self._select_pending)
        layout.addWidget(self.pending_table, 2)
        form = QFormLayout()
        self.review_source = QLineEdit()
        self.review_source.setReadOnly(True)
        self.review_translation = QLineEdit()
        form.addRow('原文', self.review_source)
        form.addRow('采纳译文（可编辑）', self.review_translation)
        layout.addLayout(form)
        row = QHBoxLayout()
        button('采纳译文', lambda: self._review('accept'), row)
        button('拒绝', lambda: self._review('reject'), row)
        layout.addLayout(row)
        layout.addWidget(label('已拒绝的原文'))
        self.rejected_table = table(['原文', '拒绝时间'])
        layout.addWidget(self.rejected_table, 1)
        row = QHBoxLayout()
        button('解除所选拒绝', self._unblock, row)
        layout.addLayout(row)

    def _settings_page(self):
        layout = self._page('AI 设置', '密钥由 Windows 当前用户保护。留空表示保留已保存密钥，只有“清除密钥”会删除它。')
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        self.enabled = QCheckBox('允许对受支持的界面文案发送新 AI 请求')
        self.enabled.toggled.connect(self._dirty)
        form.addRow(self.enabled)
        self.provider = QComboBox()
        for name, text in PROVIDER_LABELS.items():
            self.provider.addItem(text, name)
        self.provider.currentIndexChanged.connect(self._switch_provider)
        form.addRow('提供商协议', self.provider)
        self.base_url = QLineEdit()
        self.model = QLineEdit()
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText('输入新密钥以替换；留空保留')
        self.key_status = label('尚未加载')
        for field in (self.base_url, self.model, self.api_key):
            field.textEdited.connect(self._dirty)
        self.clear_key = QCheckBox('清除该提供商的已保存密钥')
        self.clear_key.toggled.connect(self._clear_key_changed)
        form.addRow('API Base URL（HTTPS）', self.base_url)
        form.addRow('模型', self.model)
        form.addRow('新密钥', self.api_key)
        form.addRow('密钥状态', self.key_status)
        form.addRow(self.clear_key)
        self.limit_inputs = {}
        for name, (caption, low, high) in LIMITS.items():
            spin = QSpinBox()
            spin.setRange(low, high)
            spin.valueChanged.connect(self._dirty)
            self.limit_inputs[name] = spin
            form.addRow(caption, spin)
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)
        self.config_hint = label('尚未加载配置。')
        layout.addWidget(self.config_hint)
        row = QHBoxLayout()
        button('重新加载', self._reload_config, row)
        button('保存配置', self._save_config, row)
        button('测试已保存配置', self._probe, row)
        layout.addLayout(row)

    def _proxy_page(self):
        layout = self._page('代理与启动', '代理快捷方式管理将在 M4 接入。')
        layout.addWidget(label('M3 可在概览中启动应用。系统代理识别、端口连通和 API 测试是不同状态；API 测试可在 AI 设置页主动执行。'))
        layout.addWidget(label('当前页面尚不提供快捷方式扫描、启用或移除功能。'))
        layout.addStretch()

    def _diagnostics_page(self):
        layout = self._page('日志与诊断', '仅记录本次管理器会话的时间、操作与结果代码，不记录密钥或 API 响应正文。')
        row = QHBoxLayout()
        button('刷新诊断', lambda: self.run_action('diagnostics', self._show_diagnostics), row)
        layout.addLayout(row)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)

    def run_action(self, action, callback=None, **kwargs):
        if self.task is not None:
            return False
        self.pages.setEnabled(False)
        self.navigation.setEnabled(False)
        self.statusBar().showMessage('正在处理，请稍候…')
        self._callback = callback
        self.task = ServiceTask(self.service, action, kwargs, self)
        self.task.finished.connect(self._task_finished)
        self.task.start()
        return True

    def _task_finished(self):
        task = self.task
        result = task.result or {'ok': False, 'message': '操作未返回结果。'}
        callback = self._callback
        self.task = None
        self._callback = None
        task.deleteLater()
        self.pages.setEnabled(True)
        self.navigation.setEnabled(True)
        message = result.get('message') or ('操作完成。' if result.get('ok') else '操作失败，请检查诊断。')
        self.statusBar().showMessage(message)
        if self._close_pending:
            self._close_pending = False
            if result.get('ok'):
                if task.action == 'save-config':
                    self._show_config(result)
                self.close()
                return
        if callback:
            callback(result)
        if not result.get('ok'):
            QMessageBox.warning(self, '操作未完成', message)

    def _navigate(self, index):
        self.pages.setCurrentIndex(index)
        if index == 1 and self.dictionary_revision is None:
            self.load_dictionary()
        elif index == 2 and self.candidates_revision is None:
            self.load_pending()
        elif index == 3 and self.config_draft is None:
            self.load_config()
        elif index == 5:
            self.run_action('diagnostics', self._show_diagnostics)

    def _confirm(self, title, text):
        return QMessageBox.question(self, title, text, QMessageBox.StandardButton.Yes |
                                    QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def _choose_app(self):
        directory = QFileDialog.getExistingDirectory(self, '选择 Antigravity 安装目录', self.app_path.text())
        if directory:
            self.app_path.setText(directory)
            self.refresh_status()

    def refresh_status(self, checked=False, after=None):
        def done(result):
            self._show_status(result)
            if after:
                after()
        self.run_action('status', done, app_dir=self.app_path.text().strip() or None)

    def _show_status(self, result):
        self._last_status = copy.deepcopy(result)
        install = result.get('installation') or {}
        if install.get('path') and not self.app_path.text().strip():
            self.app_path.setText(install['path'])
        names = [('path', '安装目录'), ('version', '版本'), ('compatibility', '兼容状态'),
                 ('component', '组件状态'), ('running', '运行状态')]
        statuses = {'unavailable': '不可用', 'unknown': '未知', 'matched': '已匹配',
                    'unsupported': '未支持', 'installed': '已安装', 'not_installed': '未安装',
                    'verified': '已校验', 'modified': '已变化', 'ready': '可用',
                    'outdated': '需要更新', 'invalid': '校验失败', 'static_only': '仅静态汉化',
                    'not_tested': '未测试', 'connected': '测试成功',
                    'authentication_failed': '认证失败', 'rate_limited': '限流或额度不足',
                    'provider_unavailable': '提供商暂不可用', 'provider_rejected': '提供商拒绝请求',
                    'invalid_response': '响应无效', 'timeout': '测试超时', 'cancelled': '已取消',
                    'network_error': '网络错误', 'invalid_configuration': '配置无效',
                    'configuration_changed': '配置已变化，需重新测试', 'invalid_endpoint': '地址不受支持',
                    'unsafe_endpoint': '域名未解析到公网', 'proxy_configuration_error': '代理配置错误',
                    'proxy_connection_failed': '代理连接失败', 'proxy_authentication_required': '代理要求认证'}
        text = [f'{caption}：{statuses.get(install.get(key), install.get(key, "未知"))}' for key, caption in names]
        configuration_status = result.get('configurationStatus', '未知')
        text.append('配置状态：' + statuses.get(configuration_status, configuration_status))
        if 'config' in result:
            text.append('AI 新请求：' + ('已启用' if result['config']['enabled'] else '已关闭'))
        connection = result.get('connection', {}).get('status', 'not_tested')
        text.append('API 连接：' + statuses.get(connection, connection))
        text.append('运行连接：未主动探测；安装或进程存在不代表桥接已连接。')
        if result.get('message'):
            text.append(result['message'])
        self.overview.setPlainText('\n\n'.join(text))

    def _install(self, action):
        target = self.app_path.text().strip()
        if not target:
            QMessageBox.information(self, '选择目标', '请先选择明确的安装目录，再执行汉化或还原。')
            return
        caption = '应用汉化' if action == 'apply' else '还原英文'
        if self._confirm(caption, f'目标目录：{target}\n\n请保存工作并退出此安装的 Antigravity。确认执行{caption}？'):
            self.run_action(action, self._install_finished, app_dir=target, confirmed=True)

    def _install_finished(self, result):
        details = [result.get('message', '操作完成。' if result.get('ok') else '操作未完成。')]
        if 'filesChanged' in result:
            details.append('安装文件已变化' if result['filesChanged'] else '安装文件未变化')
        if result.get('restartRequired'):
            details.append('下次启动目标应用后生效')
        if result.get('steps'):
            details.extend(self._format_steps(result['steps']))
        self.operation_result.setText('\n'.join(details))
        if result.get('ok'):
            self.refresh_status()

    def _launch(self):
        self.run_action('launch', self._install_finished, app_dir=self.app_path.text().strip() or None)

    def load_dictionary(self):
        self.run_action('list', self._show_dictionary, query=self.query.text())

    def _show_dictionary(self, result):
        if not result.get('ok'):
            return
        self.dictionary_revision = result['dictionaryRevision']
        fill_table(self.dictionary_table, [(x['original'], x['translation'], ORIGINS.get(x['source'], x['source']))
                                          for x in result['entries']])
        # A refreshed revision must never silently authorize an old editor draft.
        self.source.clear()
        self.translation.clear()

    def _select_dictionary(self):
        row = self.dictionary_table.currentRow()
        if row >= 0 and self.dictionary_table.item(row, 0):
            self.source.setText(self.dictionary_table.item(row, 0).text())
            self.translation.setText(self.dictionary_table.item(row, 1).text())

    def _dictionary_changed(self, result):
        if result.get('ok'):
            self.candidates_revision = None
            self.load_dictionary()

    def _save_entry(self):
        self.run_action('set', self._dictionary_changed, source=self.source.text(),
                        translation=self.translation.text(), revision=self.dictionary_revision)

    def _restore_entry(self):
        if self._confirm('恢复默认', '移除此原文的个人词条，恢复内置译文或英文原文？'):
            self.run_action('restore-default', self._dictionary_changed, source=self.source.text(),
                            revision=self.dictionary_revision)

    def _import_dictionary(self):
        path, _ = QFileDialog.getOpenFileName(self, '导入个人词典', '', 'JSON (*.json)')
        if path and self._confirm('导入词典', '将导入文件中的词条合并为个人词条；相同原文会覆盖当前个人译文。继续？'):
            self.run_action('import-dictionary', self._dictionary_changed, path=path, revision=self.dictionary_revision)

    def _export_dictionary(self):
        path, _ = QFileDialog.getSaveFileName(self, '导出个人词典', 'personal-dictionary-export.json', 'JSON (*.json)')
        if path:
            self.run_action('export-dictionary', path=path)

    def load_pending(self):
        self.run_action('pending', self._show_pending)

    def _show_pending(self, result):
        if not result.get('ok'):
            return
        self.candidates_revision = result['candidatesRevision']
        self.pending_entries = result['entries']
        self.rejected_entries = result['rejected']
        fill_table(self.pending_table, [(x['original'], x['translation'], self._expiry(x['expiresAt']))
                                       for x in self.pending_entries])
        self.pending_table.resizeRowsToContents()
        fill_table(self.rejected_table, [(x['original'], self._date(x.get('rejectedAt')))
                                        for x in self.rejected_entries])
        self.review_source.clear()
        self.review_translation.clear()

    @staticmethod
    def _date(value):
        if isinstance(value, (int, float)):
            try:
                return datetime.datetime.fromtimestamp(value / 1000).strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, OSError, OverflowError):
                return '未知'
        return str(value or '—')

    def _expiry(self, value):
        seconds = max(0, int(value / 1000 - datetime.datetime.now().timestamp()))
        remaining = f'{seconds // 86400} 天 {(seconds % 86400) // 3600} 小时' if seconds else '已到期'
        return remaining + '\n' + self._date(value)

    def _refresh_expiries(self):
        for row, item in enumerate(self.pending_entries):
            cell = self.pending_table.item(row, 2)
            if cell:
                cell.setText(self._expiry(item['expiresAt']))

    def _select_pending(self):
        row = self.pending_table.currentRow()
        if 0 <= row < len(self.pending_entries):
            item = self.pending_entries[row]
            self.review_source.setText(item['original'])
            self.review_translation.setText(item['translation'])

    def _review(self, action):
        kwargs = dict(source=self.review_source.text(), revision=self.candidates_revision)
        if action == 'accept':
            kwargs['translation'] = self.review_translation.text()
        self.run_action(action, self._reviewed, **kwargs)

    def _unblock(self):
        row = self.rejected_table.currentRow()
        if 0 <= row < len(self.rejected_entries):
            self.run_action('unblock', self._reviewed, source=self.rejected_entries[row]['original'],
                            revision=self.candidates_revision)

    def _reviewed(self, result):
        if result.get('ok'):
            self.dictionary_revision = None
            self.load_pending()

    def _cleaned(self, result):
        if result.get('ok'):
            self.load_pending()

    def _scheduled_cleanup(self):
        # Do not refresh visible rows: that would destroy an edited translation.
        if self.task is None and not self._close_pending:
            self.run_action('cleanup')

    def load_config(self):
        self.run_action('config', self._show_config)

    def _reload_config(self):
        if not self.config_dirty or self._confirm('重新加载', '放弃未保存的 AI 设置并读取当前配置？'):
            self.load_config()

    def _show_config(self, result):
        if not result.get('ok'):
            return
        self._loading = True
        self.config_draft = copy.deepcopy(result['config'])
        self.key_edits = {}
        self.enabled.setChecked(self.config_draft['enabled'])
        self.provider.setCurrentIndex(self.provider.findData(self.config_draft['provider']))
        self._provider = self.config_draft['provider']
        for name, spin in self.limit_inputs.items():
            spin.setValue(self.config_draft['limits'][name])
        self._load_profile()
        self._loading = False
        self.config_dirty = False
        self.config_hint.setText('已加载配置；API 测试只使用已保存的版本。')
        if self._last_status is not None:
            status = copy.deepcopy(self._last_status)
            status['configurationStatus'] = 'ready'
            status['config'] = {key: self.config_draft[key] for key in ('enabled', 'provider', 'revision')}
            if status.get('connection', {}).get('revision') != self.config_draft['revision']:
                status['connection'] = {'status': 'not_tested', 'revision': None}
            self._show_status(status)

    def _dirty(self, *_):
        if not self._loading:
            self.config_dirty = True
            self.config_hint.setText('存在未保存的设置。请保存后再测试连接。')

    def _capture_profile(self):
        if self.config_draft is None or self._provider is None:
            return
        profile = self.config_draft['providers'][self._provider]
        profile.update(baseUrl=self.base_url.text(), model=self.model.text())
        if self.clear_key.isChecked():
            self.key_edits[self._provider] = ''
        elif self.api_key.text():
            self.key_edits[self._provider] = self.api_key.text()
        else:
            self.key_edits.pop(self._provider, None)

    def _switch_provider(self, *_):
        if self._loading or self.config_draft is None:
            return
        self._capture_profile()
        self._provider = self.provider.currentData()
        self.config_draft['provider'] = self._provider
        self._loading = True
        self._load_profile()
        self._loading = False
        self._dirty()

    def _load_profile(self):
        profile = self.config_draft['providers'][self._provider]
        self.base_url.setText(profile['baseUrl'])
        self.model.setText(profile['model'])
        self.api_key.setText(self.key_edits.get(self._provider, ''))
        self.clear_key.setChecked(self._provider in self.key_edits and self.key_edits[self._provider] == '')
        self.api_key.setEnabled(not self.clear_key.isChecked())
        self.key_status.setText('已保存密钥（内容不回显）' if profile['hasKey'] else '尚未保存密钥')

    def _clear_key_changed(self, checked):
        self.api_key.setEnabled(not checked)
        self._dirty()

    def _save_config(self):
        if self.config_draft is None:
            return
        self._capture_profile()
        self.config_draft['enabled'] = self.enabled.isChecked()
        self.config_draft['limits'] = {name: spin.value() for name, spin in self.limit_inputs.items()}
        self.run_action('save-config', self._show_config, config=copy.deepcopy(self.config_draft),
                        revision=self.config_draft['revision'], keys=dict(self.key_edits))

    def _probe(self):
        if self.config_draft is None:
            return
        if self.config_dirty:
            QMessageBox.information(self, '先保存配置', '请保存或重新加载配置后，再测试连接。')
            return
        if self._confirm('测试连接', '将使用已保存的提供商、模型和密钥发送固定测试文案，可能产生费用。继续？'):
            self.run_action('probe', self._probed, revision=self.config_draft['revision'], confirmed=True)

    def _probed(self, result):
        self.config_hint.setText(result.get('message', '测试结束。'))
        if self._last_status is not None and result.get('connection'):
            status = copy.deepcopy(self._last_status)
            status['connection'] = copy.deepcopy(result['connection'])
            self._show_status(status)

    def _show_diagnostics(self, result):
        if result.get('ok'):
            lines = []
            for event in result['events']:
                lines.append(f"{event['time']}  {event['action']}  {'成功' if event['ok'] else '失败'}  {event['code']}")
                if event.get('message'):
                    lines.append(event['message'])
                if 'filesChanged' in event:
                    lines.append('安装文件已变化' if event['filesChanged'] else '安装文件未变化')
                if event.get('restartRequired'):
                    lines.append('下次启动目标应用后生效')
                lines.extend(self._format_steps(event.get('steps', [])))
            self.log.setPlainText('\n'.join(lines))

    @staticmethod
    def _format_steps(steps):
        return [STEP_LABELS.get(item.get('step'), '其他步骤') + '：' +
                STEP_STATUSES.get(item.get('status'), '未知状态') for item in steps]

    def closeEvent(self, event):
        if self.task is not None:
            self._close_pending = True
            self.statusBar().showMessage('正在完成当前操作，完成后关闭管理器。')
            event.ignore()
            return
        if self.config_dirty and not self._confirm('关闭管理器', 'AI 设置有未保存的修改。放弃修改并关闭？'):
            event.ignore()
            return
        self.cleanup_timer.stop()
        self.expiry_timer.stop()
        self.api_key.clear()
        self.key_edits.clear()
        event.accept()
