# DragonGirl 验证记录

日期：2026-10-26；执行环境：Linux 云工作区。起点 `feat/Fly`：`c18e0eaa40a8ac7effaf01c78663ff51f81434d7`；开发分支 `feat/DragonGirl`。

## 已完成

- 只读核对远端 `feat/Fly` 与实施基线一致，未覆盖任何用户未提交修改。
- 基线原 86 项测试在 Linux 出现 3 failures / 14 errors（另 1 skip）；仅修正测试中的 Windows fixture 平台/模拟子进程常量，不放宽生产平台支持。新增 Linux 拒绝用例。
- 最终 `python -B -m unittest discover -s tests -v`：**125 项，成功，1 项按环境跳过**。
- 最终 `node --test tests/js/*.test.cjs`：**76 项，通过，无失败/跳过**。
- 根目录 Python 源码通过 Python 3.8 grammar 检查（不代表已在 Python 3.8 解释器运行）；所有 runtime JS/CJS 通过 `node --check`；`git diff --check` 通过。
- 兼容配置精确指纹门槛、模拟完整汉化→重复汉化→还原、用户数据保留、原主入口 fallback、实际生成 preload 的 VM 执行均有隔离测试。
- GUI controller、配置/词典 CRUD、明文保存确认、Node↔Python 存储互通、原子替换、损坏/冲突保护、显式 probe 有自动测试。
- 四种 provider 请求体/响应解析均用 mock transport 测试，未使用真实密钥或发起真实 API 请求。
- 独立只读审查发现的三项问题已修复并复核：有效批次子集不被无效兄弟条目阻断；发 IPC 前重新检查排除区域/原文/版本；按实际 pretty-JSON UTF-8 字节数预检写入上限，拒绝时旧有效词典字节不变。

## 仍未完成，不能当作通过

- **没有真实应用 ASAR/DOM 样本可验证；出厂 compatibility profiles 为空。真实 Antigravity 中个人词典/AI 桥接尚不启用。** 现有内置词典汉化保持原路径。
- Windows/macOS 真机启动、实际隐私筛选区域、CJS bootstrap 与原程序入口语义/时序兼容性待验证。
- Tk 可导入，但无桌面显示环境；GUI 视觉/交互真机验收未完成。缺少显示时安全返回，不伪装运行成功。
- PyInstaller 原生二进制没有构建/运行；新 CI/构建工作流仅配置完成，未在 GitHub 执行。
- 未做真实提供商/模型/费用、系统代理/PAC、Windows ACL 验证。Claude 首版不支持需要额外 workspace header 的非 workspace-scoped key。
- 本地提交不等于远端已有代码；未推送、建远程分支/PR、发布 Release。远程写权限按用户安排延后。

下一道门槛是取得授权应用副本，在隔离环境验证入口、窗口、preload 与精确 UI 白名单，并完成对应系统真机回归；不能仅添加哈希就声称兼容。详细使用及验证要求见 [DRAGONGIRL.md](DRAGONGIRL.md)。

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

带密钥的真实连接测试尚未执行；真实 Antigravity 桥接、冻结包和 macOS 真机仍未验收。未修改用户 API 配置、系统代理、快捷方式或真实应用安装。
