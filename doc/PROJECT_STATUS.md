# 项目状态与代码说明

更新日期：2026-11-08。本文对应当前工作区源码与设计文件；工作区中的新增和修改不代表已经提交、发布或打包。日常使用命令见 [README.md](../README.md)，英文说明见 [README_EN.md](../README_EN.md)，维护约定见 [CONTRIBUTING.md](../CONTRIBUTING.md)。

## 0. 本轮交付与交接（2026-11-08，codex/work）

开发位置：`D:\Python\Python_Code_Set\Tools\Antigravity-zh-CN-codex-work`，分支 `codex/work`。用户确认仅更新此工作分区，不同步原工作区。代码尚未提交或推送，构建产物不是已发布 Release。

**已实现**：`app/` 中的原生 PySide6 Windows 中文助手，根目录 `main.py` 启动。四页为概览、翻译词典、代理启动、恢复与帮助；首次找不到唯一安装时提供三步引导。已接通真实本地服务，不是 HTML 示例界面。日夜/系统主题、可关闭插画、100%/115%/130% 字号、窄窗口布局、未保存编辑保护、后台任务与任务期间关闭保护已实现。

**验证结果**：Python 3.12.10、PySide6 Essentials 6.8.3、PyInstaller 6.16.0。最终完整回归 **157/157 通过，0 失败、0 跳过**，耗时 28.116 秒。涵盖真实 Chromium 隔离 DOM、Node 翻译规则、模拟 ASAR、模拟 COM 快捷方式、真实 Qt 控件和 QThread。此前 Crashpad 失败由沙箱浏览器启动限制导致，工具批准后在沙箱外重跑全部通过。一次中间全量运行出现临时目录 rename 的 WinError 5；单项、相关 40 项及最终全量均通过，未修改测试绕过失败，不能据此声称 Windows 文件占用永不发生。

**构建**：最终 PyInstaller 目录包及冻结 EXE 的 `--smoke-test` 通过（含四个动态后端模块导入），已生成 ZIP 和每用户 MSI 安装包。MSI 含 222 个文件/223 个组件，全部文件解包 SHA-256 一致。MSI 使用本机 Python 3.12 `msilib` 构建；读取安装数据库、提取 CAB 并逐文件校验 SHA-256，不在本机注册安装。Inno Setup 配置保留为可选路线，官方下载在本环境不可达，因此未生成 Inno EXE。最终产物及校验值在 `dist/`；构建流程见 [packaging/README.md](../packaging/README.md)。

| 可运行入口/交付 | 位置 |
| --- | --- |
| 源码启动 | `.\.venv\Scripts\python.exe main.py` |
| 明确选择安装 | `.\.venv\Scripts\python.exe main.py --app-dir "D:\Apps\Antigravity"` |
| 免 Python 目录包 | `dist/AntigravityZhCN/AntigravityZhCN.exe`，保留旁边 `_internal/` |
| 便携 ZIP | `dist/AntigravityZhCN-0.1.0-windows-x64.zip` |
| 安装包 | `dist/AntigravityZhCN-0.1.0-Setup-x64.msi` |
| 文件校验 | `dist/SHA256SUMS.txt` |
| 全量测试输出 | `build/test-results-final.txt`（本地忽略文件） |
| 实际 Qt 检查图 | `build/ui-verification/dpi-{100,125,150,200}/`（本地忽略文件） |
| MSI 检查报告 | `build/msi-validation.json`（本地忽略文件） |

**后续对话从这里接续**：先 `git status --short --branch`，阅读本节和相关实现；无需重新做设计或重写 CLI。默认数据目录是 `%LOCALAPPDATA%/AntigravityZhCN/`，测试可用 `--data-dir` 隔离。修复后按影响范围重跑对应测试，必要时完整回归；源码变化后运行 `packaging/build-windows.ps1` 重建产物。

**尚未作为公开发行验收完成**：无 Python 的干净 Windows 上实际安装/升级/卸载、真实 Antigravity 目标版本汉化/恢复/代理写入、Narrator 读屏、多显示器跨屏和真实高对比度切换。测试未修改用户真实安装或真实快捷方式。构建未签名，未上传发布。DPI 检查使用真实 Windows Qt 渲染与测试缩放因子，实际 DPR 约 1/1.25/1.5/2；不等同于更改系统缩放或真机跨屏测试。

## 1. 项目当前负责什么

项目有两条可以分别使用的流程：

1. **界面汉化与还原**：读取安装目录中的官方 ASAR，生成带中文翻译的应用目录；需要时恢复官方归档。
2. **Windows 代理启动与清理**：创建代理启动文件，调整快捷方式；需要时将快捷方式改回 EXE，并删除代理启动文件。

汉化不会替用户配置代理客户端，代理工具也不修改汉化词典或 ASAR。代理工具不生成永久备份；汉化保留的 `app.asar.disabled` 则是原版代码的改名，是还原所必需的文件。

| 模块 | 当前状态 |
| --- | --- |
| Python 命令行工具 | 汉化、还原、Windows 代理启动器与快捷方式管理均已有源码 |
| 翻译规则与注入引擎 | 词条、动态文本、原生菜单、提示链接及图标修复已有实现；验证结果见第 7 节 |
| Windows 图形界面 | `app/` 已实现四页 PySide6 应用及首次引导，根目录 `main.py` 启动 |
| 界面预览 | 已有 HTML 示例原型和三张 PNG 设计稿，不连接真实安装、网络检测或词典存储 |
| 打包发布 | Windows 目录包/ZIP/MSI 已构建并隔离检查；未签名、未发布。macOS 构建流程仍待维护 |

汉化和还原在需要切换安装文件时会关闭目标应用，**完成后始终不自动启动**；保留的 `--no-launch` 仅用于兼容旧命令。需要使用时由用户手动启动 Antigravity。代理 Setup/Cleanup 不关闭正在运行的应用。

### 已处理的主要问题

| 原问题 | 当前处理方式 |
| --- | --- |
| 没有原版归档时，还原仍删除唯一的 `resources/app` | 先检查归档及其主入口、外置依赖；没有有效来源就停止，保留现有代码 |
| 解包忽略 `unpacked` 条目，汉化目录缺少依赖 | 从官方 `app.asar.unpacked` 复制对应文件，核对文件大小及可用的完整性信息 |
| 重用不完整解包目录，或验证前禁用官方归档 | 每次从经过验证的原版归档生成暂存目录；注入与入口验证完成后再切换 |
| 删除出错却提示成功 | 删除错误向上传递，分别报告安装切换和临时文件清理的结果 |
| 自定义安装路径无法处理 | 提供 `--app-dir`，并对自动发现的多个安装明确报错 |
| Setup 看似成功，实际 PS1 被执行策略阻止 | 部署前只读检查策略，不配置已知无法执行的入口，不修改全局策略 |
| 删除旧备份后找不到自定义快捷方式 | 将扫描根写在现有 PS1 的注释中，Cleanup 读回；无元数据的旧版仍需用户补充目录 |
| 额外扫描目录拼错却继续清理 | 显式或记录的扫描根无效时报错，保留启动器 |
| Setup 自身仍积累代理备份 | 移除新建备份和备份还原功能，重新启用依靠 Setup 再生成 |
| 公共快捷方式权限不足，没有可用个人入口 | 尝试个人开始菜单回退，同时保留未处理入口的错误状态 |

### 当前源码中的翻译改进

- 补充项目排序、对话操作、文件审阅、语音、模型、插件与自动化相关界面词条。
- 处理剩余百分比、连接器数量、带快捷键的提示、语音预设和动态删除说明，保留名称、数量与快捷键值。
- 插件市场描述支持完整文本、换行文本及足够明确的截断前缀；不明确的短前缀不做猜测替换。
- 对跨文本节点的提示、云资源说明与连接器计数进行定向翻译，保留既有链接和可交互节点；隔离浏览器验证已通过，实际目标版本页面仍需验收，见第 7 节。
- 原生菜单翻译保留菜单动作；原生更新弹窗只替换显示字段；`restore_page` 图标有定向 SVG 修复逻辑。
- DOM 遍历避开代码块、Monaco 编辑器与可编辑正文，输入框占位文字可以翻译。上述保护不能替代真实应用页面的验收。

内置词典和动态规则仍由 `src/Antigravity-Patcher.py` 维护，999 条普通词条同步提取到 `app/resources/builtin-dictionary.json` 供 GUI 展示，一致性测试防止二者漂移。GUI 的用户 JSON 覆盖层经严格校验后交给共享引擎；动态/系统规则只读。CLI 不传词典快照时保持原行为。

## 2. 源码结构

| 文件 | 职责与主要入口 |
| --- | --- |
| [Antigravity-Patcher.py](../src/Antigravity-Patcher.py) | 翻译词典、DOM/菜单注入代码，以及 `apply_patch()` 汉化流程；`main()` 解析 CLI |
| [Restore.py](../src/Restore.py) | `restore()` 验证原版归档、切换应用状态、清除汉化目录；`main()` 处理 CLI 和失败状态 |
| [antigravity_common.py](../src/antigravity_common.py) | 安装目录发现、ASAR 校验/提取、入口验证、受限范围删除，以及目标安装的进程控制 |
| [Setup-Proxy-Shortcuts.py](../src/Setup-Proxy-Shortcuts.py) | 启动器模板、Windows 快捷方式 COM 桥接、扫描、策略检查、目录元数据与 `install()` |
| [Cleanup-Proxy-Shortcuts.py](../src/Cleanup-Proxy-Shortcuts.py) | 加载同目录 Setup 工具函数；`plan_cleanup()` 计划修改，`apply_cleanup()` 改回 EXE 后删除启动器 |
| [tests](../tests) | 隔离样例与回归测试，不以真实安装作为写入目标 |
| [design](design/README.md) | Windows 应用规划、样式规范、HTML/PNG 预览与统一素材目录 |
| [build-mac.yml](../.github/workflows/build-mac.yml) | 现有 macOS PyInstaller 工作流；构建命令仍指向根目录脚本，需更新后再验证 |

上表中的工具脚本均在仓库根目录的 `src/` 下，运行时使用 `python src/脚本名.py`。汉化和还原通过普通 Python 导入共享模块，因此分发源码时必须包含 `src/antigravity_common.py`。Cleanup 使用 `runpy.run_path()` 读取同目录 Setup 的定义，不会执行它的命令行入口。

### 公共模块的关键函数

- `discover_install(explicit=None)`：接受明确目录，或在 Windows 环境变量/注册表、macOS 常见应用目录中查找；结果不唯一时停止。
- `resources_dir(app_dir)`：Windows 使用 `resources`，macOS 使用 `.app/Contents/Resources`。
- `validate_asar(asar_path, unpacked_dir=None)`：检查归档头、索引、相对路径、数据范围、外置文件和 `package.json` 的主入口；无效时抛错。
- `extract_asar(...)`：写入空的暂存目录，包括外置依赖；不会把不完整提取结果当作可用安装。
- `validate_extracted_app(...)`：检查解包入口及调用者指定的必要汉化目标文件。
- `remove_tree(path, parent)`：确认目标是预期父目录中的子目录，拒绝符号链接/重解析点，删除失败不忽略。
- `stop_application(app_dir)`：只关闭所选安装的进程。公共模块仍保留 `launch_application(app_dir)` 辅助函数及其回归测试，但当前 Patcher/Restore 流程不调用它。

## 3. 汉化与还原的文件状态

以下路径均相对于目标安装的资源目录，macOS 的资源目录层级不同。

| 路径 | 含义 | 是否可以当作残留直接删除 |
| --- | --- | --- |
| `app.asar` | 当前官方应用归档 | 否 |
| `app.asar.unpacked/` | 官方归档放在外部的依赖文件 | 否 |
| `app.asar.disabled` | 汉化时改名保留的原始归档 | 否，还原依赖它 |
| `app/` | 汉化后的解包应用，也可能是异常状态下唯一剩余的代码 | 不能仅凭目录名删除 |
| `.antigravity-*` 临时目录 | 暂存或隔离中的代码 | 正常完成会清理；失败时先读输出判断用途，不能盲删 |

正常状态：

```text
原版：app.asar + app.asar.unpacked/
  │ 验证原版 → 暂存提取完整依赖 → 注入翻译 → 验证入口 → 切换
  ▼
汉化：app.asar.disabled + app/ + app.asar.unpacked/
  │ 验证原始归档 → 停止目标应用 → 隔离汉化目录 → 恢复归档 → 清理
  ▼
原版：app.asar + app.asar.unpacked/
```

### 为什么先暂存再切换

直接在 `resources/app` 中边解包边修改，会在断电、文件缺失、权限错误或解包中断时留下半成品。新版先完成全部可验证工作，再执行目录/文件改名。切换发生异常时尝试回滚；如果回滚也失败，保留仍有恢复价值的代码并报告其具体位置。

恢复时先把汉化目录移出 `app` 这个生效路径，避免部分删除后残余目录继续遮蔽官方归档。清理隔离目录失败会返回未完成状态，不能将其误报为全部清理成功。失败遗留的 `.antigravity-restore-*` 不会由下次 Restore 自动删除，应按本次输出核查后处理。多次文件操作不等同于断电级事务，强制结束解释器或断电后的状态仍需核查。

同时存在 `app.asar` 和 `app.asar.disabled` 时可能涉及官方更新与旧汉化混用。工具不会猜测哪个版本应覆盖哪个版本，而是停止。无有效原版归档时需要先修复官方安装。

## 4. 代理启动与清理原理

启动链路：

```text
桌面／开始菜单中的 .lnk
  → Antigravity-Proxy.cmd
  → Antigravity-Proxy.ps1
  → 读取当前用户 Windows 系统代理
  → 设置本次进程的 HTTP_PROXY / HTTPS_PROXY / NO_PROXY 等变量
  → 同一安装目录中的 Antigravity.exe
```

### 快捷方式为什么要编码参数

原 `.lnk` 的参数可能包含中文、空格、引号和 `&`。如果直接拼进 CMD 命令行，会再次受到 Shell 解析。Setup 将原始参数按 UTF-8 编码后转为 Base64，通过 `-ShortcutArgsBase64` 传递；PS1 解码后交给 `ProcessStartInfo.Arguments`。Cleanup 反向解码后写回 EXE 快捷方式。

匹配依据是目标文件路径，不能仅凭快捷方式名称判断。读取时记录内容哈希，写入前再次检查，避免覆盖扫描后用户修改的快捷方式。任务栏图标分组还受 Windows 的应用标识和固定项缓存影响，修改 `.lnk` 并不保证所有图标合并。

### 无备份如何找到自定义目录

新版 `.ps1` 的注释元数据记录 `--scan-root` 对应的扫描根。Setup 重跑时合并这些目录，Cleanup 在删除 `.ps1` 前读出并验证。元数据只作为 JSON 数据读取，不执行其中内容，也不生成独立清单文件。

旧版安装若仍有备份记录，Cleanup 可以只读利用其中的快捷方式路径。旧记录和旧启动器都不包含某个位置时，不可能自动推断该位置，必须由用户再次提供 `--scan-root`。已记录目录离线或不可访问时需要先恢复访问，避免漏处理。

### 清理的顺序

1. 确认同一安装目录内存在 `Antigravity.exe`。
2. 扫描默认位置、自定义元数据目录及本次额外目录，验证结果完整。
3. 将匹配的快捷方式改回 EXE，恢复原始参数，保留图标及工作目录。
4. 再次检查已扫描范围内是否仍有代理快捷方式。
5. 只对确定的 `Antigravity-Proxy.cmd`、`Antigravity-Proxy.ps1` 调用直接删除。

中途失败不会继续删除启动器。已完成的快捷方式修改可能保留；处理错误后可重跑。Setup/Cleanup 不提供磁盘备份还原，不删除 `.lnk`；需要重新启用代理时运行 Setup。

## 5. 参数与使用选择

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| Patcher / Restore | `--app-dir` | 明确选择安装目录或 macOS `.app` |
| Patcher / Restore | `--no-launch` | 兼容旧命令；当前无论是否传入都不自动启动，不影响切换前关闭应用 |
| Setup / Cleanup | `--app-dir` | 选择包含 `Antigravity.exe` 的 Windows 安装目录 |
| Setup / Cleanup | `--scan-root` | 额外扫描快捷方式目录，可重复使用 |
| Setup / Cleanup | `--dry-run` | 预览，不创建、修改或删除安装文件及快捷方式 |

两条恢复操作的用途不同：`src/Restore.py` 恢复英文界面；`src/Cleanup-Proxy-Shortcuts.py` 退出代理启动方式。后者不操作汉化归档，前者不清理代理快捷方式。

## 6. Windows 应用设计与目录约定

设计资料统一放在 [design/](design/README.md)：

| 位置 | 用途 |
| --- | --- |
| [WINDOWS_APP_PLAN.md](design/WINDOWS_APP_PLAN.md) | 面向普通用户的 Windows 应用范围、流程与开发阶段规划 |
| [FRONTEND_STYLE_PLAN.md](design/FRONTEND_STYLE_PLAN.md) | 虹光日夜主题、组件状态、布局与 Qt 验收标准 |
| [frontend-style-preview.html](design/frontend-style-preview.html) | 浏览器交互预览，使用内存中的示例数据，刷新即重置 |
| `design/ui-*.png` | 与 HTML 同级的三张界面效果预览，属于设计稿 |
| [assets/](design/assets/) | 三张原始插画/背景、来源清单 `manifest.json` 和设计参数 `frontend-tokens.json` |

`design/` 根目录保留设计文档与预览效果，输入素材及配套数据集中到 `design/assets/`。打开 HTML 时应保留整个目录结构；设计参数用于实现参考，不是当前 CLI 的运行配置。

状态首页、三步首次引导、圆角卡片、日夜主题、可视化词典和后台任务已在原生 Qt 中实现。HTML/PNG 仍为设计参考；实际验收结果见第 0 节。实现采用 Python + PySide6、JSON 覆盖层、PyInstaller 目录包及 MSI 安装器。

## 7. 验证方式与当前边界

运行回归测试：

```powershell
python -B -m unittest discover -s tests -v
```

2026-11-08 最终完整回归：**157 项全部通过，无失败或跳过**。执行使用工作分区 `.venv` 的 Python 3.12.10 和 Node.js v24.15.0；涉及 Chrome/Edge 的测试需允许隔离浏览器正常启动。完整命令：

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

受限环境中可将 `TEMP` / `TMP` 指向本工作区 `build/tmp`。旧状态记录的 5 项 Crashpad 失败以及新增归档场景已通过；不要通过跳过断言将环境失败计为成功。

GUI 新增测试覆盖词典严格导入、特殊字符/对象键、跨节点禁用及重复运行稳定性、原子保存与跨进程锁、损坏文件恢复、实际安装状态和词典 hash、代理预览失效保护、诊断字段过滤、后台线程/重复操作/关闭保护、编辑保存与未保存提示、首次引导的检查与重试。浏览器使用一次性配置目录；Qt、ASAR 和快捷方式均使用隔离数据，进程终止与真实 COM 写入被模拟。

测试覆盖包括：

- 完整/截断/无效的 ASAR、越界路径、缺失主入口、外置依赖复制与校验。
- 无原始归档时保留唯一代码、归档冲突停止、注入/改名/删除失败的处理。
- 自定义安装目录、CLI 参数、不自动启动行为，以及保留的启动辅助函数的失败报告。
- 快捷方式中文/引号参数、路径匹配、并发修改保护、失败时保留启动器。
- 无代理备份的创建→清理→重新创建，自定义扫描目录保留与验证。
- 受限 PowerShell 策略在修改前停止，公共入口失败时个人入口回退。
- 动态翻译值保留、重复执行稳定性、原生菜单动作保留、更新弹窗显示字段与动作键分离。

这些检查不能替代所有系统和软件版本上的实际运行验证。仍有以下边界：

- macOS 的路径和进程分支保留，但本轮未在 macOS 真机运行；Python 3.8 的最低兼容声明仍需对应解释器验证。
- 翻译依赖特定应用文件布局；当前测试不等于已对某个官方版本完成全部界面和功能验收。
- PAC、纯 SOCKS 系统配置、仅环境变量代理、代理端口/目标服务连通性不在自动修复范围内。
- 企业执行策略、安装目录权限和系统固定项存储形式可能阻止某些步骤；工具会报告已知失败条件，不擅自放宽安全设置。
- 未知位置或其他用户账户的快捷方式不能保证被自动发现。
- 强制终止或系统掉电仍可能留下暂存目录；无法删除或回滚的目录会保留以免丢失可恢复代码。
- 对不同归档格式、新版应用文件布局或不支持的链接条目，应停止而不是猜测后继续覆盖。
- 本次已构建新的 Windows 图形助手目录包、ZIP 和 MSI；未发布 Release，现有其他旧版 EXE 不会自动更新。

## 8. 后续维护事项

1. 在目标 Antigravity 版本的可恢复测试安装上进行实际页面、启动、汉化/还原、代理配置/清理验收。隔离 DOM 回归已通过。
2. 将 macOS 工作流的 PyInstaller 输入路径同步为 `src/` 中的实际入口，并验证公共模块打包和两个架构产物；当前工作流不能作为可发布证明。
3. 在干净 Windows 环境验证 MSI 安装/升级/卸载、用户数据保留、Narrator、真实系统缩放与高对比度；确认版本支持表及素材/发行授权后再签名发布。

新增翻译优先修改 Patcher 中的字典与注入代码；新增归档处理逻辑放在公共模块；Windows 启动器与 COM 桥接集中在 Setup。修改涉及安装文件切换时，应先添加失败路径回归测试，再考虑正常流程。

发布前应在目标版本的干净安装上验证：英文启动、汉化启动、核心依赖功能、还原启动、代理配置、代理清理、无效输入保护。不要仅凭单元测试通过宣称所有版本完全兼容。



## 9. Windows 图形助手代码与数据约定

| 文件 | 职责 |
| --- | --- |
| `main.py`、`app/main.py` | 源码/打包入口，隔离 `--smoke-test` |
| `app/ui.py`、`app/widgets.py` | 四页窗口、确认、状态与会话结果 |
| `app/theme.py` | 统一读取设计参数，双主题、背景缓存、资源缺失回退、高对比度优先 |
| `app/dictionary_view.py` | 原生表格搜索、编辑、导入冲突预览、宽窄布局、dirty 保护 |
| `app/onboarding.py`、`app/workers.py` | 三步只读引导与后台 QThread，GUI 线程只渲染结果 |
| `app/dictionary.py`、`app/storage.py` | 词典校验、覆盖合并、单次读取快照、文件锁、原子保存及显式恢复 |
| `app/services.py` | 复用 src 脚本，安装预检、阶段输出、互斥、代理计划复核、脱敏诊断 |
| `app/resources/builtin-dictionary.json` | 951 UI + 48 menu 普通词条的同步目录 |
| `packaging/` | 固定依赖、PyInstaller、MSI 构建与校验、可选 Inno 配置、许可文件 |
| `tests/test_app_*.py`、`tests/test_onboarding.py` | GUI/服务/词典专项回归 |
| `tests/render_app.py` | 生成实际 Qt 日夜、宽窄和字号检查图，不写真实安装 |

用户覆盖 JSON 采用 `schemaVersion: 1`、`revision`、`entries`；词条含 `scope`（ui/menu）、`source`、`target`、`enabled`，可附 category/note。拒绝未知字段、重复键、超限输入、无效 Unicode 和代码/正则字段。原文精确匹配，数据使用 JSON 序列化注入；禁用项阻止回退翻译。包含嵌套链接/按钮的整段自定义译文不会强行打平交互节点，由既有只读系统规则处理；单个链接/按钮自身文本可覆盖。

词典保存采用同目录临时文件替换，`custom-dictionary.lock` 是一字节 OS 锁文件，不含词典内容，不是代理日志或备份。损坏文件从有效导入恢复前另存为 `.corrupt-时间戳`；保存时检测其他窗口的修改。安装内部 `.antigravity-zhcn.json` 在暂存阶段写入词典修订/hash，成功切换后才可视为已应用；UI 同时核对实际安装与内容 hash。

安装任务使用 Windows 命名互斥锁；CLI 和官方更新器不参与该锁，因此共享核心仍检查切换前状态。代理预览记录匹配快捷方式与启动文件，执行前重新生成计划并比较；变化时停止。长任务期间不允许强制取消或关闭窗口，避免打断切换。会话日志不永久落盘，诊断导出只允许固定元数据，不包含原始日志、用户名路径或代理地址。
