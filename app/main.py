"""GUI entry point; smoke mode never inspects or writes a real installation."""
import argparse
import os
import sys
import tempfile


def main(argv=None):
    parser = argparse.ArgumentParser(description='Antigravity 中文助手')
    parser.add_argument('--app-dir', help='明确选择 Antigravity 安装目录')
    parser.add_argument('--data-dir', help='单独的助手用户数据目录（测试或便携使用）')
    parser.add_argument('--smoke-test', action='store_true', help='隔离用户数据，验证窗口和资源后退出')
    args = parser.parse_args(argv)
    if args.smoke_test:
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QLibraryInfo, QTranslator
    from .ui import MainWindow
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName('Antigravity 中文助手')
    app.setOrganizationName('AntigravityZhCN')
    translator = QTranslator(app)
    translator.load('qtbase_zh_CN', QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    app.installTranslator(translator)
    if args.smoke_test:
        with tempfile.TemporaryDirectory(prefix='antigravity-gui-smoke-') as temporary:
            window = MainWindow(data_dir=temporary, autoload=False)
            window.show()
            app.processEvents()
            assert window.dictionary_page.model.rowCount() > 0
            assert window.pages.count() == 4
            from .services import _module
            for name in ('Antigravity-Patcher', 'Restore', 'Setup-Proxy-Shortcuts', 'Cleanup-Proxy-Shortcuts'):
                _module(name)
            window.close()
            app.processEvents()
        return 0
    window = MainWindow(data_dir=args.data_dir, app_dir=args.app_dir)
    window.show()
    return app.exec()
