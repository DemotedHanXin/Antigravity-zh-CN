# DragonGirl 验证记录

当前状态（2026-11-05，Asia/Shanghai）：M0–M2 已获批准，M3 已完成、待审核；M4 尚未开始。阶段交付与历史回归见 [M3 记录](development/M3-unified-manager.md)，当前进度见 [开发进度](development/PROGRESS.md)；真实应用接入证据见 [M1 记录](development/M1-real-integration.md)。本次按用户要求整理源码和文档，统一启动入口为 `python main.py`，功能源码集中到 `src/`，除首页外的项目 Markdown 集中到 `docs/`。目录整理不代表进入 M4，也不替代原生 GUI、真实 API 或安装包验收。下文按日期保留历史结果，早期“尚未验证／profiles 为空”仅描述当时状态。

## 2026-11-03：M2 词典与审核流程

Python 完整回归 218 项（214 通过、4 跳过），JavaScript 194 项（193 通过、1 跳过），无失败。最后 UTF-8/BOM 收紧后的 Node 存储 14 项、审核元数据更新后的兼容专项 32 项（30 通过、2 跳过）也通过。验证内置数据提取一致性、个人覆盖／恢复默认、七天候选、采纳／拒绝／解除、跨语言迁移、事务继续提交和并发失效。独立审阅发现的到期竞态、损坏编码、容量与空白规则问题已修复并复核。

使用原始归档的相关文件在临时目录验证 M2 注入、生成 JavaScript 和 11 项完整性摘要；没有运行应用。Python 3.8 AST 语法检查通过。本轮未迁移日常用户数据、安装真实组件、调用外部 AI 或进行原生 GUI／冻结包验收；实际生成 preload 的 VM 证据与 M1 真机接入证据分开记录。

## 2026-10-26：DragonGirl 初始开发（Linux）

执行环境：Linux 云工作区。起点 `feat/Fly`：`c18e0eaa40a8ac7effaf01c78663ff51f81434d7`；开发分支 `feat/DragonGirl`。

### 当日已完成

- 只读核对远端 `feat/Fly` 与实施基线一致，未覆盖任何用户未提交修改。
- 基线原 86 项测试在 Linux 出现 3 failures / 14 errors（另 1 skip）；仅修正测试中的 Windows fixture 平台/模拟子进程常量，不放宽生产平台支持。新增 Linux 拒绝用例。
- 最终 `python -B -m unittest discover -s tests -v`：**125 项，成功，1 项按环境跳过**。
- 最终 `node --test tests/js/*.test.cjs`：**76 项，通过，无失败/跳过**。
- 根目录 Python 源码通过 Python 3.8 grammar 检查（不代表已在 Python 3.8 解释器运行）；所有 runtime JS/CJS 通过 `node --check`；`git diff --check` 通过。
- 兼容配置精确指纹门槛、模拟完整汉化→重复汉化→还原、用户数据保留、原主入口 fallback、实际生成 preload 的 VM 执行均有隔离测试。
- GUI controller、配置/词典 CRUD、明文保存确认、Node↔Python 存储互通、原子替换、损坏/冲突保护、显式 probe 有自动测试。
- 四种 provider 请求体/响应解析均用 mock transport 测试，未使用真实密钥或发起真实 API 请求。
- 独立只读审查发现的三项问题已修复并复核：有效批次子集不被无效兄弟条目阻断；发 IPC 前重新检查排除区域/原文/版本；按实际 pretty-JSON UTF-8 字节数预检写入上限，拒绝时旧有效词典字节不变。

### 当日尚未完成的项目

- **没有真实应用 ASAR/DOM 样本可验证；出厂 compatibility profiles 为空。真实 Antigravity 中个人词典/AI 桥接尚不启用。** 现有内置词典汉化保持原路径。
- Windows/macOS 真机启动、实际隐私筛选区域、CJS bootstrap 与原程序入口语义/时序兼容性待验证。
- Tk 可导入，但无桌面显示环境；GUI 视觉/交互真机验收未完成。缺少显示时安全返回，不伪装运行成功。
- PyInstaller 原生二进制没有构建/运行；新 CI/构建工作流仅配置完成，未在 GitHub 执行。
- 未做真实提供商/模型/费用、系统代理/PAC、Windows ACL 验证。Claude 首版不支持需要额外 workspace header 的非 workspace-scoped key。
- 本地提交不等于远端已有代码；未推送、建远程分支/PR、发布 Release。远程写权限按用户安排延后。

当时的下一道门槛是取得授权应用副本，在隔离环境验证入口、窗口、preload 与精确 UI 白名单，并完成对应系统真机回归；不能仅添加哈希就声称兼容。后续 Windows M1 验证见本文 2026-11-03 条目；详细使用及边界见 [DRAGONGIRL.md](DRAGONGIRL.md)。

## 2026-11-01：源码目录整理（Windows）

执行环境：Windows，Python 3.11.4，Node v24.15.0。9 个 Python 源文件迁入 `src/localization/` 和 `src/proxy/`，同步更新模块/资源定位、测试入口、macOS 构建入口及使用文档。

- `python -B -m unittest discover -s tests -q`：**129 项，127 项通过，2 项按环境跳过，无失败**。跳过项分别为 POSIX 权限检查和缺少 Windows 符号链接权限的检查；路径越界检查仍单独执行。
- `node --test --test-reporter=tap tests/js/*.test.cjs`：**76 项，75 项通过，1 项因缺少 Windows 符号链接权限跳过，无失败**。仅在 Windows 返回权限错误时跳过该项，其他错误继续报告失败。
- 新增迁移回归检查：5 个 CLI 从其他工作目录执行 `--help`；设置 GUI 的无窗口导入、源码运行时和连接测试探针定位；Cleanup 从自身目录加载 Setup；模拟 `_MEIPASS` 中的冻结资源定位及资源缺失时拒绝回退。
- 同步本机 `.idea/workspace.xml` 中 4 个 PyCharm 运行配置的脚本入口，验证 XML 和目标路径有效；该文件按仓库现有规则忽略，不随 Git 提交。
- 17 个 Python 源码/测试文件通过 Python 3.8 grammar 检查；10 个 JS/CJS 文件通过 `node --check`；本地 Markdown 链接与 `git diff --check` 检查通过。
- 默认沙盒临时目录阻止部分重命名操作；本轮测试只在测试进程内将 `TEMP` / `TMP` 指向仓库中的 `.test-tmp/`，运行后清理该目录，未改动系统环境变量或用户配置。

本轮没有操作真实 Antigravity 安装、现有代理快捷方式或 API，也没有实际构建 PyInstaller 二进制、执行远程 CI 或发布。冻结资源检查为隔离模拟，不能替代冻结包或真实应用验收。

## 2026-11-02：连接测试使用系统代理（Windows）

问题复现：Windows 系统代理已启用，原 Node HTTPS 直连在 15 秒内未能连接 Google；显式使用本机 HTTP 代理可收到响应。Gemini 原生协议的 Base URL 与 OpenAI 兼容地址需分别配置。

- 新增共用 `network.cjs`，在每次请求时读取 Windows 手动代理，支持 HTTP/HTTPS CONNECT、分协议地址和绕过列表；系统代理关闭时使用直连/TUN。macOS/Linux 支持 HTTPS_PROXY/ALL_PROXY/NO_PROXY，但尚未做这两个系统的真机验证。
- DNS 校验后将 CONNECT 目标固定为公网 IP，隧道内保留 API 域名的 TLS 校验；API 凭据不进入 CONNECT 请求头。总超时和取消覆盖注册表读取、DNS、代理握手、TLS 和响应体，失败后释放连接且不自动直连重试。
- GUI 与 probe 增加代理配置、代理连接、代理认证、非公网 DNS 和提供商拒绝等脱敏提示。桥接打包资源清单包含新模块；现有真实应用兼容门槛不变。
- `node --test --test-reporter=spec tests/js/*.test.cjs`：**94 项，93 项通过，1 项因 Windows 符号链接权限跳过，无失败**。新增 18 项网络测试，包含真实本机 HTTP/HTTPS 代理和 TLS 服务、证书不可信/域名不匹配、混合公网私网 DNS、407/502、超时/取消与响应容量限制；全部使用测试身份和虚拟密钥。
- `python -B -m unittest discover -s tests -q`：**129 项，127 项通过，2 项按环境跳过，无失败**。Python 测试临时目录仅在测试进程内改为仓库下唯一目录，测试后已删除。
- 通过修复后的共用网络层进行一次**不携带密钥**的 Google 官方接口请求，自动使用当前系统代理 `127.0.0.1:10808`，约 **1.56 秒返回 HTTP 403**。该结果仅证明网络与 TLS 路径可达，不证明用户密钥、模型权限或翻译响应有效。

截至本轮连接测试修复结束，带密钥的真实连接测试尚未执行，真实 Antigravity 桥接、冻结包和 macOS 真机仍未验收。本轮未修改用户 API 配置、系统代理、快捷方式或真实应用安装。

## 2026-11-03：M1 限定真实版本接入（Windows）

目标为用户授权的 Antigravity 2.28.2 / Windows x64 隔离副本。用户执行实际启动、界面操作及服务恢复测试；助手核对受限结构化报告与源码、完成无界面回归。测试记录、命令、完整结果和跳过项集中在 [M1 阶段记录](development/M1-real-integration.md)，本节不重复可能变化的测试总数。

- 已验证实际 Hub 窗口、Electron preload、动态本地 HTTPS 服务及四个固定导航正文标签；运行安全开关保持 contextIsolation=true、sandbox=true、nodeIntegration=false。
- 本地受控提供方验证人为未命中的成功显示、失败保留英文、启动时关闭零请求；正常及较快关闭 Settings 返回主页后恢复显示，设置工具关闭时仍可工作。
- 同次运行在带 query 的 Settings 页面停留 16.216 秒，状态请求继续但授权、翻译和提供方计数未增加，诊断未采样其 DOM。该实测不外推为所有路由或在途导航情形均已验收。
- 原始归档切换、归档哈希／入口／依赖完整性、解包副本重建、重新启动与登录保留通过；纯 `app.asar` 布局启动未验证。
- 一次用户显式触发的实际服务终止后，应用 session、主进程及窗口保持，服务代次由 1 变为 2，窗口连接新服务端口并恢复授权与测试译文，preloadErrors=0。恢复前的短暂 `no_eligible_window` 报告也保留；最终采样间隔不能作为准确恢复耗时。

源码注册表纳入 `antigravity-2.28.2-win32-x64-navigation`，按入口、preload、窗口／服务模块及外置 `language_server.exe` 的指纹匹配。**匹配后重新汉化会停用旧广域 DOM observer，只保留 `/` 且无 query/hash 的 New Conversation、Automations、Customizations、Settings 四个导航正文标签翻译**；原生菜单保持静态汉化，未匹配版本保留原有同步路径。

四个标签均已有内置译文，正常使用没有由这些标签产生的自然未命中。受控助手对 Automations 人为制造未命中并返回固定译文，证明的是桥接链路，不是真实外部提供方页面翻译。正式 profile 不含测试绕过，也不放开 Projects、同名 aria-label 或其他页面内容。

本轮源码更新不会自行修改日常安装；适用范围扩大需要新的验证。M1 仍待用户阶段审核，不代表发布批准；真实提供方页面补译、macOS、GUI／冻结包和安装程序等未验证事项分别保留在阶段／发布计划中。
