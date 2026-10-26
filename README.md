# Antigravity-zh-CN

<div align="center">

**🌏 [English](README_EN.md) | 简体中文**

一个为 Google Antigravity 桌面端提供完整中文界面的开源汉化补丁

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

</div>

---

## 📖 项目简介

**Antigravity v2.21.1 一键汉化补丁** - 为 Google Antigravity 桌面端提供完整的中文界面支持。

## ✨ 核心特性

- 🚀 **零依赖 (Zero Dependencies)** - 自带纯原生 Python 编写的 ASAR 解析与打包算法，无需安装 Node.js，无需 npm，无需 `asar` 命令行工具
- 🎯 **智能文本匹配** - 采用底层 `indexOf` 碎片化重组与 CSS 伪类多态匹配策略，完美绕过 Webpack 代码分割导致的汉化失效问题
- ⚡ **一键部署** - 执行补丁后自动清理进程并重启软件，实现"敲下回车 → 享受中文"的无缝体验
- 🛡️ **纯净可逆** - 还原脚本可彻底抹除所有汉化残留，确保随时能"无损回滚"至纯血官方英文版
- 🧭 **全动态跨平台寻址** - 智能识别系统架构，原生支持 Windows 及 macOS 环境下的路径寻址与进程管理

## 📦 下载与安装

### 方式一：独立免安装版 (Windows / macOS) ⭐ 推荐普通用户

**下载：** [前往 Release 下载对应系统版本](https://github.com/MIMICTE/Antigravity-zh-CN/releases/latest) (支持 Windows x64, macOS Intel/M芯片)

**特点：**
- ✅ 开箱即用，**无需安装 Python** 环境
- ✅ 原生级体验，一键执行，自动识别路径并重启

**【Windows 用户使用方法】**
1. 下载 `Antigravity-zh-CN-v2.21.1-windows-x64.zip` 并解压
2. 双击运行 `Antigravity-Patcher.exe` 开始汉化 (还原请双击 `Restore.exe`)

**【macOS 用户使用方法】**
1. 下载对应的 macOS 压缩包（`arm64`为M系列芯片，`x86_64`为Intel芯片）并解压
2. 打开终端 (Terminal)，进入解压目录，赋予执行权限并运行：
   ```bash
   chmod +x Antigravity-Patcher-macOS-*
   ./Antigravity-Patcher-macOS-*
   ```
> 🍎 **Mac 用户注意**：若系统提示“无法打开，因为无法验证开发者”，请前往「系统设置 -> 隐私与安全性」，向下滑动并点击「仍要打开」。或者在终端执行 `xattr -cr Antigravity-Patcher-macOS-*` 即可解除限制。

---

### 方式二：从源码安装 ⭐ 推荐开发者

**克隆仓库：**
```bash
git clone https://github.com/MIMICTE/Antigravity-zh-CN.git
cd Antigravity-zh-CN
python Antigravity-Patcher.py
```

**或下载源码压缩包：**

从 [Releases 页面](https://github.com/MIMICTE/Antigravity-zh-CN/releases/latest) 下载 `Source code (zip)` 或 `Source code (tar.gz)`，解压后运行 `Antigravity-Patcher.py`。

### Windows 代理快捷方式修复

如果 Windows 系统代理已开启，但 Antigravity 启动后卡在加载界面，可运行独立的单文件脚本 [Setup-Proxy-Shortcuts.py](Setup-Proxy-Shortcuts.py)。它使用 Python 标准库和 Windows 自带的 PowerShell，**无需安装 pip 依赖**：

```powershell
python Setup-Proxy-Shortcuts.py
```

脚本会在软件安装目录部署 `Antigravity-Proxy.cmd` 和 `Antigravity-Proxy.ps1`，扫描当前用户及公共桌面、开始菜单、启动项目，以及 Quick Launch / 任务栏目录中的 `.lnk`，修复匹配的 Antigravity 快捷方式并保留原有启动参数。改动前会备份文件，完成后输出备份目录及还原命令。之后每次通过修复后的快捷方式启动，都会读取当时的 Windows 系统代理，仅为本次软件进程配置代理；关闭系统代理时会清除继承的代理变量。

常用选项：

```powershell
# 只预览，不修改文件
python Setup-Proxy-Shortcuts.py --dry-run
# 指定包含 Antigravity.exe 的安装目录，并额外扫描多个自定义目录
python Setup-Proxy-Shortcuts.py --app-dir "D:\Apps\Antigravity" --scan-root "D:\Shortcuts" --scan-root "E:\Launchers"
# 将 BACKUP 替换为脚本输出的完整备份目录
python Setup-Proxy-Shortcuts.py --restore "BACKUP"
```

- `--scan-root` 可重复使用。部分 Windows 固定项不以 `.lnk` 保存，无法由此脚本直接修复；自定义快捷方式目录需要用此选项补充。
- 不支持 PAC 自动代理脚本，检测到后会明确报错；请使用 HTTP / 混合端口的系统代理，或关闭 Windows 代理脚本后使用 TUN。
- 脚本不会重启正在运行的软件；请完全退出 Antigravity，再从修复后的快捷方式启动，使设置生效。
- 默认以普通用户运行；仅在公共桌面、公共开始菜单等共享目录提示权限不足时，再以管理员身份运行。

### 移除代理启动器并恢复 EXE 快捷方式

运行 [Cleanup-Proxy-Shortcuts.py](Cleanup-Proxy-Shortcuts.py) 可退出代理启动方案，同时保留应用快捷方式。请将它与 `Setup-Proxy-Shortcuts.py` 放在同一目录，无需额外安装依赖。

```powershell
# 先预览将改回 EXE 的快捷方式和待删除的启动文件
python Cleanup-Proxy-Shortcuts.py --dry-run
# 执行清理
python Cleanup-Proxy-Shortcuts.py
# 以后需要代理启动时，重新创建启动文件并配置快捷方式
python Setup-Proxy-Shortcuts.py
```

脚本将所有扫描到的、直接指向 `Antigravity-Proxy.cmd` 或 `Antigravity-Proxy.ps1` 的 `.lnk` **保留并改回同一安装目录中的 `Antigravity.exe`**，恢复编码前的原始启动参数、保留图标和工作目录，并改为正常显示窗口。只有在相关快捷方式全部处理成功后，才删除安装目录里的这两个代理启动文件。原有 EXE 快捷方式、其他软件入口和 `antigravity-proxy-backups` 旧修复备份均保留。支持 `--app-dir` 和可重复的 `--scan-root`，也会检查旧修复记录中的自定义快捷方式；不识别的启动器参数会报错并保留原状。

清理脚本使用直接删除，不进入回收站，**不创建备份、归档、日志或还原文件**，也不再提供 `--backup-dir` 和 `--restore`。以后需要代理启动时，只需重新运行 `Setup-Proxy-Shortcuts.py` 创建启动文件并配置快捷方式。脚本只在内存中校验待处理文件，若文件发生变化或快捷方式处理失败，会停止后续操作。此前已经存在的历史备份不会自动删除。脚本不会修改软件本体、汉化文件或全局代理，也不会结束正在运行的软件。清理后的快捷方式直接启动 EXE，不再自动注入代理。部分 Windows 固定项不是 `.lnk`，不属于脚本处理范围。

## 💡 技术原理

本项目利用 Electron 框架机制实现汉化：

### 1. 免打包劫持 (Unpacked Patching)
禁用官方 `app.asar` 文件，迫使软件读取注入了汉化代码的解包 `app` 文件夹。

### 2. 动态 DOM 拦截 (Dynamic DOM Interception)
在 `preload.js` 中注入 `MutationObserver`，实时监控页面 DOM 变化并替换英文文本为中文。

### 3. 原生 ASAR 解析器
使用纯 Python 实现的 ASAR 文件格式解析器，零外部依赖。

## ⚠️ 已知限制

- **思考日志为英文** - 受限于大模型的即时流式输出架构，智能体后台生成的思考日志（`Thought` 过程）无法汉化，但所有最终回复与前端界面均已 100% 汉化
- **多平台支持** - 目前已完美适配 Windows 以及 macOS (Intel & M芯片) 平台，Linux 暂不支持
- **版本依赖** - 针对 Antigravity v2.21.1 深度优化，其他版本亦具备高度兼容性

## 📸 效果展示

<div align="center">

![antigravity-chinese](antigravity-chinese.png)

*汉化后的 Antigravity 界面 - 所有文本已完全汉化*

</div>

**界面完全汉化包括：**
- ✅ 侧边栏菜单（新建对话、历史对话、计划任务、项目）
- ✅ 顶部导航栏（文件、音频、窗口）
- ✅ 输入框提示文本和模型选择器
- ✅ 设置页面所有选项和说明
- ✅ 底层终端操作权限请求弹窗及动态状态提示

> 💡 提示：要查看实际效果，双击运行 `Antigravity-Patcher.exe` 或 `Antigravity-Patcher.py` 即可体验完整的中文界面！

## 🔐 安全性说明

本项目是完全开源和安全的：

### ✅ 我们做了什么

- **仅修改界面文本** - 只在前端层面替换显示文本，不涉及网络通信、数据收集、账号信息访问
- **开源透明** - 所有代码完全开源，无混淆、无加密、无隐藏逻辑
- **可逆操作** - 提供完整的还原机制，一键恢复原版
- **零外部依赖** - 纯 Python 标准库实现，不连接外部服务器

### 🛡️ 技术原理

1. **ASAR 解包** - 使用纯 Python 解析 Electron 的 ASAR 打包格式
2. **代码注入** - 在 `preload.js` 和 `menu.js` 中追加翻译代码
3. **DOM 监听** - 使用 `MutationObserver` 监听页面变化
4. **文本替换** - 通过字典匹配将英文替换为中文

### 关于免安装可执行版 (Windows .exe / macOS 二进制文件)

- 该版本使用 [PyInstaller](https://pyinstaller.org/) 开源工具打包
- 包含完整的 Python 运行时环境（因此文件较大约 8 MB）
- Windows 下可能被部分杀毒软件误报，这是 PyInstaller 的已知问题
- macOS 下可能被系统提示“无法验证开发者”，这是因为缺少苹果付费签名
- 如有安全顾虑，推荐使用“从源码安装”的方式（代码完全透明）

整个过程不涉及任何逆向工程或破解行为。

## ❓ 常见问题

<details>
<summary><b>Q: Mac 版本运行提示“无法打开，因为无法验证开发者”怎么办？</b></summary>

A: 这是由于 Mac 的 Gatekeeper 门禁机制引起的（由于本项目是开源免费工具，未购买苹果开发者签名）。解决方法：
1. 方式一：前往「系统设置」 -> 「隐私与安全性」，向下滑动并点击「仍要打开」。
2. 方式二：在终端执行 `xattr -cr 你下载的程序路径` 即可一键解除限制。
</details>

<details>
<summary><b>Q: Python 脚本版和免安装版本有什么区别？</b></summary>

A: 
- **Python 脚本版**：需要 Python 环境，文件小，代码透明
- **免安装版本**：无需 Python，开箱即用，但文件较大且可能被杀毒软件误报

两者功能完全相同，推荐根据自己的需求选择。
</details>

<details>
<summary><b>Q: 为什么 .exe 文件这么大？</b></summary>

A: .exe 文件包含了完整的 Python 运行时环境，所以约 8 MB 是正常的。
</details>

<details>
<summary><b>Q: 杀毒软件报毒怎么办？</b></summary>

A: 这是 PyInstaller 打包的已知问题，非真实病毒。可以：
- 添加到杀毒软件白名单
- 使用 Python 脚本版代替（推荐）
- 上传到 [VirusTotal](https://www.virustotal.com/) 验证
</details>

<details>
<summary><b>Q: 为什么执行脚本时提示 "Python 不是内部或外部命令"？</b></summary>

A: 这说明 Python 没有添加到系统环境变量中。请重新安装 Python，并在安装时勾选 "Add Python to PATH" 选项，或者直接使用无需 Python 环境的 `.exe` 版本。
</details>

<details>
<summary><b>Q: 为什么有时 Antigravity 打开没有界面？是因为这个脚本导致软件损坏了吗？</b></summary>

A: 通常这不是脚本损坏了软件，而是由 Electron 的后台残留机制导致的。遇到这种情况请排查：
1. 软件可能默认最小化到了右下角的**系统托盘**，请尝试双击托盘黑色的 `^` 图标唤醒。
2. Windows 任务管理器中可能残留了未完全关闭的 `Antigravity.exe` 僵尸进程。请按 `Ctrl+Shift+Esc` 结束所有 Antigravity 进程后再重新打开。
3. 如果依然白屏或无反应，可能是杀毒软件拦截了解包的核心代码文件。请运行 `Restore.exe` 恢复官方原版，关闭杀软拦截后再重新运行汉化补丁即可满血复活。
</details>

<details>
<summary><b>Q: Antigravity 官方每次更新项目后，这个汉化补丁能不能继续使用？</b></summary>

A: **可以无缝继续使用！** 
从 v2.21.1 版本开始，脚本引入了 **OTA 智能兼容机制**。当官方软件更新时，会释放新的核心文件，此时汉化会自动失效并短暂恢复为英文原版。您只需要**重新运行一次汉化补丁**，脚本会自动侦测到版本发生变化，自动清理旧版缓存并基于官方最新代码重新解包注入，完全兼容后续版本更新。
</details>

<details>
<summary><b>Q: 这个补丁会影响软件的安全性吗？</b></summary>

A: 不会。本补丁仅修改界面文本显示，不涉及网络通信、数据加密、账号认证、核心功能逻辑。所有修改都在前端层面，不影响软件与服务器的通信。
</details>

<details>
<summary><b>Q: 如何添加新的翻译？</b></summary>

A: 编辑 `Antigravity-Patcher.py` 文件中的 `dictionary` 字典，添加键值对：
```python
"English Text": "中文翻译",
```
然后重新执行汉化脚本。
</details>

<details>
<summary><b>Q: 支持其他操作系统吗？</b></summary>

A: 目前仅支持 Windows。macOS 和 Linux 版本的路径和机制不同，需要单独适配。
</details>

更多问题？欢迎在 [GitHub Issues](../../issues) 或 [Discussions](../../discussions) 中提问！

## 🤝 参与贡献

欢迎提交 Issue 和 Pull Request！

- 发现翻译错误或遗漏？请提交 [Issue](../../issues) 或直接 PR 修改
- 有更好的技术方案？欢迎在 [Discussions](../../discussions) 讨论

详细的贡献指南请查看 [CONTRIBUTING.md](CONTRIBUTING.md)

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

## ⚠️ 免责声明

- 本项目仅供学习交流使用
- 使用本补丁造成的任何问题由用户自行承担
- 请使用正版 Antigravity 软件
- 请遵守 Antigravity 的服务条款

## 🌟 Star History

如果这个项目对你有帮助，请考虑给它一个 Star ⭐️

## 📧 联系方式

- Issues: [GitHub Issues](../../issues)
- Discussions: [GitHub Discussions](../../discussions)

---

<div align="center">

**Made with ❤️ by Antigravity-zh-CN Contributors**

</div>
