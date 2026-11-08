"""Searchable native table and responsive dictionary editor."""
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox,
    QTableView, QHeaderView, QAbstractItemView, QPlainTextEdit, QCheckBox,
    QSplitter, QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QTableWidget,
    QTableWidgetItem)
from .widgets import label, button, card, row, scroll, error, confirm

ORIGINS = {'builtin': '内置', 'custom': '自定义', 'override': '已修改'}


class EntryModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 3

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        entry = self.entries[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole, Qt.ItemDataRole.AccessibleTextRole):
            return [entry['source'], entry['target'],
                    ORIGINS.get(entry['origin'], entry['origin']) + (' · 已禁用' if not entry['enabled'] else '')][index.column()]

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ['英文原文', '中文译文', '来源 / 状态'][section]

    def set_entries(self, entries):
        self.beginResetModel()
        self.entries = entries
        self.endResetModel()


class DictionaryPage(QWidget):
    saved = Signal()

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.current = None
        self.dirty = False
        self.loading = False
        self.editing = False
        self._selected_key = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(label('翻译词典', 'title'))
        layout.addWidget(label('让常用表达，更合你的习惯。保存后重新应用汉化，译文才会生效。', 'muted'))
        self.pending = label('内置词典 · 可搜索和编辑普通文本')
        layout.addWidget(self.pending)
        self.search = QLineEdit()
        self.search.setPlaceholderText('搜索英文或中文…')
        self.search.setAccessibleName('搜索词典')
        self.scope_filter = QComboBox()
        self.scope_filter.addItems(['全部用途', '界面', '原生菜单'])
        self.scope_filter.setAccessibleName('用途筛选')
        self.origin_filter = QComboBox()
        self.origin_filter.addItems(['全部来源', '内置', '已修改 / 自定义', '已禁用'])
        self.origin_filter.setAccessibleName('来源筛选')
        layout.addLayout(row(self.search, self.scope_filter, self.origin_filter))
        layout.addLayout(row(button('添加词条', self.add_entry, 'primary'),
                             button('导入', self.import_file), button('导出', self.export_file),
                             button('规则说明', self.show_rules)))
        self.split = QSplitter()
        self.list_panel = QWidget()
        list_layout = QVBoxLayout(self.list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        self.model = EntryModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAccessibleName('翻译词条列表')
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(2, 110)
        list_layout.addWidget(self.table)
        self.count = label('', 'muted')
        list_layout.addWidget(self.count)
        self.split.addWidget(self.list_panel)
        editor, form = card('编辑词条')
        self.back = button('返回列表', self.back_to_list)
        form.addWidget(self.back)
        self.edit_status = label('选择一条词条，查看完整内容。', 'muted')
        form.addWidget(self.edit_status)
        self.scope = QComboBox()
        self.scope.addItem('界面文本', 'ui')
        self.scope.addItem('原生菜单', 'menu')
        self.source = QPlainTextEdit()
        self.source.setMinimumHeight(90)
        self.source.setMaximumHeight(120)
        self.target = QPlainTextEdit()
        self.target.setMinimumHeight(110)
        self.target.setMaximumHeight(150)
        for title, widget in [('用途', self.scope), ('原文（必填）', self.source), ('译文（必填）', self.target)]:
            title_label = label(title)
            title_label.setBuddy(widget)
            widget.setAccessibleName(title)
            form.addWidget(title_label)
            form.addWidget(widget)
        self.enabled = QCheckBox('启用此词条')
        self.enabled.setChecked(True)
        form.addWidget(self.enabled)
        self.original = label('', 'muted')
        form.addWidget(self.original)
        form.addWidget(label('按用途和完整原文匹配，保护代码、输入内容和用户正文。禁用后保留原文。', 'muted'))
        self.validation = label('')
        form.addWidget(self.validation)
        form.addWidget(button('保存修改', self.save_entry, 'primary'))
        form.addWidget(button('取消编辑', self.cancel_edit))
        form.addWidget(button('恢复内置 / 删除自定义', self.reset_entry))
        form.addStretch()
        self.editor = scroll(editor)
        self.editor.setMinimumWidth(300)
        self.split.addWidget(self.editor)
        self.split.setStretchFactor(0, 1)
        self.split.setSizes([600, 340])
        layout.addWidget(self.split, 1)
        self.table.selectionModel().currentRowChanged.connect(self.select_row)
        self.table.clicked.connect(self.reopen_editor)
        self.search.textChanged.connect(self.refresh)
        self.scope_filter.currentIndexChanged.connect(self.refresh)
        self.origin_filter.currentIndexChanged.connect(self.refresh)
        for field in (self.source, self.target):
            field.textChanged.connect(self.mark_dirty)
        self.scope.currentIndexChanged.connect(self.mark_dirty)
        self.enabled.toggled.connect(self.mark_dirty)
        QShortcut(QKeySequence.StandardKey.Save, self, activated=self.save_entry)
        QShortcut(QKeySequence.StandardKey.Find, self, activated=self.search.setFocus)
        self.refresh()
        self._load(None)

    def refresh(self, *args):
        query = self.search.text().casefold().strip()
        scope = ['', 'ui', 'menu'][self.scope_filter.currentIndex()]
        origin = self.origin_filter.currentIndex()
        entries = [entry for entry in self.store.entries()
                   if (not query or query in (entry['source'] + ' ' + entry['target']).casefold())
                   and (not scope or entry['scope'] == scope)
                   and (origin == 0 or origin == 1 and entry['origin'] == 'builtin'
                        or origin == 2 and entry['origin'] != 'builtin'
                        or origin == 3 and not entry['enabled'])]
        self.loading = True
        self.model.set_entries(entries)
        self.loading = False
        self.count.setText(f'共 {len(entries)} 条 · 界面与菜单分别匹配' if entries else '没有匹配词条。可点击“添加词条”，使用此原文新增。')

    def mark_dirty(self, *args):
        if not self.loading:
            self.dirty = True
            self.edit_status.setText('未保存 · 请保存修改或取消编辑')

    def _load(self, entry):
        self.loading = True
        self.current = entry
        self.scope.setCurrentIndex(1 if entry and entry['scope'] == 'menu' else 0)
        self.scope.setEnabled(entry is None)
        self.source.setReadOnly(entry is not None)
        self.source.setPlainText(entry['source'] if entry else '')
        self.target.setPlainText(entry['target'] if entry else '')
        self.enabled.setChecked(entry['enabled'] if entry else True)
        self.edit_status.setText(ORIGINS.get(entry['origin'], '') if entry else '新词条 · 填写完整原文和译文')
        builtin = self.store._builtin.get((entry['scope'], entry['source'])) if entry else None
        self.original.setText('内置译文：' + builtin['target'] if builtin else '')
        self.validation.clear()
        self.dirty = False
        self.loading = False

    def maybe_leave(self):
        if not self.dirty:
            return True
        box = QMessageBox(self)
        box.setWindowTitle('词条尚未保存')
        box.setText('是否保存当前词条的修改？')
        save = box.addButton('保存修改', QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton('放弃修改', QMessageBox.ButtonRole.DestructiveRole)
        stay = box.addButton('继续编辑', QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(stay)
        box.setEscapeButton(stay)
        box.exec()
        if box.clickedButton() is save:
            return self.save_entry()
        if box.clickedButton() is discard:
            self._load(self.current)
            return True
        return False

    def select_row(self, index, previous):
        if self.loading or not index.isValid():
            return
        entry = self.model.entries[index.row()]
        if not self.maybe_leave():
            self.loading = True
            self.table.setCurrentIndex(previous)
            self.loading = False
            return
        self._load(entry)
        self.editing = True
        self.adjust_layout()

    def add_entry(self):
        if not self.maybe_leave():
            return
        self._load(None)
        self.source.setPlainText(self.search.text().strip())
        self.editing = True
        self.adjust_layout()
        self.source.setFocus()

    def save_entry(self):
        if not self.dirty:
            return True
        try:
            scope = self.scope.currentData()
            source = self.source.toPlainText()
            self.store.set_entry(scope, source, self.target.toPlainText(), self.enabled.isChecked())
        except (ValueError, OSError) as exc:
            self.validation.setText(str(exc))
            self.target.setFocus()
            return False
        self.refresh()
        entry = next(e for e in self.store.entries() if e['scope'] == scope and e['source'] == source)
        self._load(entry)
        self.edit_status.setText('已保存 · 重新应用汉化后生效')
        self.saved.emit()
        return True

    def cancel_edit(self):
        if not self.dirty or confirm(self, '取消编辑', '放弃此词条尚未保存的输入？', '放弃修改'):
            self._load(self.current)

    def reset_entry(self):
        if not self.current:
            return
        if not confirm(self, '恢复词条', '将删除此词条的自定义覆盖；内置词条恢复默认译文。', '恢复 / 删除'):
            return
        try:
            self.store.reset_entry(self.current['scope'], self.current['source'])
        except (ValueError, OSError) as exc:
            error(self, str(exc))
            return
        self._load(None)
        self.refresh()
        self.saved.emit()

    def import_file(self):
        if not self.maybe_leave():
            return
        path, _ = QFileDialog.getOpenFileName(self, '导入自定义词典', '', '词典 JSON (*.json)')
        if not path:
            return
        try:
            preview = self.store.preview_import(path)
            dialog = QDialog(self)
            dialog.setWindowTitle('导入预览')
            layout = QVBoxLayout(dialog)
            conflicts = preview['conflicts']
            layout.addWidget(label(f"新增 {preview['added']} 条 · 冲突 {len(conflicts)} 条。只导入普通文本词条。"))
            policy = QComboBox()
            policy.addItem('冲突时保留本地译文', 'keep')
            policy.addItem('冲突时采用导入译文', 'overwrite')
            layout.addWidget(policy)
            detail = QPlainTextEdit()
            detail.setReadOnly(True)
            detail.setPlainText('\n'.join(f"{e['scope']} · {e['source']} → {e['target']}" for e in conflicts) or '没有冲突。')
            layout.addWidget(detail)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText('确认导入')
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('返回')
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setDefault(True)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            dialog.resize(min(760, self.window().width()-40), 420)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            count = self.store.import_data(preview['data'], policy=policy.currentData())
            self._load(None)
            self.refresh()
            self.saved.emit()
            self.count.setText(f'导入完成，更新 {count} 条；冲突处理：{policy.currentText()}。')
        except (ValueError, OSError) as exc:
            error(self, str(exc))

    def export_file(self):
        if not self.maybe_leave():
            return
        path, _ = QFileDialog.getSaveFileName(self, '导出自定义词典', 'custom-dictionary.json', '词典 JSON (*.json)')
        if path:
            try:
                self.store.export(path)
                self.count.setText('自定义词典已导出。')
            except (OSError, ValueError) as exc:
                error(self, str(exc))

    def show_rules(self):
        box = QMessageBox(self)
        box.setWindowTitle('系统规则 · 只读')
        box.setText('普通词条之外，汉化还包含动态文本和界面保护规则。')
        box.setInformativeText('例如：剩余百分比、连接器计数、语音时长、插件描述、跨节点提示及原生更新弹窗。\n这些规则保留数量、名称、快捷键和交互节点。首版不接受自定义正则或脚本。\n界面结构随 Antigravity 版本变化，规则效果仍需在目标版本核验。')
        box.exec()

    def back_to_list(self):
        if self.maybe_leave():
            self.editing = False
            self.adjust_layout()

    def reopen_editor(self, index):
        if index.isValid() and not self.editing:
            self.select_row(index, index)

    def adjust_layout(self):
        narrow = self.width() < 840
        self.back.setVisible(narrow)
        self.list_panel.setVisible(not narrow or not self.editing)
        self.editor.setVisible(not narrow or self.editing)
        if not narrow:
            self.editor.setMaximumWidth(400)
        else:
            self.editor.setMaximumWidth(16777215)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_layout()
