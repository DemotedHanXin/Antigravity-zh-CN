"""Source checkout entry point; Qt is imported only for the GUI."""
import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Antigravity 中文管理器',
        epilog='命令行接口：python main.py --cli --help',
    )
    parser.add_argument('--data-dir', help='独立用户数据目录（默认使用当前用户目录）')
    parser.add_argument('--app-dir', help='Antigravity 安装目录')
    args = parser.parse_args(argv)
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print('无法加载 PySide6。请运行 python -m pip install -r requirements-manager.txt，并检查 Python 与 Qt 运行依赖。', file=sys.stderr)
        return 2
    from .service import DataError, ManagerService
    from .ui import ManagerWindow
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName('Antigravity 中文管理器')
    try:
        service = ManagerService(data_dir=args.data_dir)
    except (DataError, OSError):
        print('无法确定用户数据目录，请检查 APPDATA 或显式指定 --data-dir。', file=sys.stderr)
        return 2
    window = ManagerWindow(service, app_dir=args.app_dir)
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
