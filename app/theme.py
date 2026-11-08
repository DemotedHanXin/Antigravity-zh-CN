"""Shared design tokens and local artwork for the native Qt interface."""
import ctypes
import json
import os
from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPixmap, QLinearGradient, QPalette
from PySide6.QtWidgets import QWidget, QApplication

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / 'doc' / 'design'
TOKENS = json.loads((DESIGN / 'assets' / 'frontend-tokens.json').read_text(encoding='utf-8'))


def high_contrast():
    if os.name != 'nt':
        return False
    class HIGHCONTRAST(ctypes.Structure):
        _fields_ = [('size', ctypes.c_uint), ('flags', ctypes.c_uint), ('scheme', ctypes.c_wchar_p)]
    value = HIGHCONTRAST()
    value.size = ctypes.sizeof(value)
    return bool(ctypes.windll.user32.SystemParametersInfoW(0x0042, value.size, ctypes.byref(value), 0) and value.flags & 1)


def theme_name(preference):
    if preference in ('light', 'dark'):
        return preference
    return 'dark' if QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark else 'light'


def apply_theme(app, preference='system', scale=1.0):
    name = theme_name(preference)
    if high_contrast():
        app.setStyleSheet('')
        app.setPalette(app.style().standardPalette())
        return name
    t = TOKENS['themes'][name]
    palette = QPalette()
    for role, key in [('Window', 'canvas'), ('WindowText', 'text'), ('Base', 'surface'),
                      ('AlternateBase', 'subtle'), ('Text', 'text'), ('Button', 'surface'),
                      ('ButtonText', 'text'), ('Highlight', 'accentSoft'), ('HighlightedText', 'text'),
                      ('ToolTipBase', 'surface'), ('ToolTipText', 'text'), ('PlaceholderText', 'secondary')]:
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(t[key]))
    app.setPalette(palette)
    size = round(14 * scale)
    app.setStyleSheet(f'''
        QWidget {{ color: {t['text']}; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: {size}px; }}
        QMainWindow, QDialog {{ background: {t['canvas']}; }}
        QLabel {{ background: transparent; }}
        QLabel[role="muted"] {{ color: {t['secondary']}; }}
        QLabel[role="title"] {{ font-size: {round(26*scale)}px; font-weight: 600; }}
        QLabel[role="hero"] {{ font-size: {round(32*scale)}px; font-weight: 600; }}
        QLabel[role="heading"] {{ font-size: {round(18*scale)}px; font-weight: 600; }}
        QFrame[role="card"] {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 16px; }}
        QWidget#sidebar {{ background: {t['surface']}; border-right: 1px solid {t['border']}; }}
        QPushButton {{ background: {t['surface']}; border: 1px solid {t['controlBorder']}; border-radius: 10px; padding: 9px 14px; min-height: {round(20*scale)}px; font-weight: 600; }}
        QPushButton:hover {{ background: {t['subtle']}; }}
        QPushButton:pressed {{ background: {t['accentSoft']}; }}
        QPushButton:focus {{ border: 2px solid {t['accent']}; padding: 8px 13px; }}
        QPushButton[role="primary"] {{ background: {t['accent']}; color: {t['onAccent']}; border-color: {t['accent']}; }}
        QPushButton[role="primary"]:hover {{ background: {t['accentHover']}; }}
        QPushButton[role="primary"]:pressed {{ background: {t['accentPressed']}; }}
        QPushButton[role="danger"] {{ color: {t['danger']}; border-color: {t['danger']}; }}
        QPushButton[role="nav"] {{ text-align: left; border-color: transparent; padding: 12px; }}
        QPushButton[role="nav"]:checked {{ background: {t['accentSoft']}; color: {t['accent']}; border-left: 3px solid {t['accent']}; }}
        QPushButton:disabled {{ background: {t['subtle']}; color: {t['secondary']}; border-color: {t['border']}; }}
        QLineEdit, QPlainTextEdit, QComboBox {{ background: {t['surface']}; border: 1px solid {t['controlBorder']}; border-radius: 8px; padding: 8px; selection-background-color: {t['accentSoft']}; selection-color: {t['text']}; }}
        QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border: 2px solid {t['accent']}; padding: 7px; }}
        QComboBox QAbstractItemView {{ background: {t['surface']}; selection-background-color: {t['accentSoft']}; }}
        QTableView {{ background: {t['surface']}; alternate-background-color: {t['subtle']}; border: 1px solid {t['border']}; border-radius: 10px; gridline-color: {t['border']}; selection-background-color: {t['accentSoft']}; selection-color: {t['text']}; }}
        QHeaderView::section {{ background: {t['subtle']}; border: none; border-bottom: 1px solid {t['border']}; padding: 10px; font-weight: 600; }}
        QScrollArea {{ background: transparent; border: none; }}
        QScrollArea > QWidget > QWidget {{ background: transparent; }}
        QProgressBar {{ border: none; background: {t['subtle']}; border-radius: 3px; max-height: 6px; }}
        QProgressBar::chunk {{ background: {t['accent']}; border-radius: 3px; }}
        QCheckBox {{ spacing: 8px; padding: 4px 0; }}
        QToolTip {{ background: {t['surface']}; color: {t['text']}; border: 1px solid {t['border']}; padding: 6px; }}
        QStatusBar {{ background: {t['surface']}; }}
    ''')
    return name


class Artwork(QWidget):
    """Paint cached artwork only on the overview; data controls stay opaque."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = 'light'
        self.enabled = True
        self.overview = True
        self._key = None
        self._cache = QPixmap()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        if not self.enabled or not self.overview or high_contrast():
            return
        # Cache by logical size, theme and DPR; painting never stretches the source.
        key = (self.size().width(), self.size().height(), self.theme, self.devicePixelRatioF())
        if self._key != key:
            self._key = key
            source = QPixmap(str(DESIGN / TOKENS['artwork'][self.theme]))
            if source.isNull():
                self._cache = QPixmap()
                return
            self._cache = QPixmap(self.size() * self.devicePixelRatioF())
            self._cache.setDevicePixelRatio(self.devicePixelRatioF())
            self._cache.fill(QColor(TOKENS['themes'][self.theme]['canvas']))
            p = QPainter(self._cache)
            compact = self.window().width() < 1280
            target = QRectF(0, 0, self.width(), 200 if compact else self.height())
            factor = max(target.width()/source.width(), target.height()/source.height())
            width, height = source.width()*factor, source.height()*factor
            p.drawPixmap(QRectF(target.right()-width, 0 if compact else (target.height()-height)/2, width, height), source, QRectF(source.rect()))
            gradient = QLinearGradient(0, 0, self.width(), 0)
            for stop, alpha in ((0, 250), (.40, 235), (.70, 60), (1, 0)):
                color = QColor(TOKENS['themes'][self.theme]['canvas'])
                color.setAlpha(alpha)
                gradient.setColorAt(stop, color)
            p.fillRect(target, gradient)
            p.end()
        if not self._cache.isNull():
            painter.drawPixmap(0, 0, self._cache)
