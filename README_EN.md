# Antigravity-zh-CN

English | [简体中文](README.md)

Chinese UI localization, restoration, and Windows proxy launcher / shortcut management for Antigravity Desktop. CLI tools use the Python standard library; the unified manager requires PySide6.

This fork extends [MIMICTE/Antigravity-zh-CN](https://github.com/MIMICTE/Antigravity-zh-CN). Legacy translation rules target the v2.21.1 layout; the new, limited 2.28.2 integration is described below. Text coverage and compatibility with other versions are not guaranteed. These changes apply to **the source in this repository**. Previously published executables need rebuilding to include them.

## Staged Windows manager development

Development stays on `feat/DragonGirl`, progressing from M0 through M5. Each stage delivers documentation, a local commit and an annotated review tag, then stops for explicit user approval. No automatic push, merge or release is included. **M0–M2 are approved. M3 unified manager is complete, pending review; M4 has not started.**

See the [M0 agreement](docs/development/M0-baseline.md), [M3 record](docs/development/M3-unified-manager.md) and [progress tracker](docs/development/PROGRESS.md) (Chinese). Windows packaging remains M4 work.

Source manager (Windows, Python 3.11+):

```powershell
python -m pip install -r requirements-manager.txt
python -m antigravity_manager
# Isolated review data; no automatic patch, app launch or API request
python -m antigravity_manager --data-dir .m3-lab/review
```

## DragonGirl development status — read first

**M1 is approved. The source includes the limited `antigravity-2.28.2-win32-x64-navigation` profile for Antigravity 2.28.2 / Windows x64; it has not been released.** Matching checks fingerprints of the entry point, preload, window/service modules and external `language_server.exe`, and binds the actual application window to its dynamic local service.

Repatching a matching build disables the legacy broad DOM observer. Web translation then covers **only four navigation body labels on `/`, with no query string or hash: New Conversation, Automations, Customizations and Settings**. Other page text, Projects and same-text aria-labels are outside this profile. Native menus retain static localization. Unmatched builds retain the legacy synchronous localization path.

All four labels currently match the built-in dictionary, so they do not naturally generate AI fallback requests. Isolated real-application tests used a deliberately missed label and a local fixed provider to validate requests, display, failures, disabled mode, navigation and service recovery. **Real-provider page translation has not been validated.** Updating repository files does not change the user's daily installation; applying the patch to a chosen installation is a separate operation.

- Unified manager: `python -m antigravity_manager`. The older Tk settings tool remains available.
- Order: personal dictionary → built-in dictionary/rules → valid pending candidate → AI. AI is off by default; native menus remain static.
- New AI results enter a separate seven-day candidate store. Reuse never extends expiry; acceptance creates a personal entry, and rejection suppresses requests until explicitly lifted.
- Dictionary/review CLI: `python src/localization/Translation-Dictionary.py --help`. Static data lives in `localization_runtime/builtin-dictionary.json`; regex logic stays in code.
- Separate OpenAI Responses, Gemini generateContent, Claude Messages, and custom OpenAI-compatible Chat Completions adapters.
- Windows keys use current-user DPAPI protection; existing plaintext configuration migrates on first read. Another account cannot directly decrypt it. Repatching/restoration do not delete settings or the personal dictionary.
- Connection testing is an explicit, potentially billable action requiring confirmation and external Node. Success does not establish application compatibility.

See the [DragonGirl guide](docs/DRAGONGIRL.md) and [M1 record](docs/development/M1-real-integration.md) (Chinese) for scope, evidence, current regression results and remaining limits. macOS integration, real-provider page translation, GUI/frozen packages and full application coverage remain unvalidated.

M2 migrates old data to schema 2 on first use, retaining manual entries and marking saved AI entries as legacy/unreviewed. Legacy entries do not expire. M3 protects key-bearing configurations using disk schema 3. Update the installed component together with the tools: old components reject the new format. Development tests have not migrated daily user data, and reverting Git is not a data downgrade.

## Existing features and repairs

- Validate ASAR structure, paths, application entry points and external files from `app.asar.unpacked`. Extract and translate in a staging directory before switching the installed code.
- Refuse restoration without a valid original archive, keeping a potentially sole working `resources/app`. Report deletion failures instead of silently claiming success.
- Select custom installations with `--app-dir`; multiple detected installations require an explicit selection.
- Create proxy CMD/PowerShell launchers and retarget matching `.lnk` files while retaining arguments, icons and working directories.
- Create no permanent proxy backups or recovery archives. Custom scan roots are stored as comment metadata inside the existing `.ps1` file.
- Cleanup preserves shortcuts, retargets them to the EXE, then directly deletes the two launchers. Rerun Setup to enable proxy launching again.
- Check PowerShell execution policy before deployment without changing or bypassing it. Try a personal Start Menu fallback when shared shortcuts cannot be updated, while reporting unresolved items.

See [Project status and code guide](PROJECT_STATUS.md) (Chinese) for the implementation and validation scope.

## Repository layout

```text
src/
├── localization/                     # Upstream localization/restoration and extensions
│   ├── Antigravity-Patcher.py
│   ├── Restore.py
│   ├── antigravity_common.py
│   ├── Translation-Settings.py
│   ├── translation_config.py
│   ├── translation_integration.py
│   └── Inspect-Translation-Compatibility.py
└── proxy/                            # Proxy and shortcut tools added by this fork
    ├── Setup-Proxy-Shortcuts.py
    └── Cleanup-Proxy-Shortcuts.py
localization_runtime/                 # JavaScript runtime and compatibility registry
tests/                                # Isolated Python / JavaScript tests
docs/                                 # DragonGirl usage and verification guides
```

Run the commands below from the repository root. Python entry points now live under `src`; use an absolute script path when launching from another working directory.

## Requirements and setup

| Function | Environment |
| --- | --- |
| Localization / restoration | Python 3.8+; Windows and macOS path / process branches |
| Proxy and shortcuts | Windows, Python 3.8+, built-in Windows PowerShell and WScript.Shell |
| Historical validation | Earlier Windows/Python 3.11 work is recorded in PROJECT_STATUS; not DragonGirl real-app acceptance |
| DragonGirl development tests | Python and Node 22+; isolated simulations do not prove real-app compatibility |

Download the complete repository and preserve this layout. Localization, restoration, settings and inspection tools import their sibling modules. Runtime resources are located relative to the source files at the repository root's `localization_runtime/`, independently of the working directory. Cleanup loads Setup from its own directory; keep the two proxy scripts together.

```powershell
git clone https://github.com/DemotedHanXin/Antigravity-zh-CN.git
cd Antigravity-zh-CN
python --version
```

Save your work first. Localization and restoration stop the target application before switching files. Patcher reports the result without launching the application; Restore accepts `--no-launch` to suppress its subsequent automatic launch. Proxy Setup/Cleanup do not stop running applications.

## Apply and remove localization

```powershell
python src/localization/Antigravity-Patcher.py
python src/localization/Antigravity-Patcher.py --app-dir "D:\Apps\Antigravity" --no-launch
python src/localization/Restore.py --app-dir "D:\Apps\Antigravity" --no-launch
```

On macOS, use `python3` and select the entire app bundle:

```bash
python3 src/localization/Antigravity-Patcher.py --app-dir "/Applications/Antigravity.app" --no-launch
python3 src/localization/Restore.py --app-dir "/Applications/Antigravity.app" --no-launch
```

Localization renames the original `resources/app.asar` to `app.asar.disabled` and installs the translated `resources/app`. **The `.disabled` file is the original archive needed for restoration, not leftover proxy backup data. Keep it.** Also retain the official `app.asar.unpacked` dependencies.

If both archive names exist, the tools stop rather than mixing an updated archive with older files. They also stop if a valid original archive is unavailable. Repair the official installation in that situation; deleting `resources/app` does not repair missing application code.

## Windows proxy launcher setup

Use this when your proxy client has enabled the **Windows system proxy with an HTTP / mixed port**, but Antigravity does not inherit the needed proxy environment.

```powershell
# Preview
python src/proxy/Setup-Proxy-Shortcuts.py --dry-run

# Deploy launchers and configure shortcuts
python src/proxy/Setup-Proxy-Shortcuts.py

# Custom installation and additional shortcut locations
python src/proxy/Setup-Proxy-Shortcuts.py --app-dir "D:\Apps\Antigravity" --scan-root "D:\Shortcuts" --scan-root "E:\Launchers"
```

Setup scans current-user and shared Desktop, Start Menu and Startup folders, plus Quick Launch / taskbar `.lnk` files. It matches the destination within the selected installation, not the shortcut name. It creates a personal Start Menu entry when no usable matching entry is available and reports shared shortcuts it cannot update.

Each launch reads the current Windows system proxy and supplies `HTTP_PROXY`, `HTTPS_PROXY` and related variables to the application process. No username, installation drive or proxy port is hardcoded, and Windows global proxy settings are not changed.

Fully exit Antigravity and launch it again through a repaired shortcut after setup. Existing processes do not acquire new environment variables.

### Cleanup and EXE shortcuts

```powershell
python src/proxy/Cleanup-Proxy-Shortcuts.py --dry-run
python src/proxy/Cleanup-Proxy-Shortcuts.py

# Older launchers may need their original custom roots specified again
python src/proxy/Cleanup-Proxy-Shortcuts.py --app-dir "D:\Apps\Antigravity" --scan-root "D:\Shortcuts"

# Recreate the proxy launch setup later
python src/proxy/Setup-Proxy-Shortcuts.py
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
- Restore reports failure of its automatic launch separately from file changes; use `--no-launch` to suppress that launch. Patcher never launches the application after applying changes.
- Translation depends on the application's file layout. Other versions and native macOS operation still require validation; complete translation of dynamic content or model output is not promised.

## Tests and code guide

```powershell
python -B -m unittest discover -s tests -v
node --test tests/js/*.test.cjs
```

Tests use isolated directories and mocked process control. They cover archive validation, external dependencies, localization / restore failure handling, shortcut arguments, scan roots and backup-free proxy operations. Do not run mutation tests against a working installation.

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for module responsibilities, file states and maintenance notes.

## Screenshot

![Antigravity Chinese UI example](antigravity-chinese.png)

This historical example does not represent M1 coverage or complete translation of every version or generated content. Static entries live in `localization_runtime/builtin-dictionary.json`; matching builds still restrict them to the four fixed navigation labels. Expanding that scope requires separate compatibility validation.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [MIT License](LICENSE). Report issues in [this fork](https://github.com/DemotedHanXin/Antigravity-zh-CN/issues). Original project: [MIMICTE/Antigravity-zh-CN](https://github.com/MIMICTE/Antigravity-zh-CN).
