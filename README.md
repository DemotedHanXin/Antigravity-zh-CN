# Antigravity-zh-CN

[English](README_EN.md) | 简体中文

为 Antigravity 桌面端提供中文界面补丁、汉化还原，以及 Windows 代理启动与快捷方式管理。运行脚本使用 Python 标准库，不需要安装 pip 依赖。

本分支基于 [MIMICTE/Antigravity-zh-CN](https://github.com/MIMICTE/Antigravity-zh-CN) 扩展。翻译规则以 v2.21.1 的文件结构为基础，不保证所有版本的文本覆盖率。本次修复针对仓库中的 **Python 源码**；旧版 Release 中的可执行程序需要重新打包后才包含这些修复。

## 本次新增与修复

- **汉化前验证安装完整性**：检查 ASAR 结构、文件路径和应用入口，补齐 `app.asar.unpacked` 中的外置依赖；先在临时目录完成解包与注入，验证通过后才切换。
- **保护可运行代码**：缺少或损坏原版归档时停止还原，不再把唯一的 `resources/app` 删除；目录删除失败会报告错误，不再静默提示成功。
- **自定义安装目录**：汉化、还原和代理工具均支持 `--app-dir`。发现多个安装时要求明确选择，不猜测目标。
- **代理启动器与快捷方式修复**：生成 `.cmd`、`.ps1`，修改匹配的 `.lnk`，保留原始启动参数、图标和工作目录。
- **不新增代理备份**：Setup 和 Cleanup 不再生成备份目录、归档或还原记录；自定义扫描目录记录在现有 `.ps1` 的注释中。
- **清理保留快捷方式**：先将匹配入口改回 EXE，再直接删除两个代理启动文件；需要代理时重新运行 Setup。
- **启动条件检查**：代理配置前检查 PowerShell 执行策略；不修改全局策略，也不绕过组织策略。公共开始菜单写入失败时，尝试创建个人入口并报告未处理项。

实现细节、状态转换、文件用途和验证范围见 [项目状态与代码说明](PROJECT_STATUS.md)。

## 运行条件与准备

| 功能 | 环境 |
| --- | --- |
| 汉化、还原 | Python 3.8+；Windows 或 macOS 的路径与进程处理分支 |
| 代理启动与快捷方式 | Windows、Python 3.8+、系统自带 Windows PowerShell 与 WScript.Shell |
| 本次验证环境 | Windows、Python 3.11；macOS 和其他 Antigravity 版本仍需实际验证 |

下载完整仓库，保留脚本依赖：`Antigravity-Patcher.py`、`Restore.py` 依赖同目录的 `antigravity_common.py`；`Cleanup-Proxy-Shortcuts.py` 依赖同目录的 `Setup-Proxy-Shortcuts.py`。

```powershell
git clone https://github.com/DemotedHanXin/Antigravity-zh-CN.git
cd Antigravity-zh-CN
python --version
```

请先保存 Antigravity 中的工作。汉化和还原会关闭目标应用以切换安装文件；`--no-launch` 只禁止完成后的自动启动。代理 Setup/Cleanup 不结束正在运行的软件。

## 汉化与还原

```powershell
# 自动查找安装目录并汉化
python Antigravity-Patcher.py

# 指定包含 Antigravity.exe 的目录；完成后不自动启动
python Antigravity-Patcher.py --app-dir "D:\Apps\Antigravity" --no-launch

# 恢复英文原版；自定义安装使用同一个目录
python Restore.py --app-dir "D:\Apps\Antigravity" --no-launch
```

macOS 使用 `python3`，`--app-dir` 指向整个 `.app`，例如：

```bash
python3 Antigravity-Patcher.py --app-dir "/Applications/Antigravity.app" --no-launch
python3 Restore.py --app-dir "/Applications/Antigravity.app" --no-launch
```

汉化会将原版 `resources/app.asar` 改名保留为 `app.asar.disabled`，并生成汉化后的 `resources/app`。**`.disabled` 是恢复原版所需的原始归档，不是代理备份残留，请勿手动删除。** `app.asar.unpacked` 是官方运行依赖，也应保留。

如果同时存在 `app.asar` 和 `app.asar.disabled`，工具会停止，避免把更新后的归档与旧版代码混用。缺少有效原版归档时也会停止；此时应通过官方安装程序修复安装，不能依靠删除 `resources/app` 修好。

## Windows 代理启动修复

适用于代理软件已开启 **Windows 系统代理的 HTTP／混合端口**，但 Antigravity 没有继承所需代理环境的情况。

```powershell
# 查看将处理的安装与快捷方式
python Setup-Proxy-Shortcuts.py --dry-run

# 创建启动器并修改快捷方式
python Setup-Proxy-Shortcuts.py

# 自定义安装与快捷方式目录；--scan-root 可以重复使用
python Setup-Proxy-Shortcuts.py --app-dir "D:\Apps\Antigravity" --scan-root "D:\Shortcuts" --scan-root "E:\Launchers"
```

脚本扫描当前用户和公共桌面、开始菜单、启动项及 Quick Launch／任务栏中的 `.lnk`，只处理指向所选安装的快捷方式。没有可用开始菜单入口时，会创建个人入口；权限不足的共享入口仍会单独报告。名称相似的其他软件不会被当作 Antigravity。

每次通过修复后的快捷方式启动，会读取当时的 Windows 系统代理，将 `HTTP_PROXY`、`HTTPS_PROXY` 等变量设置到本次进程中，再启动同目录的 EXE。不会固定使用某个用户名、安装盘符或代理端口，也不会修改 Windows 全局代理设置。

配置完成后，请完全退出 Antigravity，再通过修复后的快捷方式启动。运行中的旧进程不会自动获得新环境变量。

### 清理并改回 EXE 启动

```powershell
python Cleanup-Proxy-Shortcuts.py --dry-run
python Cleanup-Proxy-Shortcuts.py

# 旧版启动器没有扫描目录记录时，需要再次提供 --scan-root
python Cleanup-Proxy-Shortcuts.py --app-dir "D:\Apps\Antigravity" --scan-root "D:\Shortcuts"

# 以后重新启用代理启动
python Setup-Proxy-Shortcuts.py
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
- 完成后的自动启动失败，不等于汉化／还原文件修改失败；应根据输出分别判断。`--no-launch` 可用于只处理安装文件。
- 当前翻译依赖应用文件布局。新版本可能需要调整规则；不承诺所有版本、所有文本或所有平台均已验证。

## 测试与代码说明

```powershell
python -B -m unittest discover -s tests -v
```

测试使用隔离目录及模拟的进程控制，覆盖归档校验、外置依赖、汉化／还原失败保护、快捷方式参数、扫描目录和不产生代理备份等行为，不应直接对正在使用的安装运行变更测试。

更详细的模块入口、文件状态和维护说明见 [PROJECT_STATUS.md](PROJECT_STATUS.md)。

## 界面示例

![Antigravity 中文界面示例](antigravity-chinese.png)

示例不代表所有版本、动态内容或模型输出均已翻译。新增词条可修改 `Antigravity-Patcher.py` 中的翻译字典，再运行汉化脚本。

## 贡献与许可

参阅 [贡献指南](CONTRIBUTING.md) 和 [MIT License](LICENSE)。问题可提交到 [本分支 Issues](https://github.com/DemotedHanXin/Antigravity-zh-CN/issues)。上游项目为 [MIMICTE/Antigravity-zh-CN](https://github.com/MIMICTE/Antigravity-zh-CN)。
