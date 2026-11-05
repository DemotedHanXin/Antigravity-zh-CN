"""One-shot work executed away from the Qt GUI thread.

The window retains the worker until QThread.finished and defers closing until
then. No termination or blocking wait can interrupt an installation transaction.
"""
from PySide6.QtCore import QThread


class ServiceTask(QThread):
    def __init__(self, service, action, kwargs, parent=None):
        super().__init__(parent)
        self.service = service
        self.action = action
        self.kwargs = kwargs
        self.result = None

    def run(self):
        try:
            self.result = self.service.execute(self.action, **self.kwargs)
        except Exception:
            # Never render an arbitrary exception: it can contain credentials.
            self.result = {'ok': False, 'code': 'internal_error',
                           'message': '操作失败，请检查配置与文件状态后重试。'}
        finally:
            self.kwargs = {}  # Release transient password edits promptly.
