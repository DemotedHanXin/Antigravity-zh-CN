# DragonGirl：AI 补译开发版使用与验证说明

> **当前没有经过真实 Antigravity 安装验证的兼容配置。** 随源码提供的 `localization_runtime/compatibility.json` 中 `profiles` 为空。现有内置词典汉化继续使用；真实应用中的个人词典接入和 AI 补译不会自动启用。保存配置、连接测试通过、模拟测试通过，都不等于真实应用桥接已经可用。

## 1. 已提供的组件与明确边界

- 独立 Tkinter GUI，管理四类提供商、AI 开关、自动保存开关、个人词典和缓存失效标记。
- Python / Node 共用的用户目录、版本化 JSON、跨进程锁与原子替换；词条手工编辑优先、删除记录防止旧结果恢复词条。
- 主进程翻译服务、受限 IPC、去重/缓存/队列/限流与四种提供商适配器。
- 默认空白名单的 DOM 补译模块，异步回写前检查原文、节点、导航和配置/词典版本。
- 只读兼容性检查工具与受指纹约束的注入流程。只有经审查的匹配 profile 才可以增加主进程桥接；没有匹配时保留原有同步汉化。

这些组件可通过隔离模拟测试检查，但 **Windows/macOS 真机桥接、目标应用 UI 白名单、原生 GUI 外观、冻结包运行以及真实提供商兼容性仍需独立验收**。本分支没有把真实 API 请求或完整应用验收当作已经通过。

翻译顺序为内置词典/规则 → 个人词典 → AI；个人词典不覆盖内置命中。AI 失败、关闭或响应不合法时保留原文。原生菜单仍使用现有内置词典，不接个人词典和 AI。配置和词典编辑可以先使用；没有真实兼容 profile 时，它们不会注入实际应用页面。

## 2. 启动设置界面

从完整源码目录运行：

```bash
python Translation-Settings.py
# macOS 如需使用 python3：
python3 Translation-Settings.py
```

需要带 Tk 的 Python 和可用桌面显示环境。导入模块不会弹出 GUI、修改安装或发起网络请求。缺少 Tk/显示环境会说明不可用，而不是绕过检查。单纯编辑配置不要求 Node；可选连接测试需要 `node` 在 PATH 中，并随源码/冻结包附带 `localization_runtime/probe.cjs`。

首次默认 `enabled=false`、`autoSave=false`；地址有官方默认值，模型和密钥留空。自行填写提供商、模型、密钥，并明确保存。**保存配置不自动勾选启用 AI；勾选启用也不能绕过兼容 profile 检查。** 模型名称和账户额度由所选服务决定，不自动查询或承诺免费额度。

连接测试必须主动点击并确认可能产生费用，使用已保存配置和固定测试文案，不采集正在编辑的页面内容。缺少 Node/测试资源会报告不可用；测试只返回脱敏状态。没有自动测试连接、自动切换提供商或后台模型枚举。命令行主动测试方式：

```bash
# 此命令会发起真实网络请求，可能计费；仅在明确同意且配置完成后运行。
node localization_runtime/probe.cjs --confirm-network --revision N
```

将 `N` 替换为您刚核对的 `config.json` 中 `revision` 整数；配置在确认后变化会拒绝请求。推荐使用 GUI，避免手工处理配置版本。命令行不要传入密钥或待翻译的工作内容。

## 3. 提供商协议与地址

| GUI 选项 | API 类型 | 默认 Base URL |
| --- | --- | --- |
| OpenAI | 原生 Responses | `https://api.openai.com/v1` |
| Gemini | 原生 generateContent | `https://generativelanguage.googleapis.com/v1beta` |
| Claude | 原生 Messages | `https://api.anthropic.com/v1` |
| OpenAI 兼容 | Chat Completions | 用户填写 |

Claude 第一版只支持不需要额外 workspace header 的 workspace-scoped API key；未提供任意自定义认证头，不承诺所有 Claude 凭据类型可用。该限制以实施时核对的官方 API 文档为依据，真实账户连接仍需用户主动测试。

填写 **Base URL**，不要重复附加 `/responses`、`/messages`、`/chat/completions` 或 Gemini 模型动作路径；适配器负责添加路径。四种协议不是互相替代的兼容模式。

当前网络层仅允许 HTTPS 公网目标和标准 HTTPS 端口，拒绝内嵌凭据、查询参数、片段、本机/私网解析与重定向认证转发；不支持本地 HTTP 模型服务器。自定义地址会接收该提供商密钥和筛选后的 UI 文案，务必核对主机。TLS 验证不会关闭。现有代理快捷方式工具不意味着新 API 请求已获得系统代理/PAC 支持，实际网络环境需另行验证。

## 4. 用户数据与明文密钥风险

| 系统 | 目录 |
| --- | --- |
| Windows | `%APPDATA%/Antigravity-zh-CN/` |
| macOS | `~/Library/Application Support/Antigravity-zh-CN/` |
| Linux 开发/隔离测试 | `$XDG_CONFIG_HOME/Antigravity-zh-CN/`，未设置时 `~/.config/Antigravity-zh-CN/` |

Linux 用户目录支持只用于设置/开发工具，不表示汉化安装工具支持 Linux。

- `config.json`：schema/revision、开关、四类提供商地址/模型/**明文密钥**、请求限制和缓存版本。
- `personal-dictionary.json`：schema/revision、原文→译文、来源/更新时间和删除记录。
- `.translation.lock/`：跨进程写入锁。锁争用有超时，不强删其他进程的锁；异常遗留时先确认所有相关进程已退出，再调查锁状态，不在写入进行中手工删除。

明文不是加密：同一账户下其他程序、共享账户、云盘同步、备份和文件泄露都可能暴露密钥并造成费用。GUI 遮蔽输入和脱敏日志不能消除磁盘风险；保存密钥前有显式确认。不要把此目录加入仓库、截图公开或发给他人。工具不自动读取浏览器/系统凭据。

同目录临时写入、文件同步和原子替换减少半文件风险；版本冲突会拒绝覆盖，需要重新加载。损坏 JSON/未知 schema 不自动重建覆盖。文件权限、磁盘满或保存失败会报告错误。个人词典手工条目不被 AI 自动覆盖；删除记录用于阻止在途请求把词条重新保存。

“自动保存 AI 译文”关闭时，仅使用会话缓存；开启时才将通过校验的结果保存到个人词典。可在词典页查看、检索、编辑、删除。已有个人词典可以在 AI 关闭时使用，但仍需可信应用桥接和安全 DOM 区域。

重新汉化、官方更新与 `Restore.py` 不删除用户目录。官方更新可能覆盖注入，使补译暂停；重新验证并汉化后才恢复。还原英文不是清除个人数据，清除账户/密钥需另行处理。

## 5. 为什么桥接默认不启用

仓库提供的是补丁工具，不包含官方 Electron 主入口和真实页面源码。菜单 hook 能运行，不代表可以安全信任任意窗口/preload。不能通过降低 sandbox/contextIsolation、开放通用 IPC 或网页直连来绕过这一点。

只读检查工具用于**已合法取得并解包的应用副本**：

```bash
python Inspect-Translation-Compatibility.py /path/to/extracted-app --ui-file dist/example-ui.js
```

`--ui-file` 示例路径必须替换为副本中实际存在的 UI 资源，可重复指定。工具读取 `package.json`、入口、preload 和指定 UI 文件并输出摘要；不解包真实安装、不关闭应用、不写安装文件、不联网。`matchedProfile: null` 表示没有已审核匹配项；`bridgeVerified: false` 表示指纹本身不是运行兼容证明。

新增 profile 前必须在授权样本/测试安装中验证：

1. 原入口模块制式、启动顺序及 bootstrap 对原应用的影响；当前 profile 设计只接受经审核的 CommonJS 入口，不猜测 ESM 支持。
2. 可信顶层窗口、精确页面 URL、preload、sandbox/contextIsolation、导航和子 frame；页面级脚本不得获得通用 IPC 或密钥。
3. UI 资源指纹与真实 DOM 区域；按钮/短字符串本身不是安全证明。明确排除对话、用户输入/命名、编辑器/代码、终端、工件和思考/执行日志。
4. 配置关闭零请求、错误保留原文、旧响应不覆盖新内容、词典修改/删除不被旧请求恢复。
5. Windows 与 macOS 的启动、重汉化、还原和用户数据保留；记录实际支持版本/架构。

不要仅凭一组哈希将 `verified` 改为 true；检查报告不是授权 profile。配置文件没有“强制启用未知版本”的开关。

## 6. 源码分发与打包

分发完整源码，至少保留：

- `Antigravity-Patcher.py`、`Restore.py`、`antigravity_common.py`；
- `translation_integration.py` 与完整 `localization_runtime/`（包括兼容注册表）；
- `Translation-Settings.py`、`translation_config.py`；
- `Inspect-Translation-Compatibility.py`；
- 代理功能仍需 Setup/Cleanup 两个原脚本。

macOS 工作流 `.github/workflows/build-mac.yml` 为本机 Intel/arm64 分别构建，不用同一个架构解释器冒充跨架构成功。对应 `macos-15-intel` / `macos-15` runner 标签已按 [GitHub 官方 runner 文档](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) 核对（2026-10-26）。Patcher、设置 GUI 和兼容检查工具需显式带入 runtime 资源，例如：

```bash
# 在目标 macOS 架构的 Python 环境运行；PyInstaller 是打包依赖，不是运行源码的必需依赖。
python -m PyInstaller -F --add-data "localization_runtime:localization_runtime" Antigravity-Patcher.py
python -m PyInstaller -F --add-data "localization_runtime:localization_runtime" Translation-Settings.py
python -m PyInstaller -F --add-data "localization_runtime:localization_runtime" Inspect-Translation-Compatibility.py
python -m PyInstaller -F Restore.py
```

GUI 包不附带 Node；可选网络测试仍需外部 Node。已安装的桥接运行于应用自身 Electron/Node 环境，不能以开发机 Node 测试替代该运行时验收。本次未实际构建原生二进制，也未在 GitHub 上执行新工作流。打包产物只是待验收构建，不自动签名、公证或发布。冻结包需验证任意工作目录启动、资源包含、Tk 可用和无真实凭据打包。

## 7. 隔离测试与发布门槛

```bash
python -B -m unittest discover -s tests -v
node --test tests/js/*.test.cjs
```

使用 Node 22+ 运行开发测试；无 npm 运行时依赖。PowerShell/进程/安装变更测试使用隔离 fixture 和 mock，JavaScript 网络合约测试注入传输，不使用真实密钥或请求。Windows COM 等平台专属检查可能按环境跳过；实际数量和结果以本次运行日志为准。

CI 工作流仅配置了验证任务，尚未因本地代码修改而在 GitHub 上运行。Linux 模拟通过不等于 Windows/macOS 真机通过；Windows/macOS CI 单元测试也不等于完整 GUI/Antigravity 安装验收。

发布前必须分别建立证据：自动测试、冻结包检查、授权真实提供商请求、真实应用 bridge/DOM 隐私边界、双平台安装→重汉化→还原。缺少任一环节，就明确标记未验证，不宣传“所有版本完全兼容”。
