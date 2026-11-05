# Antigravity-zh-CN

[English](README_EN.md) | 简体中文

为 Antigravity 桌面端提供中文界面补丁、汉化还原，以及 Windows 代理启动与快捷方式管理。命令行工具使用 Python 标准库；统一管理器需要 PySide6。

本分支基于 [MIMICTE/Antigravity-zh-CN](https://github.com/MIMICTE/Antigravity-zh-CN) 扩展。原有翻译规则以 v2.21.1 的文件结构为基础；新增的 2.28.2 接入范围见下文，不保证所有版本的文本覆盖率。本次开发针对仓库中的 **源码**；旧版 Release 中的可执行程序需要重新打包后才包含这些改动。

## Windows 管理器分阶段开发

在 `feat/DragonGirl` 上按 M0–M5 顺序开发 Python + PySide6 管理器。每阶段交付记录文档、本地提交和附注标签，等待用户审核通过后才继续；不自动推送、合并或发布。当前 **M0–M2 已获批准，M3 统一管理器已完成、待审核；M4 尚未开始**。

需求和架构见 [M0 基线与开发约定](docs/development/M0-baseline.md)，当前实现与验证见 [M3 阶段记录](docs/development/M3-unified-manager.md) 和 [开发进度](docs/development/PROGRESS.md)。Windows 安装包属于 M4。

源码管理器启动（Windows、Python 3.11+）：

```powershell
python -m pip install -r requirements-manager.txt
python -m antigravity_manager
# 首次审核建议用独立数据目录；不会自动汉化、启动应用或测试 API
python -m antigravity_manager --data-dir .m3-lab/review
```

## DragonGirl 开发版：请先了解状态

**M1 已获审核通过，源码提供 Antigravity 2.28.2 / Windows x64 的限定兼容 profile：`antigravity-2.28.2-win32-x64-navigation`，未发布。** 匹配同时核对入口、preload、窗口／服务模块及外置 `language_server.exe` 的指纹，并绑定实际应用窗口与动态本地服务。

重新汉化匹配版本时，旧的广域 DOM observer 会停用，网页翻译范围缩小为根路径 `/`、无 query/hash 时的四个导航正文标签：**New Conversation、Automations、Customizations、Settings**。其他页面正文、Projects 和同名 aria-label 不在此 profile 范围内；原生菜单仍沿用静态汉化。未匹配版本保留原有同步汉化路径。

这四个标签目前都命中内置词典，正常运行不会由它们产生自然未命中的 AI 请求。隔离实测通过人为未命中和本地固定提供方验证了请求、显示、失败、关闭、导航及服务恢复链路，**没有验证真实提供方的页面补译**。仅更新仓库源码不会修改日常安装；需另行对目标安装执行汉化才会应用新 profile。

- 统一管理器：`python -m antigravity_manager`；旧 Tk 设置工具仍保留。
- 个人词典 → 内置词典／规则 → 有效待确认译文 → AI；AI 默认关闭，原生菜单不接个人覆盖或 AI。
- 新 AI 结果统一进入独立候选，首次生成后保留 7 天、复用不续期；采纳后才进入个人词典，拒绝持续抑制直到解除。
- 词典／审核 CLI：`python src/localization/Translation-Dictionary.py --help`；内置数据在 `localization_runtime/builtin-dictionary.json`，正则逻辑仍由代码维护。
- OpenAI Responses、Gemini generateContent、Claude Messages 及自定义 OpenAI 兼容 Chat Completions 四种协议。
- Windows 密钥使用当前用户 DPAPI 保护，已有明文配置在首次读取时迁移；配置/个人词典不会随汉化更新或还原删除。跨账户无法直接解密。
- 连接测试为单独、需确认的可能计费操作，需要外部 Node；通过不表示真实应用桥接可用。

完整使用方式和边界见 [DragonGirl 说明](docs/DRAGONGIRL.md)；实测证据、最新回归结果及未验证范围见 [M1 阶段记录](docs/development/M1-real-integration.md)。macOS 桥接、真实 AI 页面补译、GUI／冻结包及完整应用覆盖仍未验收。

M2 首次读取旧配置时会迁移到 schema2，保留全部旧手工和历史 AI 词条；历史 AI 标为未审核，不进入过期清理。M3 将含密钥配置保护为磁盘 schema3。请同步更新应用内翻译组件，旧组件遇到新格式会暂停增强翻译。源码开发和隔离测试没有迁移日常用户数据；回退 Git 不等于数据降级。

## 原有功能与修复

- **汉化前验证安装完整性**：检查 ASAR 结构、文件路径和应用入口，补齐 `app.asar.unpacked` 中的外置依赖；先在临时目录完成解包与注入，验证通过后才切换。
- **保护可运行代码**：缺少或损坏原版归档时停止还原，不再把唯一的 `resources/app` 删除；目录删除失败会报告错误，不再静默提示成功。
- **自定义安装目录**：汉化、还原和代理工具均支持 `--app-dir`。发现多个安装时要求明确选择，不猜测目标。
- **代理启动器与快捷方式修复**：生成 `.cmd`、`.ps1`，修改匹配的 `.lnk`，保留原始启动参数、图标和工作目录。
- **不新增代理备份**：Setup 和 Cleanup 不再生成备份目录、归档或还原记录；自定义扫描目录记录在现有 `.ps1` 的注释中。
- **清理保留快捷方式**：先将匹配入口改回 EXE，再直接删除两个代理启动文件；需要代理时重新运行 Setup。
- **启动条件检查**：代理配置前检查 PowerShell 执行策略；不修改全局策略，也不绕过组织策略。公共开始菜单写入失败时，尝试创建个人入口并报告未处理项。

实现细节、状态转换、文件用途和验证范围见 [项目状态与代码说明](PROJECT_STATUS.md)。

## 目录结构

```text
src/
├── localization/                     # 原作者汉化、还原及相关扩展
│   ├── Antigravity-Patcher.py
│   ├── Restore.py
│   ├── antigravity_common.py
│   ├── Translation-Settings.py
│   ├── translation_config.py
│   ├── translation_integration.py
│   └── Inspect-Translation-Compatibility.py
└── proxy/                            # 本分支的代理与快捷方式工具
    ├── Setup-Proxy-Shortcuts.py
    └── Cleanup-Proxy-Shortcuts.py
localization_runtime/                 # JavaScript 运行时与兼容注册表
tests/                                # Python / JavaScript 隔离测试
docs/                                 # DragonGirl 使用与验证说明
```

下文命令均从仓库根目录执行。Python 入口已迁入 `src`；从其他工作目录运行时，请使用入口脚本的完整路径。

## 运行条件与准备

| 功能 | 环境 |
| --- | --- |
| 汉化、还原 | Python 3.8+；Windows 或 macOS 的路径与进程处理分支 |
| 代理启动与快捷方式 | Windows、Python 3.8+、系统自带 Windows PowerShell 与 WScript.Shell |
| 原有修复记录 | 历史 Windows/Python 3.11 验证见 PROJECT_STATUS；不代表 DragonGirl 真机验证 |
| DragonGirl 开发测试 | Python、Node 22+；隔离模拟不等于真实应用兼容 |

下载完整仓库并保留上述目录结构。汉化、还原、设置 GUI 和兼容检查工具通过同目录模块导入依赖；运行时资源按源码位置查找仓库根目录的 `localization_runtime/`，不依赖当前工作目录。Cleanup 从自身所在目录加载 Setup，两个代理脚本应一起保留。

```powershell
git clone https://github.com/DemotedHanXin/Antigravity-zh-CN.git
cd Antigravity-zh-CN
python --version
```

请先保存 Antigravity 中的工作。汉化和还原会关闭目标应用以切换安装文件。汉化完成后只输出处理结果，不自动启动应用；还原可使用 `--no-launch` 禁止完成后的自动启动。代理 Setup/Cleanup 不结束正在运行的软件。

## 汉化与还原

```powershell
# 自动查找安装目录并汉化
python src/localization/Antigravity-Patcher.py

# 指定包含 Antigravity.exe 的目录
python src/localization/Antigravity-Patcher.py --app-dir "D:\Apps\Antigravity"

# 恢复英文原版；自定义安装使用同一个目录
python src/localization/Restore.py --app-dir "D:\Apps\Antigravity" --no-launch
```

macOS 使用 `python3`，`--app-dir` 指向整个 `.app`，例如：

```bash
python3 src/localization/Antigravity-Patcher.py --app-dir "/Applications/Antigravity.app"
python3 src/localization/Restore.py --app-dir "/Applications/Antigravity.app" --no-launch
```

汉化脚本仍接受旧命令中的 `--no-launch` 参数；无论是否传入，完成后都不会自动启动应用。

汉化会将原版 `resources/app.asar` 改名保留为 `app.asar.disabled`，并生成汉化后的 `resources/app`。**`.disabled` 是恢复原版所需的原始归档，不是代理备份残留，请勿手动删除。** `app.asar.unpacked` 是官方运行依赖，也应保留。

如果同时存在 `app.asar` 和 `app.asar.disabled`，工具会停止，避免把更新后的归档与旧版代码混用。缺少有效原版归档时也会停止；此时应通过官方安装程序修复安装，不能依靠删除 `resources/app` 修好。

## Windows 代理启动修复

适用于代理软件已开启 **Windows 系统代理的 HTTP／混合端口**，但 Antigravity 没有继承所需代理环境的情况。

```powershell
# 查看将处理的安装与快捷方式
python src/proxy/Setup-Proxy-Shortcuts.py --dry-run

# 创建启动器并修改快捷方式
python src/proxy/Setup-Proxy-Shortcuts.py

# 自定义安装与快捷方式目录；--scan-root 可以重复使用
python src/proxy/Setup-Proxy-Shortcuts.py --app-dir "D:\Apps\Antigravity" --scan-root "D:\Shortcuts" --scan-root "E:\Launchers"
```

脚本扫描当前用户和公共桌面、开始菜单、启动项及 Quick Launch／任务栏中的 `.lnk`，只处理指向所选安装的快捷方式。没有可用开始菜单入口时，会创建个人入口；权限不足的共享入口仍会单独报告。名称相似的其他软件不会被当作 Antigravity。

每次通过修复后的快捷方式启动，会读取当时的 Windows 系统代理，将 `HTTP_PROXY`、`HTTPS_PROXY` 等变量设置到本次进程中，再启动同目录的 EXE。不会固定使用某个用户名、安装盘符或代理端口，也不会修改 Windows 全局代理设置。

配置完成后，请完全退出 Antigravity，再通过修复后的快捷方式启动。运行中的旧进程不会自动获得新环境变量。

### 清理并改回 EXE 启动

```powershell
python src/proxy/Cleanup-Proxy-Shortcuts.py --dry-run
python src/proxy/Cleanup-Proxy-Shortcuts.py

# 旧版启动器没有扫描目录记录时，需要再次提供 --scan-root
python src/proxy/Cleanup-Proxy-Shortcuts.py --app-dir "D:\Apps\Antigravity" --scan-root "D:\Shortcuts"

# 以后重新启用代理启动
python src/proxy/Setup-Proxy-Shortcuts.py
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
- 还原完成后的自动启动失败，不等于还原文件修改失败；应根据输出分别判断。还原时可使用 `--no-launch` 只处理安装文件；汉化始终只输出处理结果。
- 当前翻译依赖应用文件布局。新版本可能需要调整规则；不承诺所有版本、所有文本或所有平台均已验证。

## 测试与代码说明

```powershell
python -B -m unittest discover -s tests -v
node --test tests/js/*.test.cjs
```

测试使用隔离目录及模拟的进程控制，覆盖归档校验、外置依赖、汉化／还原失败保护、快捷方式参数、扫描目录和不产生代理备份等行为，不应直接对正在使用的安装运行变更测试。

更详细的模块入口、文件状态和维护说明见 [PROJECT_STATUS.md](PROJECT_STATUS.md)。

## 界面示例

![Antigravity 中文界面示例](antigravity-chinese.png)

这是历史界面示例，不代表 M1 的覆盖范围或所有版本、动态内容、模型输出均已翻译。内置数据在 `localization_runtime/builtin-dictionary.json`，个人修改通过词典工具保存为覆盖；匹配 profile 时仍受四个固定导航标签的范围限制，扩大范围需要另行验证兼容配置。

## 贡献与许可

参阅 [贡献指南](CONTRIBUTING.md) 和 [MIT License](LICENSE)。问题可提交到 [本分支 Issues](https://github.com/DemotedHanXin/Antigravity-zh-CN/issues)。上游项目为 [MIMICTE/Antigravity-zh-CN](https://github.com/MIMICTE/Antigravity-zh-CN)。
