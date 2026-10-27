# DragonGirl 本轮验证记录

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
