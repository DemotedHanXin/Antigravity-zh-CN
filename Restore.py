# coding: utf-8
"""Validate and restore the original application without deleting its only code."""
import argparse
import stat
import subprocess
import sys
import uuid

from antigravity_common import (
    discover_install,
    launch_application,
    remove_tree,
    resources_dir,
    stop_application,
    validate_asar,
)


def _exists(path):
    # A dangling link is a conflicting object, not an available destination.
    return path.exists() or path.is_symlink()


def _snapshot(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or
            getattr(info, 'st_file_attributes', 0) &
            getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024)):
        raise ValueError('原版归档必须是普通文件，不能是目录链接或符号链接：' + str(path))
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _check_app_directory(path, parent):
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or
            getattr(info, 'st_file_attributes', 0) &
            getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024) or
            path.is_symlink() or path.resolve().parent != parent.resolve()):
        raise ValueError('拒绝清理安装目录以外的目录、符号链接或重解析点：' + str(path))
    return (info.st_dev, info.st_ino)


def _app_snapshot(path, parent):
    return _check_app_directory(path, parent) if _exists(path) else None


def restore(app_dir=None, launch=True):
    """Return 0 on completion and 2 if original code is restored but cleanup fails.

    Validation and commit failures raise before any success message. The caller
    must never discard a quarantined directory if a rollback also fails.
    """
    root = discover_install(app_dir)
    resources = resources_dir(root)
    archive = resources / 'app.asar'
    disabled = resources / 'app.asar.disabled'
    application = resources / 'app'
    sidecar = resources / 'app.asar.unpacked'
    print('[安装目录] ' + str(root))

    if _exists(archive) and _exists(disabled):
        raise ValueError('app.asar 与 app.asar.disabled 同时存在，可能来自不同版本；未覆盖或删除任何文件，请先核对安装状态。')
    source = disabled if _exists(disabled) else archive
    if not _exists(source):
        raise ValueError('未找到可恢复的 app.asar 或 app.asar.disabled。已保留 resources/app，请修复或重新安装官方软件。')

    # Do not stop the application, rename app, or delete anything before this
    # check succeeds, including the entry point and required external files.
    snapshot = _snapshot(source)
    validate_asar(source, unpacked_dir=sidecar)
    if _snapshot(source) != snapshot:
        raise ValueError('原版归档在校验期间发生变化，未执行还原。')
    app_snapshot = _app_snapshot(application, resources)
    has_app = app_snapshot is not None
    needs_activation = source == disabled
    if not has_app and not needs_activation:
        print('[完成] 原版归档及主入口校验通过，没有汉化工作目录需要清理。')
        return 0

    print('[执行] 正在关闭该安装目录下的 Antigravity...')
    stop_application(root)
    if _snapshot(source) != snapshot:
        raise ValueError('原版归档在还原前发生变化，未修改安装文件。')
    if _app_snapshot(application, resources) != app_snapshot:
        raise ValueError('汉化工作目录在关闭程序期间发生变化，未修改安装文件。')

    quarantined = None
    try:
        if _app_snapshot(application, resources) != app_snapshot:
            raise ValueError('汉化工作目录在切换前发生变化，未修改安装文件。')
        if has_app:
            quarantined = resources / ('.antigravity-restore-' + uuid.uuid4().hex)
            if _exists(quarantined):
                raise ValueError('临时目录已存在，未覆盖：' + str(quarantined))
            application.rename(quarantined)
        if needs_activation:
            if _exists(archive):
                raise ValueError('还原过程中出现新的 app.asar，未覆盖该文件。')
            if _snapshot(disabled) != snapshot:
                raise ValueError('原版归档在切换前发生变化，已停止还原。')
            disabled.rename(archive)
    except BaseException as error:
        if quarantined is not None and _exists(quarantined):
            try:
                if _exists(application):
                    raise ValueError('resources/app 已被其他程序创建，不能覆盖。')
                quarantined.rename(application)
            except BaseException as rollback_error:
                raise RuntimeError('还原未完成：{}；工作目录恢复失败：{}。原工作目录仍保留在 {}，请勿删除。'.format(
                    error, rollback_error, quarantined)) from error
        raise

    # The original archive is now active and app no longer shadows it. Never
    # move a partly deleted quarantine back to the active app directory.
    if quarantined is not None:
        try:
            remove_tree(quarantined, resources)
        except (OSError, ValueError, RuntimeError) as error:
            print('[未完成] 原版 app.asar 已就位，但汉化临时目录未能清理：{}；残留位置：{}'.format(error, quarantined))
            print('[说明] 未报告清理成功，也未自动启动；解除文件占用或权限问题后可清理上述目录。')
            return 2

    print('[完成] 已恢复原版归档并清除汉化工作目录；代理启动文件和快捷方式保持不变。')
    if launch:
        try:
            launch_application(root)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            raise RuntimeError('安装文件已还原，但自动启动未完成：' + str(error)) from error
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='校验官方归档后安全还原 Antigravity，保留唯一可运行的代码。')
    parser.add_argument('--app-dir', help='Antigravity 安装目录；macOS 使用 Antigravity.app 路径')
    parser.add_argument('--no-launch', action='store_true', help='还原完成后不自动启动软件')
    args = parser.parse_args(argv)
    try:
        return restore(args.app_dir, launch=not args.no_launch)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('[错误] ' + str(error))
        return 1


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    try:
        result = main()
    except KeyboardInterrupt:
        print('\n[提示] 用户取消操作。')
        result = 130
    if len(sys.argv) == 1 and sys.stdin.isatty():
        try:
            input('\n执行完毕，按 Enter 键退出...')
        except (EOFError, KeyboardInterrupt):
            pass
    sys.exit(result)
