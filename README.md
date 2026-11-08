# Antigravity-zh-CN

[English](README_EN.md) | 简体中文

为 Antigravity 桌面端提供中文界面补丁、汉化还原，以及 Windows 代理启动与快捷方式管理。运行脚本使用 Python 标准库，不需要安装 pip 依赖。

当前提供 **Windows 图形助手（测试版）和 Python 命令行工具**。图形助手包含安装检查、汉化/恢复、999 条普通词条的可视化管理和代理入口预览/配置/清理。设计素材见 [设计目录](doc/design/README.md)。翻译覆盖与兼容性取决于 Antigravity 版本和文件结构，实际验证边界见 [项目状态](doc/PROJECT_STATUS.md)。

## Windows 图形助手

使用本次本地构建：打开 `dist/AntigravityZhCN/AntigravityZhCN.exe`，或解压 `dist/AntigravityZhCN-0.1.0-windows-x64.zip` 后打开其中 EXE；请保留旁边的 `_internal` 文件夹。不需要安装 Python 或 Node.js。安装器与构建说明见 [packaging/README.md](packaging/README.md)。这些是本地测试产物，未签名、未发布 Release。

从源码启动（Windows x64，已验证 Python 3.12.10）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-app.txt
.\.venv\Scripts\python.exe main.py
```

可用 `main.py --app-dir "D:\Apps\Antigravity"` 明确选择安装，`--data-dir` 指定独立助手数据目录。`--smoke-test` 使用临时数据验证窗口及打包依赖后退出，不检查或修改真实安装。

- 概览中先选择安装，文件结构检查通过后预览并应用汉化；确认前保存 Antigravity 工作。汉化与恢复结束后不自动启动。
- 词典支持中英文搜索、添加、修改、禁用、恢复内置，以及 JSON 导入冲突预览、保留/覆盖选择、导出。动态规则只读。保存后需要重新应用汉化。
- 代理页面先预览，再按已核对的计划修复或移除入口；计划发生变化会停止并要求重新预览。不更改系统代理设置，配置完成不等于网络连通。
- 恢复与帮助提供恢复英文、会话详情、脱敏诊断导出，以及日夜主题、插画和文字大小设置。

偏好和个人词典默认位于 `%LOCALAPPDATA%/AntigravityZhCN/`。词典原子保存，损坏文件保留并提供从有效 JSON 恢复入口；多个助手窗口保存冲突会提示重开。升级或卸载助手保留个人词典，也不会替用户撤销 Antigravity 的汉化或代理配置。

## 项目来源与作者

| 角色 | 作者 | 仓库与工作范围 |
| --- | --- | --- |
| 上游原作者 | [MIMICTE](https://github.com/MIMICTE) 及上游贡献者 | [MIMICTE/Antigravity-zh-CN](https://github.com/MIMICTE/Antigravity-zh-CN)，提供原始汉化项目 |
| 当前分支作者与维护者 | [DemotedHanXin](https://github.com/DemotedHanXin)（Git 提交名 `Demoted_Han_Xin`） | [DemotedHanXin/Antigravity-zh-CN](https://github.com/DemotedHanXin/Antigravity-zh-CN)，在上游基础上扩展翻译、安装校验与还原保护、Windows 代理启动和快捷方式管理，并实现 Windows 图形助手 |

本仓库是上游项目的派生分支（fork），保留上游贡献与署名。上游及当前分支均使用 MIT 许可证，具体关系见本文末尾。它是社区维护的辅助工具，与 Antigravity 官方产品的发布和支持相互独立。

## 当前功能

- **汉化前验证安装完整性**：检查 ASAR 结构、文件路径和应用入口，补齐 `app.asar.unpacked` 中的外置依赖；先在临时目录完成解包与注入，验证通过后才切换。
- **保护可运行代码**：缺少或损坏原版归档时停止还原，不再把唯一的 `resources/app` 删除；目录删除失败会报告错误，不再静默提示成功。
- **自定义安装目录**：汉化、还原和代理工具均支持 `--app-dir`。发现多个安装时要求明确选择，不猜测目标。
- **代理启动器与快捷方式修复**：生成 `.cmd`、`.ps1`，修改匹配的 `.lnk`，保留原始启动参数、图标和工作目录。
- **不新增代理备份**：Setup 和 Cleanup 不再生成备份目录、归档或还原记录；自定义扫描目录记录在现有 `.ps1` 的注释中。
- **清理保留快捷方式**：先将匹配入口改回 EXE，再直接删除两个代理启动文件；需要代理时重新运行 Setup。
- **启动条件检查**：代理配置前检查 PowerShell 执行策略；不修改全局策略，也不绕过组织策略。公共开始菜单写入失败时，尝试创建个人入口并报告未处理项。

实现细节、状态转换、文件用途和验证范围见 [项目状态与代码说明](doc/PROJECT_STATUS.md)。

## 运行条件与准备

| 功能 | 环境 |
| --- | --- |
| 汉化、还原 | Python 3.8+；Windows 或 macOS 的路径与进程处理分支 |
| 代理启动与快捷方式 | Windows、Python 3.8+、系统自带 Windows PowerShell 与 WScript.Shell |
| 验证范围 | 当前测试结果见[项目状态](doc/PROJECT_STATUS.md)；macOS 和其他 Antigravity 版本仍需实际验证 |

下载完整仓库，保留脚本依赖：`src/Antigravity-Patcher.py`、`src/Restore.py` 依赖同目录的 `src/antigravity_common.py`；`src/Cleanup-Proxy-Shortcuts.py` 依赖同目录的 `src/Setup-Proxy-Shortcuts.py`。

```powershell
git clone https://github.com/DemotedHanXin/Antigravity-zh-CN.git
cd Antigravity-zh-CN
python --version
```

以下命令均在仓库根目录执行。请先保存 Antigravity 中的工作：汉化和还原会关闭目标应用以切换安装文件，完成后需手动打开软件。`--no-launch` 仅为兼容旧命令保留；无论是否传入，当前脚本均不自动启动软件。代理 Setup/Cleanup 不结束正在运行的软件。

## 汉化与还原

```powershell
# 自动查找安装目录并汉化
python src/Antigravity-Patcher.py

# 指定包含 Antigravity.exe 的目录
python src/Antigravity-Patcher.py --app-dir "D:\Apps\Antigravity"

# 恢复英文原版；自定义安装使用同一个目录
python src/Restore.py --app-dir "D:\Apps\Antigravity"
```

macOS 使用 `python3`，`--app-dir` 指向整个 `.app`，例如：

```bash
python3 src/Antigravity-Patcher.py --app-dir "/Applications/Antigravity.app"
python3 src/Restore.py --app-dir "/Applications/Antigravity.app"
```

汉化会将原版 `resources/app.asar` 改名保留为 `app.asar.disabled`，并生成汉化后的 `resources/app`。**`.disabled` 是恢复原版所需的原始归档，不是代理备份残留，请勿手动删除。** `app.asar.unpacked` 是官方运行依赖，也应保留。

如果同时存在 `app.asar` 和 `app.asar.disabled`，工具会停止，避免把更新后的归档与旧版代码混用。缺少有效原版归档时也会停止；此时应通过官方安装程序修复安装，不能依靠删除 `resources/app` 修好。

## Windows 代理启动修复

适用于代理软件已开启 **Windows 系统代理的 HTTP／混合端口**，但 Antigravity 没有继承所需代理环境的情况。

```powershell
# 查看将处理的安装与快捷方式
python src/Setup-Proxy-Shortcuts.py --dry-run

# 创建启动器并修改快捷方式
python src/Setup-Proxy-Shortcuts.py

# 自定义安装与快捷方式目录；--scan-root 可以重复使用
python src/Setup-Proxy-Shortcuts.py --app-dir "D:\Apps\Antigravity" --scan-root "D:\Shortcuts" --scan-root "E:\Launchers"
```

脚本扫描当前用户和公共桌面、开始菜单、启动项及 Quick Launch／任务栏中的 `.lnk`，只处理指向所选安装的快捷方式。没有可用开始菜单入口时，会创建个人入口；权限不足的共享入口仍会单独报告。名称相似的其他软件不会被当作 Antigravity。

每次通过修复后的快捷方式启动，会读取当时的 Windows 系统代理，将 `HTTP_PROXY`、`HTTPS_PROXY` 等变量设置到本次进程中，再启动同目录的 EXE。不会固定使用某个用户名、安装盘符或代理端口，也不会修改 Windows 全局代理设置。

配置完成后，请完全退出 Antigravity，再通过修复后的快捷方式启动。运行中的旧进程不会自动获得新环境变量。

### 清理并改回 EXE 启动

```powershell
python src/Cleanup-Proxy-Shortcuts.py --dry-run
python src/Cleanup-Proxy-Shortcuts.py

# 旧版启动器没有扫描目录记录时，需要再次提供 --scan-root
python src/Cleanup-Proxy-Shortcuts.py --app-dir "D:\Apps\Antigravity" --scan-root "D:\Shortcuts"

# 以后重新启用代理启动
python src/Setup-Proxy-Shortcuts.py
```

清理会保留 `.lnk`，将目标改回 `Antigravity.exe`，恢复编码前的启动参数并保留图标、工作目录。所有已扫描的代理入口处理成功后，才删除安装目录下的 `Antigravity-Proxy.cmd` 和 `Antigravity-Proxy.ps1`。

两个代理脚本均**不创建永久备份、日志或恢复归档**，不再支持 `--restore`／`--backup-dir`。删除使用文件系统直接删除，不进入回收站。历史版本已经生成的备份不会自动删除，也不会作为新的备份继续累积。

新版 Setup 把自定义扫描目录写入 `.ps1` 的注释元数据，Cleanup 可自动读回；不额外创建记录文件。旧版启动器没有这项记录，若旧备份也已删除，需在清理时补充原来的 `--scan-root`。显式指定或记录的目录不可访问时会停止，避免漏改快捷方式后删除启动器。

## 故障提示与适用范围

| 情况 | 处理方式 |
| --- | --- |
| 找不到安装或发现多个安装 | 用 `--app-dir` 指定 EXE 所在目录；macOS 指定 `.app` |
| 缺少归档、归档损坏、两个归档同时存在 | 保留现有文件，先修复官方安装，避免手动删掉唯一代码 |
| PowerShell 禁止执行脚本或要求签名 | Setup 会在写入前停止；按电脑或组织允许的方式处理策略，脚本不自动放宽限制 |
| 公共入口或 Program Files 拒绝访问 | 查看具体失败路径；需要相应写入权限。个人入口可作为共享入口失败时的回退 |
| 自定义扫描目录不存在 | 确认盘符已挂载、目录拼写正确；恢复可访问状态再运行 |
| 快捷方式在处理期间被修改 | 停止后续处理，重新预览，避免覆盖其他修改 |
| 任务栏出现两个图标或旧图标仍在 | CMD 入口与应用窗口的任务栏分组可能不同；固定项缓存可能需要重新固定。非 `.lnk` 固定项不在自动修复范围内 |

- 不解析 PAC，不支持标准 `socks=...` 纯 SOCKS 系统代理配置；使用 HTTP／混合端口。
- 系统代理关闭时按直连／TUN 处理，并清除继承的代理环境变量。仅通过环境变量提供代理的配置不属于此方案。
- 工具不检测代理客户端是否运行、端口是否连通、账号是否可用或目标服务是否可达。
- 自定义或移动到未知位置的快捷方式需要 `--scan-root`，不能保证找到任意位置、其他用户账户或所有 Windows 固定项。
- 汉化和还原完成后需手动打开软件；使用代理时从修复后的快捷方式启动。
- 当前翻译依赖应用文件布局。新版本可能需要调整规则；不承诺所有版本、所有文本或所有平台均已验证。

## 测试与代码说明

```powershell
python -B -m unittest discover -s tests -v
```

测试使用隔离目录及模拟的进程控制，覆盖归档校验、外置依赖、汉化／还原失败保护、快捷方式参数、扫描目录和不产生代理备份等行为。部分翻译测试还需要 Node.js 或 Chrome/Edge，环境缺失时会跳过；这些是测试工具，不是运行脚本的 pip 依赖。不应直接对正在使用的安装运行变更测试。

更详细的模块入口、文件状态和维护说明见 [PROJECT_STATUS.md](doc/PROJECT_STATUS.md)。

## 贡献与许可

新增词条可修改 `src/Antigravity-Patcher.py` 中的翻译字典，再运行汉化脚本。提交方式、翻译约定与测试要求见[贡献指南](CONTRIBUTING.md)，代码变更请提交到[当前分支的 Pull Requests](https://github.com/DemotedHanXin/Antigravity-zh-CN/pulls)。截至 2026-11-08，当前仓库尚未启用 Issues 和 Discussions；问题反馈入口以仓库实际开放情况为准。

上游以 [MIT License](https://github.com/MIMICTE/Antigravity-zh-CN/blob/main/LICENSE) 发布，当前分支沿用 [MIT License](LICENSE)。本仓库保留原版权声明 `Copyright (c) 2026 Antigravity-zh Contributors`；当前作者的维护与新增贡献不替代上游署名。复制或分发本项目及其实质性部分时，应保留版权声明和许可全文；软件按许可证约定以“原样”提供。

本项目的 MIT 许可适用于本项目代码及随附文档，不等于取得 Antigravity 本体、商标或第三方素材的额外授权；这些内容的权利归各自权利人。
