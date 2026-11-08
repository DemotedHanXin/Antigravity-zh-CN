# Runtime and build components

This application retains the repository's MIT license and the upstream
Antigravity-zh Contributors attribution. Antigravity itself is a separate
product and is not distributed by this installer.

Runtime components:

| Component | Version | License/source |
| --- | --- | --- |
| CPython | 3.12.10 (build interpreter) | PSF license; https://www.python.org/downloads/release/python-31210/ |
| PySide6 Essentials / Qt | 6.8.3 | LGPL-3.0 / GPL-3.0 / commercial choices; https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.8.3 and https://code.qt.io/cgit/qt/qtbase.git/tag/?h=v6.8.3 |
| Shiboken6 | 6.8.3 | LGPL-3.0 / GPL-3.0 / commercial choices; same PySide source |

Build tools: PyInstaller 6.16.0 (GPL with bootloader exception), with exact
build dependency versions in packaging/requirements-build.txt. The distributed
runtime does not require users to install Python, pip, PyInstaller or Node.js.

Full license files from the installed distributions and CPython are included
under `_internal/licenses`. The onedir package keeps the Qt dynamic libraries
and Python extension modules separate. Users may replace these components with
compatible modified versions; this project adds no restriction on reverse
engineering for debugging such modifications. Source for this application is
the accompanying repository. For the relevant Qt/PySide terms, see the included
license texts and https://doc.qt.io/qtforpython-6/licenses.html.

Inno Setup is a build tool only. It is not required to run the ZIP edition.
Its current licensing information is https://jrsoftware.org/isinfo.php and
https://jrsoftware.org/isorder.php; commercial distribution decisions must
use the license applicable to the chosen compiler and project use.

The two Gemini background images are provided by the project owner. Their
source manifest is doc/design/assets/manifest.json. The repository's MIT
license does not grant additional rights to third-party artwork or trademarks.
