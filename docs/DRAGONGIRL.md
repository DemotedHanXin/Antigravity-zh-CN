# DragonGirl：AI 补译开发版使用与验证说明

> **M0、M1 已获批准，M2 词典与审核流程已完成、待审核，未发布。** 2.28.2 / Windows x64 的 profile 仍为 `antigravity-2.28.2-win32-x64-navigation`，只覆盖下述四个导航正文标签。接入实测见 [M1 记录](development/M1-real-integration.md)，当前数据协议与回归见 [M2 记录](development/M2-dictionary-review.md) 和 [开发进度](development/PROGRESS.md)。更新源码不会自行改动日常安装。

## 1. 已提供的组件与明确边界

- 独立 Tkinter GUI，管理四类提供商、AI 开关、个人词典和缓存失效标记；待确认审核提供结构化 CLI，统一 PySide6 界面留给 M3。
- Python / Node 共用的用户目录、版本化 JSON、跨进程锁与原子替换；词条手工编辑优先、删除记录防止旧结果恢复词条。
- 主进程翻译服务、受限 IPC、去重/缓存/队列/限流与四种提供商适配器。
- 默认空白名单的 DOM 补译模块，异步回写前检查原文、节点、导航和配置/词典版本。
- 只读兼容性检查工具与受指纹约束的注入流程。只有经审查的匹配 profile 才可以增加主进程桥接；没有匹配时保留原有同步汉化。

M1 在 Windows 隔离副本实测了窗口／preload 接入、动态服务绑定、受控未命中的成功／失败／关闭、导航恢复、设置页停留边界、设置工具关闭时运行、归档恢复与解包重建，以及同一应用／窗口内的服务恢复。**真实提供方页面补译、macOS 桥接、完整 UI 覆盖、原生 GUI 外观和冻结包运行仍未验收。** 固定文案连接测试通过也不能替代页面补译验收。

当前翻译顺序为 **个人词典 → 内置词典／规则 → 有效待确认译文 → AI**。删除个人覆盖恢复内置译文；无内置命中时继续正常候选／AI 流程。有效候选在 AI 关闭时仍可复用，拒绝记录仅抑制自动补译，不覆盖个人或内置译文。原生菜单仍使用静态词典，不接个人覆盖或 AI。

### M1 实际覆盖范围

profile 同时核对应用入口、preload、窗口／服务模块和外置 `resources/bin/language_server.exe` 的指纹。匹配后重新汉化会停用旧的广域 DOM observer，网页翻译仅处理实际 Hub 窗口中根路径 `/`、无 query/hash 时的以下导航正文：

| 固定原文 | 当前内置译文 |
| --- | --- |
| New Conversation | 新建对话 |
| Automations | 自动化 |
| Customizations | 自定义 |
| Settings | 设置 |

Projects、同名 aria-label、其他页面正文及带 query/hash 页面均不在此 profile 的翻译范围内；聊天、代码、输入、终端和内嵌网页不应为扩大覆盖而加入白名单。未匹配版本继续走原有同步汉化路径，其范围不能当作 M1 已验证范围。

这四个标签现在全部命中内置词典，因此正常运行不会由它们触发自然未命中的 AI 请求。实验助手只对 Automations 人为制造未命中，再由本地固定提供方返回“自动化（测试译文）”，用于验证桥接链路；正式 profile 不包含这个测试绕过。填写密钥或启用 AI 不会扩大允许区域，也不会使已命中内置词典的这四项改由 AI 翻译。

仓库改动和隔离副本验收均不自动更新日常安装。只有另行对目标安装执行汉化才会应用本次 profile；应用后网页翻译范围可能比旧广域注入更少。需要扩展页面或标签时，必须另外取得并验证对应结构和来源。

## 2. 启动设置界面

从完整仓库的根目录运行：

```bash
python src/localization/Translation-Settings.py
# macOS 如需使用 python3：
python3 src/localization/Translation-Settings.py
```

本文中的命令均从仓库根目录执行。源码入口位于 `src/localization/`；从其他工作目录启动时使用完整脚本路径。

需要带 Tk 的 Python 和可用桌面显示环境。导入模块不会弹出 GUI、修改安装或发起网络请求。缺少 Tk/显示环境会说明不可用，而不是绕过检查。单纯编辑配置不要求 Node；可选连接测试需要 `node` 在 PATH 中，并随源码/冻结包附带 `localization_runtime/probe.cjs`。

首次默认 `enabled=false`；`autoSave=false` 仅为弃用的兼容字段，不能再开启，新 AI 结果全部进入待确认流程。地址有默认值，模型和密钥留空。自行填写提供商、模型、密钥，并明确保存。**保存配置不自动勾选启用 AI；勾选启用也不能绕过兼容 profile 检查。** 模型名称和账户额度由所选服务决定，不自动查询或承诺免费额度。

连接测试必须主动点击并确认可能产生费用，使用已保存配置和固定测试文案，不采集正在编辑的页面内容。缺少 Node/测试资源会报告不可用；测试只返回脱敏状态。没有自动测试连接、自动切换提供商或后台模型枚举。命令行主动测试方式：

```bash
# 此命令会发起真实网络请求，可能计费；仅在明确同意且配置完成后运行。
node localization_runtime/probe.cjs --confirm-network --revision N
```

将 `N` 替换为您刚核对的 `config.json` 中 `revision` 整数；配置在确认后变化会拒绝请求。推荐使用 GUI，避免手工处理配置版本。命令行不要传入密钥或待翻译的工作内容。

Windows 上，连接测试和 AI 请求每次读取当前用户的系统代理：支持 HTTP/HTTPS 手动代理、HTTP/混合端口、分协议的 `https=...` 设置及代理绕过列表。代理端口不会写死；关闭系统代理后使用直连/TUN，旧进程中的代理环境变量不会覆盖当前 Windows 设置。代理连接失败时会返回错误，不自动改为直连。

macOS/Linux 使用 `HTTPS_PROXY` 或 `ALL_PROXY`（也接受小写），并遵守 `NO_PROXY`；不自动读取 macOS 系统代理。所有平台暂不支持 PAC、纯 SOCKS 和带账号密码的代理。Windows 读取代理配置失败、代理需要认证或无法连接，会在测试结果中显示对应提示。

若测试提示超时，先检查代理客户端已运行、系统代理已开启、线路能够访问提供商。修改代码后重新打开设置工具可加载新的错误提示；只改了表单而未保存时，测试仍使用磁盘上的旧配置。

## 3. 提供商协议与地址

| GUI 选项 | API 类型 | 默认 Base URL |
| --- | --- | --- |
| OpenAI | 原生 Responses | `https://api.openai.com/v1` |
| Gemini | 原生 generateContent | `https://generativelanguage.googleapis.com/v1beta` |
| Claude | 原生 Messages | `https://api.anthropic.com/v1` |
| OpenAI 兼容 | Chat Completions | 用户填写 |

Claude 第一版只支持不需要额外 workspace header 的 workspace-scoped API key；未提供任意自定义认证头，不承诺所有 Claude 凭据类型可用。该限制以实施时核对的官方 API 文档为依据，真实账户连接仍需用户主动测试。

填写 **Base URL**，不要重复附加 `/responses`、`/messages`、`/chat/completions` 或 Gemini 模型动作路径；适配器负责添加路径。四种协议不是互相替代的兼容模式。

Google 的 `https://generativelanguage.googleapis.com/v1beta/openai` 应搭配 GUI 的 `compatible` 选项；选 `gemini` 时使用表中的 `/v1beta` 地址。

当前网络层仅允许 HTTPS 公网域名目标，拒绝内嵌凭据、查询参数、片段、本机/私网解析与重定向认证转发；不支持本地 HTTP 模型服务器。自定义地址会接收该提供商密钥和筛选后的 UI 文案，务必核对主机。代理通过 CONNECT 连接经过本机 DNS 校验的公网 IP，隧道内继续校验原 API 域名的 TLS 证书，API 密钥不会放进 CONNECT 请求头。DNS、代理握手、TLS 和响应读取共用总超时。仍需能在本机将 API 域名解析为公网地址；若使用返回保留地址的 Fake-IP 模式，应为 API 域名配置真实 DNS 解析。

## 4. 用户数据与明文密钥风险

| 系统 | 目录 |
| --- | --- |
| Windows | `%APPDATA%/Antigravity-zh-CN/` |
| macOS | `~/Library/Application Support/Antigravity-zh-CN/` |
| Linux 开发/隔离测试 | `$XDG_CONFIG_HOME/Antigravity-zh-CN/`，未设置时 `~/.config/Antigravity-zh-CN/` |

Linux 用户目录支持只用于设置/开发工具，不表示汉化安装工具支持 Linux。

- `config.json`：schema/revision、开关、四类提供商地址/模型/**明文密钥**、请求限制和缓存版本。
- `personal-dictionary.json`：schema/revision、原文→译文、来源/更新时间和删除记录。
- `pending-translations/state.json`：独立候选 entries、永久拒绝记录 rejected 以及使旧响应失效的 epochs；候选从首次生成起 7 天，复用不续期。
- `.translation-journal.json`：跨文件迁移／采纳操作的恢复事务，不是导出文件，也不应手工删除或共享。
- `.translation.lock/`：跨进程写入锁。锁争用有超时，不强删其他进程的锁；异常遗留时先确认所有相关进程已退出，再调查锁状态，不在写入进行中手工删除。

明文不是加密：同一账户下其他程序、共享账户、云盘同步、备份和文件泄露都可能暴露密钥并造成费用。GUI 遮蔽输入和脱敏日志不能消除磁盘风险；保存密钥前有显式确认。不要把此目录加入仓库、截图公开或发给他人。工具不自动读取浏览器/系统凭据。

同目录临时写入、文件同步和原子替换减少半文件风险；版本冲突会拒绝覆盖，需要重新加载。损坏 JSON/未知 schema 不自动重建覆盖。文件权限、磁盘满或保存失败会报告错误。个人词典手工条目不被 AI 自动覆盖；删除记录用于阻止在途请求把词条重新保存。

新 AI 译文先持久化为候选，再通过新快照显示；保存失败不会冒充已保存或直接写个人词典。到期后移除候选并恢复默认／英文，再次遇到允许文案可重新请求。采纳时再次检查版本和期限；编辑后采纳允许修正译文。拒绝不因七天清理而消失，只有显式解除才恢复自动请求许可。解除和清理本身不调用 AI。

M2 首次读取旧数据时执行 schema1→schema2 迁移，手工条目保留；旧自动保存 AI 标为 `legacy-ai`（历史保存、未审核），留在正式词典中不受七天清理影响。旧运行时遇到 schema2 停止增强翻译，不能继续写入旧格式；应同时更新安装组件。迁移与审核共用锁及完整 after-image journal：journal 持久化后是提交点，中断后的下一次持锁读取继续完成事务；这不是恢复旧值的回滚。真实进程异常退出可能遗留锁，须核实后处理，不能直接删除。源码回退不提供数据降级。

### 词典与审核命令行

`Translation-Dictionary.py` 输出结构化 JSON，不输出提供商配置或密钥。写入时使用刚读取的版本号；版本冲突先重新加载，不猜测覆盖。默认读写当前用户目录，下面显式使用隔离目录，避免更改日常数据：

```powershell
python -B src/localization/Translation-Dictionary.py --data-dir .m2-lab/demo list --query "New Conversation"
python -B src/localization/Translation-Dictionary.py --data-dir .m2-lab/demo pending
```

按 `--help` 使用 `set`／`restore-default`，提供 `dictionaryRevision`；`accept`／`reject`／`unblock` 使用 `candidatesRevision`，均通过 `--revision` 传入。`accept --translation` 可编辑后采纳；`cleanup` 仅清理到期候选。完整步骤见 [M2 使用说明](development/M2-dictionary-review.md#4-使用方式已知问题及恢复方法)。

重新汉化、官方更新与 `src/localization/Restore.py` 不删除用户目录。官方更新可能覆盖注入，使补译暂停；重新验证并汉化后才恢复。还原英文不是清除个人数据，清除账户/密钥需另行处理。

## 5. 桥接匹配与版本检查

仓库提供补丁工具和经过限定验证的 profile，不分发官方 Electron 主入口或真实页面源码。M1 目前只支持上述 Windows 样本；未知指纹、平台或架构不启用该桥接。菜单 hook 能运行，不代表可以安全信任任意窗口/preload。不能通过降低 sandbox/contextIsolation、开放通用 IPC 或网页直连来绕过这一点。

只读检查工具用于**已合法取得并解包的应用副本**：

```bash
python src/localization/Inspect-Translation-Compatibility.py /path/to/extracted-app --ui-file dist/example-ui.js
```

`--ui-file` 示例路径必须替换为副本中实际存在的 UI 资源，可重复指定。工具读取 `package.json`、入口、preload 和指定 UI 文件并输出摘要；不解包真实安装、不关闭应用、不写安装文件、不联网。对于 2.28.2 的外置服务，还需用 `--resources-dir` 明确提供对应 resources 目录，`--resource-file bin/language_server.exe` 可将其纳入检查摘要。应检查原始解包样本；已注入文件的指纹可能不同。`matchedProfile: null` 表示未匹配，`bridgeVerified: false` 提醒仅凭本次指纹检查不能宣称运行验收；实际证据见 M1 记录。

新增 profile 前必须在授权样本/测试安装中验证：

1. 原入口模块制式、启动顺序及 bootstrap 对原应用的影响；当前 profile 设计只接受经审核的 CommonJS 入口，不猜测 ESM 支持。
2. 可信顶层窗口、精确页面 URL、preload、sandbox/contextIsolation、导航和子 frame；页面级脚本不得获得通用 IPC 或密钥。
3. UI 资源指纹与真实 DOM 区域；按钮/短字符串本身不是安全证明。明确排除对话、用户输入/命名、编辑器/代码、终端、工件和思考/执行日志。
4. 配置关闭零请求、错误保留原文、旧响应不覆盖新内容、词典修改/删除不被旧请求恢复。
5. 所声明平台的启动、重汉化、还原和用户数据保留；分别记录实际支持版本／架构，Windows 验证不能代替 macOS 验证。

不要仅凭一组哈希将 `verified` 改为 true；检查报告不是授权 profile。配置文件没有“强制启用未知版本”的开关。

## 6. 源码分发与打包

分发完整源码并保留目录结构，至少保留：

- `src/localization/Antigravity-Patcher.py`、`src/localization/Restore.py`、`src/localization/antigravity_common.py`；
- `src/localization/translation_integration.py` 与完整 `localization_runtime/`（包括兼容注册表）；
- `src/localization/builtin_dictionary.py`、`translation_service.py` 和 `Translation-Dictionary.py`；内置 JSON 也随整个 runtime 目录分发；
- `src/localization/Translation-Settings.py`、`src/localization/translation_config.py`；
- `src/localization/Inspect-Translation-Compatibility.py`；
- 代理功能仍需 `src/proxy/Setup-Proxy-Shortcuts.py` 和同目录的 `Cleanup-Proxy-Shortcuts.py`。

汉化相关 Python 模块保持在 `src/localization/` 同一目录；JavaScript 资源继续放在仓库根目录 `localization_runtime/`。源码根据脚本位置查找资源，冻结包根据 `_MEIPASS` 查找包内资源；设置 GUI 与桥接共用此定位逻辑，不依赖启动时的工作目录。用户配置和个人词典仍保存在用户数据目录。

macOS 工作流 `.github/workflows/build-mac.yml` 为本机 Intel/arm64 分别构建，不用同一个架构解释器冒充跨架构成功。对应 `macos-15-intel` / `macos-15` runner 标签已按 [GitHub 官方 runner 文档](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) 核对（2026-10-26）。Patcher、设置 GUI 和兼容检查工具需显式带入 runtime 资源，例如：

```bash
# 从仓库根目录、目标 macOS 架构的 Python 环境运行；PyInstaller 是打包依赖。
python -m PyInstaller -F --add-data "localization_runtime:localization_runtime" src/localization/Antigravity-Patcher.py
python -m PyInstaller -F --add-data "localization_runtime:localization_runtime" src/localization/Translation-Settings.py
python -m PyInstaller -F --add-data "localization_runtime:localization_runtime" src/localization/Inspect-Translation-Compatibility.py
python -m PyInstaller -F src/localization/Restore.py
```

GUI 包不附带 Node；可选网络测试仍需外部 Node。已安装的桥接运行于应用自身 Electron/Node 环境，不能以开发机 Node 测试替代该运行时验收。本次未实际构建原生二进制，也未在 GitHub 上执行新工作流。打包产物只是待验收构建，不自动签名、公证或发布。冻结包需验证任意工作目录启动、资源包含、Tk 可用和无真实凭据打包。

## 7. 隔离测试与发布门槛

```bash
python -B -m unittest discover -s tests -v
node --test tests/js/*.test.cjs
```

使用 Node 22+ 运行开发测试；无 npm 运行时依赖。PowerShell/进程/安装变更测试使用隔离 fixture 和 mock。JavaScript 提供商合约测试注入传输；网络层测试会启动临时回环 HTTP/HTTPS 代理和 TLS 服务，使用 `tests/fixtures/proxy-test-*.pem` 的公开测试证书与虚拟密钥，不调用外部 API。测试证书仅由测试代码显式信任，不安装进系统。受限环境需允许本机回环连接。Windows COM 等平台专属检查可能按环境跳过；实际数量和结果以本次运行日志为准。

CI 工作流仅配置了验证任务，尚未因本地代码修改而在 GitHub 上运行。Linux 模拟通过不等于 Windows/macOS 真机通过；Windows/macOS CI 单元测试也不等于完整 GUI/Antigravity 安装验收。

最新完整回归、Windows 隔离副本实测和已知限制见 [M1 阶段记录](development/M1-real-integration.md)；[历史验证记录](DRAGONGIRL-VERIFICATION.md) 保留各轮日期与计数，不能替代最新结果。

发布前须按实际声明范围建立自动测试、冻结包、授权真实提供方请求、真实应用 bridge／DOM 边界和安装→重汉化→还原的证据；声明双平台时须分别完成两平台验证。M1 阶段交审不代表这些发布项目全部完成；真实 AI 页面补译、纯 `app.asar` 布局启动等未验证项应继续明确列出，不宣传“所有版本完全兼容”。
