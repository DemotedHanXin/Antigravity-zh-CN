# Windows build

Use 64-bit Python 3.12 on Windows. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r packaging/requirements-build.txt
powershell -NoProfile -File packaging/build-windows.ps1
```

The build script collects license texts, creates a PyInstaller directory
package, runs its isolated `--smoke-test`, creates a ZIP, and builds a native
Windows MSI installer with Python 3.12's `msilib`. The MSI is checked by reading
its database and extracting its cabinet with Windows `expand.exe`; every file
is compared to the frozen package by SHA-256. This does not install the MSI.

The optional `-InstallerFormat inno -InnoCompiler 'C:\path\ISCC.exe'` builds
an Inno Setup EXE when that compiler is available;
`-SkipInstaller` explicitly builds only the directory package and ZIP.
No dependency is downloaded by the build script.

Outputs are under `dist/`. Keep the EXE together with `_internal/` when using
the ZIP. The installer uses per-user privileges, creates a shortcut in the
Start menu, and preserves `%LOCALAPPDATA%/AntigravityZhCN/`
on upgrade/uninstall. The MSI has Chinese installation, repair and removal
dialogs; it installs into `%LOCALAPPDATA%/Programs/AntigravityZhCN/`.
It never patches/restores Antigravity or changes proxy shortcuts on uninstall.
The optional Inno build also offers a desktop shortcut. No code-signing
certificate is configured; local test artifacts are unsigned. Do not mix MSI
and Inno installation formats on the same machine: they have independent
upgrade identities. Only MSI is the tested build route in this environment.

The MSI builder requires Python 3.12 (`msilib` was removed in Python 3.13).
`build/msi-validation.json` records the file hashes and scope checks. MSI
creation/extraction is not proof of successful install/upgrade/uninstall on a
clean Windows machine; those remain separate acceptance steps.

The frozen smoke test verifies startup, Qt widgets and bundled data with an
isolated user-data directory. It does not replace clean-machine, target-version,
screen-reader or real installation tests. See `doc/PROJECT_STATUS.md` for the
latest verified results and remaining release acceptance work.
