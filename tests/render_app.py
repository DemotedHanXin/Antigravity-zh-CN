"""Capture real Qt widgets, using isolated user data and no target installation.

Run with QT_SCALE_FACTOR=1/1.25/1.5/2 on Windows for repeatable layout review.
The normal Windows platform is intentional: offscreen does not load system fonts.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from app.ui import MainWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='build/ui-verification')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    reports = []
    with tempfile.TemporaryDirectory(prefix='ui-render-', dir=output) as data:
        window = MainWindow(data_dir=data, autoload=False)
        scenarios = [('home-light', 1440, 900, 0, 1, 0),
                     ('home-dark', 1440, 900, 0, 2, 0),
                     ('dictionary-wide', 1440, 900, 1, 1, 0),
                     ('dictionary-compact', 720, 480, 1, 1, 0),
                     ('home-compact-large-text', 720, 480, 0, 1, 2),
                     ('help-compact-large-text', 720, 480, 3, 1, 2)]
        for name, width, height, page, theme, font in scenarios:
            window.resize(width, height)
            window.theme_combo.setCurrentIndex(theme)
            window.font_combo.setCurrentIndex(font)
            window.navigate(page)
            if page == 1:
                window.dictionary_page.table.selectRow(20)
                window.dictionary_page.editing = True
                window.dictionary_page.adjust_layout()
            app.processEvents()
            window.grab().save(str(output / (name + '.png')))
            reports.append({'name': name, 'requested': [width, height],
                            'actual': [window.width(), window.height()],
                            'dpr': window.devicePixelRatioF()})
        window.close()
    (output / 'layout.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')
    if any(r['actual'] != r['requested'] for r in reports):
        raise SystemExit('Layout forced a larger window; inspect layout.json')


if __name__ == '__main__':
    main()
