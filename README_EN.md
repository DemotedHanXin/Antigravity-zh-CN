# Antigravity-zh-CN

English | [简体中文](README.md)

Chinese UI localization, restoration, and Windows proxy launcher / shortcut management for Antigravity Desktop. Runtime scripts use the Python standard library; no pip packages are required.

This fork extends [MIMICTE/Antigravity-zh-CN](https://github.com/MIMICTE/Antigravity-zh-CN). Translation rules target the v2.21.1 layout; text coverage and compatibility with other versions are not guaranteed. These changes apply to **the Python source in this repository**. Previously published executables need rebuilding to include them.

## New features and repairs

- Validate ASAR structure, paths, application entry points and external files from `app.asar.unpacked`. Extract and translate in a staging directory before switching the installed code.
- Refuse restoration without a valid original archive, keeping a potentially sole working `resources/app`. Report deletion failures instead of silently claiming success.
- Select custom installations with `--app-dir`; multiple detected installations require an explicit selection.
- Create proxy CMD/PowerShell launchers and retarget matching `.lnk` files while retaining arguments, icons and working directories.
- Create no permanent proxy backups or recovery archives. Custom scan roots are stored as comment metadata inside the existing `.ps1` file.
- Cleanup preserves shortcuts, retargets them to the EXE, then directly deletes the two launchers. Rerun Setup to enable proxy launching again.
- Check PowerShell execution policy before deployment without changing or bypassing it. Try a personal Start Menu fallback when shared shortcuts cannot be updated, while reporting unresolved items.

See [Project status and code guide](PROJECT_STATUS.md) (Chinese) for the implementation and validation scope.

## Requirements and setup

| Function | Environment |
| --- | --- |
| Localization / restoration | Python 3.8+; Windows and macOS path / process branches |
| Proxy and shortcuts | Windows, Python 3.8+, built-in Windows PowerShell and WScript.Shell |
| Validation for this revision | Windows with Python 3.11; native macOS and other app versions still need validation |

Download the complete repository. Keep `antigravity_common.py` beside `Antigravity-Patcher.py` and `Restore.py`. Keep `Setup-Proxy-Shortcuts.py` beside `Cleanup-Proxy-Shortcuts.py`.

```powershell
git clone https://github.com/DemotedHanXin/Antigravity-zh-CN.git
cd Antigravity-zh-CN
python --version
```

Save your work first. Localization and restoration stop the target application before switching files. `--no-launch` suppresses only the subsequent automatic launch. Proxy Setup/Cleanup do not stop running applications.

## Apply and remove localization

```powershell
python Antigravity-Patcher.py
python Antigravity-Patcher.py --app-dir "D:\Apps\Antigravity" --no-launch
python Restore.py --app-dir "D:\Apps\Antigravity" --no-launch
```

On macOS, use `python3` and select the entire app bundle:

```bash
python3 Antigravity-Patcher.py --app-dir "/Applications/Antigravity.app" --no-launch
python3 Restore.py --app-dir "/Applications/Antigravity.app" --no-launch
```

Localization renames the original `resources/app.asar` to `app.asar.disabled` and installs the translated `resources/app`. **The `.disabled` file is the original archive needed for restoration, not leftover proxy backup data. Keep it.** Also retain the official `app.asar.unpacked` dependencies.

If both archive names exist, the tools stop rather than mixing an updated archive with older files. They also stop if a valid original archive is unavailable. Repair the official installation in that situation; deleting `resources/app` does not repair missing application code.

## Windows proxy launcher setup

Use this when your proxy client has enabled the **Windows system proxy with an HTTP / mixed port**, but Antigravity does not inherit the needed proxy environment.

```powershell
# Preview
python Setup-Proxy-Shortcuts.py --dry-run

# Deploy launchers and configure shortcuts
python Setup-Proxy-Shortcuts.py

# Custom installation and additional shortcut locations
python Setup-Proxy-Shortcuts.py --app-dir "D:\Apps\Antigravity" --scan-root "D:\Shortcuts" --scan-root "E:\Launchers"
```

Setup scans current-user and shared Desktop, Start Menu and Startup folders, plus Quick Launch / taskbar `.lnk` files. It matches the destination within the selected installation, not the shortcut name. It creates a personal Start Menu entry when no usable matching entry is available and reports shared shortcuts it cannot update.

Each launch reads the current Windows system proxy and supplies `HTTP_PROXY`, `HTTPS_PROXY` and related variables to the application process. No username, installation drive or proxy port is hardcoded, and Windows global proxy settings are not changed.

Fully exit Antigravity and launch it again through a repaired shortcut after setup. Existing processes do not acquire new environment variables.

### Cleanup and EXE shortcuts

```powershell
python Cleanup-Proxy-Shortcuts.py --dry-run
python Cleanup-Proxy-Shortcuts.py

# Older launchers may need their original custom roots specified again
python Cleanup-Proxy-Shortcuts.py --app-dir "D:\Apps\Antigravity" --scan-root "D:\Shortcuts"

# Recreate the proxy launch setup later
python Setup-Proxy-Shortcuts.py
```

Cleanup keeps matching `.lnk` files, retargets them to `Antigravity.exe`, decodes the original arguments and retains icons / working directories. It deletes `Antigravity-Proxy.cmd` and `Antigravity-Proxy.ps1` only after all scanned proxy shortcuts have been handled.

Both proxy tools create **no permanent backups, logs or recovery archives** and no longer support `--restore` / `--backup-dir`. Deletion goes directly through the filesystem, not the Recycle Bin. Previously created backup directories are not automatically removed.

New Setup versions store custom scan roots in a comment inside the existing PS1. Cleanup reads that metadata, without another record file. If an older launcher has no metadata and its old backups are gone, provide the previous `--scan-root` values again. Missing or inaccessible explicit / recorded roots cause an error so cleanup does not silently skip them and remove the launchers.

## Troubleshooting and limits

| Situation | Action |
| --- | --- |
| Missing or multiple installations | Select the EXE directory with `--app-dir`, or the `.app` bundle on macOS |
| Invalid / missing archive or both archive names present | Preserve current files and repair the official installation |
| PowerShell scripts blocked or signatures required | Setup stops before changes; follow the computer or organization's permitted policy process. The tool does not relax it |
| Access denied for shared shortcuts or Program Files | Check the reported paths and use appropriate write permissions. A personal entry may be created as a fallback |
| Custom scan root unavailable | Correct the path or reconnect the drive before retrying |
| Shortcut changed during processing | Re-preview and retry rather than overwriting concurrent edits |
| Duplicate taskbar icons or stale pinned entries | CMD entry points and app windows may group differently; Windows pin caches may need repinning. Non-`.lnk` pins are outside this tool's scope |

- PAC scripts and standard `socks=...`-only system proxy settings are unsupported; use HTTP / mixed ports.
- When the Windows system proxy is off, the launcher uses direct / TUN behavior and clears inherited proxy variables. Environment-only proxy configurations are outside this design.
- The tools do not test proxy service availability, port connectivity, account status or destination reachability.
- Shortcuts moved outside known locations require `--scan-root`. Discovery does not cover arbitrary locations, other user accounts or every Windows pin type.
- Failure of automatic launch is reported separately from the file changes. Use `--no-launch` for file operations only.
- Translation depends on the application's file layout. Other versions and native macOS operation still require validation; complete translation of dynamic content or model output is not promised.

## Tests and code guide

```powershell
python -B -m unittest discover -s tests -v
```

Tests use isolated directories and mocked process control. They cover archive validation, external dependencies, localization / restore failure handling, shortcut arguments, scan roots and backup-free proxy operations. Do not run mutation tests against a working installation.

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for module responsibilities, file states and maintenance notes.

## Screenshot

![Antigravity Chinese UI example](antigravity-chinese.png)

This example does not imply complete translation of every version or generated content. Add translations to the dictionary in `Antigravity-Patcher.py`, then reapply the patch.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [MIT License](LICENSE). Report issues in [this fork](https://github.com/DemotedHanXin/Antigravity-zh-CN/issues). Original project: [MIMICTE/Antigravity-zh-CN](https://github.com/MIMICTE/Antigravity-zh-CN).
