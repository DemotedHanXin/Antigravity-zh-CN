"""Small accessible widget helpers; untrusted strings are always plain text."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QLabel, QPushButton, QFrame, QVBoxLayout, QHBoxLayout,
                              QScrollArea, QWidget, QMessageBox)


def label(text='', role=None):
    item = QLabel(text)
    item.setWordWrap(True)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    if role:
        item.setProperty('role', role)
    return item


def button(text, callback, role=None):
    item = QPushButton(text)
    item.setAccessibleName(text)
    item.setCursor(Qt.CursorShape.PointingHandCursor)
    if role:
        item.setProperty('role', role)
    item.clicked.connect(callback)
    return item


def card(title):
    frame = QFrame()
    frame.setProperty('role', 'card')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(12)
    layout.addWidget(label(title, 'heading'))
    return frame, layout


def row(*widgets):
    layout = QHBoxLayout()
    layout.setSpacing(8)
    for widget in widgets:
        layout.addWidget(widget)
    return layout


def scroll(content):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(content)
    return area


def confirm(parent, title, text, action):
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setText(text)
    proceed = box.addButton(action, QMessageBox.ButtonRole.AcceptRole)
    cancel = box.addButton('返回', QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel)
    box.setEscapeButton(cancel)
    box.exec()
    return box.clickedButton() is proceed


def error(parent, text):
    box = QMessageBox(QMessageBox.Icon.Warning, '请检查', text, parent=parent)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.addButton('知道了', QMessageBox.ButtonRole.AcceptRole)
    box.exec()
