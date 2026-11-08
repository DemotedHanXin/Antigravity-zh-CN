"""Build with .venv/Scripts/python.exe -m PyInstaller packaging/windows.spec."""
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

root = Path(SPECPATH).parent
datas = [
    (str(root / "src" / "*.py"), "src"),
    (str(root / "app" / "resources" / "*.json"), "app/resources"),
    (str(root / "doc/design/assets/frontend-tokens.json"), "doc/design/assets"),
    (str(root / "doc/design/assets/Gemini_Background_Light_1920x1080.png"), "doc/design/assets"),
    (str(root / "doc/design/assets/Gemini_Background_Dark_1920x1080.png"), "doc/design/assets"),
    (str(root / "LICENSE"), "."),
    (str(root / "packaging/THIRD_PARTY_NOTICES.md"), "."),
    (str(root / "build/licenses"), "licenses"),
]
for distribution in ("PySide6-Essentials", "shiboken6"):
    datas += copy_metadata(distribution)

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root), str(root / "src")],
    binaries=[], datas=datas,
    hiddenimports=["antigravity_common", "winreg", "runpy", "uuid", "signal",
                   "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="AntigravityZhCN", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, disable_windowed_traceback=False,
    uac_admin=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="AntigravityZhCN")
