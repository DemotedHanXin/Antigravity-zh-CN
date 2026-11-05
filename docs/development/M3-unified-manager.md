# M3：统一管理器

日期：2026-11-05（Asia/Shanghai）。分支：`feat/DragonGirl`；起点：M2 提交 `3562929`。用户已确认 M2 结束并要求按计划继续，授权进入 M3。本阶段实现及完整回归完成，待用户审核；原生界面及真实 API 联调仍由用户手动执行。本地交审标签：`manager-v0.1.0-m3-review.1`。

2026-11-05 后续目录整理：按用户要求将管理器与 JavaScript 运行时移入 `src/`，新增根目录 `main.py` 统一入口；本文的启动命令和源码路径已同步到当前工作区。上面的审核标签及下方原有回归计数描述 M3 原交付快照，不包含此次整理。整理后 Python 完整回归为 268 项（264 通过、4 跳过），其中目录与入口专项 7 项通过。JavaScript 完整套件在沙箱中为 189 通过、2 跳过、10 项本机网络受限失败；获工具批准后在沙箱外重跑网络专项 18 项全部通过，合并覆盖为 199 通过、2 跳过，不是单次完整套件全通过。未执行原生 GUI 或真实外部 API 验收，M4 仍未开始。

## 1. 阶段目标及实际完成内容

新增源码入口 `python main.py`，使用 PySide6 提供概览、词典管理、待确认译文、AI 设置、代理与启动说明、日志与诊断六页。支持选择安装、检查兼容／组件、应用汉化、还原和独立启动；词典搜索、覆盖、恢复默认、JSON 导入导出；候选编辑采纳、拒绝、解除及到期显示；四类协议、请求限制、密钥更新／清除及显式固定文案测试。

代理页当前仅说明 M4 范围，实际快捷方式扫描、预览、启用／移除以及 PyInstaller／Inno Setup 均留给 M4。没有提前构建或发布安装包，没有改动日常安装、系统代理或真实用户配置。

## 2. 主要实现、接口与数据变化

- `src/antigravity_manager/service.py` 为 GUI 和 JSON CLI 共用服务。配置响应只提供地址、模型和 `hasKey`；保存时只更新明确提供的密钥，留空保留、明确清除才删除。诊断记录时间、固定操作名、结果代码及白名单中的安装步骤／状态，不保存参数、密钥、原文或 API 正文。
- `installation_service.py` 返回目标安装、逐项步骤、错误码、文件是否变化及重启提示。原汉化／还原 CLI 增加 `--json`；原函数通过日志／事件回调复用，不解析中文输出判断成功。保留原有校验、暂存、切换、回滚和保留恢复源行为。
- 安装兼容来源于原版归档与受审核 profile 的指纹；磁盘组件另核对注入和运行时完整性。安装成功不等于运行连接成功；没有握手证据时 `running/runtime` 为 `unknown`。API 测试状态仅对应当前保存版本，配置变化后失效。
- 所有文件、安装、清理和网络任务通过单个后台 QThread 串行执行，期间禁用冲突控件。关闭窗口等待当前操作完成；任务失败时保留窗口与错误。定时清理不覆盖编辑草稿；旧版本写入报冲突，需要用户刷新。
- 词典 JSON 格式为 `schemaVersion:1, kind:dragongirl-dictionary, entries:{原文:译文}`。只导出个人原文／译文；导入原子合并为手工词条，使对应候选／在途响应失效。重复键、无效条目、超限文件和版本冲突整体拒绝。导出位置不得位于当前数据目录。
- Windows 密钥使用当前用户 DPAPI，Python 调用系统 API，Node 通过固定 PowerShell 逻辑及标准输入调用同一用户保护。含密钥的磁盘配置为 schema3，字段为 `apiKeyProtected`；进程内部继续使用 schema2 API。迁移与恢复 journal 写入前先保护，不产生新的明文凭据文件；失败保留原文件且不回退明文。无密钥配置可保持 schema2。
- schema1／schema2 旧含密钥配置首次读取时持锁迁移，配置与缓存版本失效；旧组件遇到 schema3 停止增强翻译。不能把 Git 回退当作数据降级。非 Windows 的生产密钥操作暂停；跨平台协议测试显式注入测试替身，生产没有环境变量或 CLI 绕过开关。
- 新增 `credentials.cjs` 到随桥接复制和完整性验证的资源集合；管理器关闭后 Node 组件仍能独立解锁配置。DPAPI 不隔离同一用户的其他程序；跨账户／系统重装不能保证解密。

## 3. 验证命令、结果、跳过项及未验证范围

最终验证：

| 检查 | 结果 |
| --- | --- |
| 环境／依赖 | Windows、Python 3.11.4、固定 PySide6-Essentials / Qt 6.8.3；项目 `.venv` 已安装 |
| 完整 Python unittest | 264 项：260 通过、4 跳过、0 失败 |
| Qt 无界面交互 | 上述完整回归包含 18 项，全部通过；含实际共享服务与独立用户数据往返 |
| 完整 JavaScript node:test | 201 项：199 通过、2 跳过、0 失败 |
| 原生密钥保护 | Python／Node 双向 DPAPI、篡改拒绝、journal 无明文、页面 snapshot 脱敏通过 |
| 原始样本离线注入 | 8 个相关原始文件，默认 profile 匹配；13 个 JS/CJS 语法检查、12 项 runtimeIntegrity 摘要通过，包含 credentials.cjs |
| 原版归档保留 | 1085 条目，验证前后 SHA-256 均为 `046fa2ba9abe96bc915eb7ed12887c067396a8a12148842ab4f4e2cd05a68feb` |
| 独立审阅 | 安装服务、配置／词典接口、密钥迁移与事务经独立审阅，无剩余阻塞项；GUI 关闭失败隐藏结果等问题已修复并回归 |
| 文档／源码 | 23 份 Python 文件通过 3.8 AST 语法检查（GUI 运行仍需 3.11+）；63 个本地文档路径存在；`git diff --check` 通过 |

Python 跳过为 POSIX 权限及三项 Windows 符号链接条件；JavaScript 跳过为 Windows 符号链接条件及非 Windows 专用保护失败测试。Qt 不是跳过项。测试使用工作区临时数据、虚拟密钥、模拟安装和本机 TLS／代理夹具，不调用真实外部 AI。沙箱拒绝本机网络夹具连接后，经工具批准重跑相同完整 JS 套件通过；未修改系统代理。CI 已配置 Windows 安装管理器依赖，尚未推送或执行远端 CI。

只读状态检查确认 `.m1-lab/install` 原始样本兼容；其现存组件仍是旧 controlled profile，缺少新凭据资源，管理器正确报告校验失败，不能当作已部署 M3。临时离线注入目录已清理，原隔离安装未写入。

```powershell
$m3TestTemp = Join-Path (Get-Location).Path '.m3-lab-unit-tests'
New-Item -ItemType Directory -Path $m3TestTemp -Force | Out-Null
$env:TEMP = $m3TestTemp
$env:TMP = $m3TestTemp
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests
node --test tests/js/*.test.cjs
git diff --check
```

原生界面外观、日常安装汉化／还原、新组件在真实应用中的解锁及真实提供方 API 尚待用户手动检查。无界面 Qt 交互测试不能当作桌面目测验收。Windows 安装包、干净系统安装／升级／卸载属于 M4；本轮未验证 macOS/Linux 生产密钥或冻结资源。

## 4. 使用方式、已知问题与恢复方法

从仓库根目录运行（Windows、Python 3.11+）：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-manager.txt
.\.venv\Scripts\python.exe main.py --data-dir .m3-lab/review
# 不使用 Qt 的结构化入口：
.\.venv\Scripts\python.exe main.py --cli --data-dir .m3-lab/review config
.\.venv\Scripts\python.exe main.py --cli --app-dir .m1-lab/install status
```

省略 `--data-dir` 使用日常用户目录，首次读取可能迁移已有密钥；首次审核建议保留上述独立目录。界面不会自动汉化、启动应用或测试 API。汉化／还原必须明确目标并确认保存工作，操作完成后不自动启动。API 测试需要 Node 及完整运行时资源，确认后使用已保存配置及固定测试文案，可能产生费用。

迁移后应同步更新目标安装中的组件；旧组件不支持受保护配置。恢复英文仍使用 `Restore.py --app-dir 目标 --no-launch` 或管理器还原按钮，不删除用户配置。损坏、不可解密、遗留锁或 journal 不手工覆盖；先核对账户、运行进程和原文件，重新读取时会按既有事务完成规则处理。首次 Node 解密多个提供商可能耗时并暂时占用共享锁，冲突后刷新重试；后续读取使用有限缓存。

## 5. 用户审核内容

1. 用独立目录启动管理器，确认六页可访问、表格及中文可读；概览能选择隔离安装并分别显示兼容、组件、运行未知和配置状态。
2. 在词典页覆盖 `New Conversation`、恢复默认、导出后再导入，核对个人译文及导入覆盖确认；候选页检查采纳／编辑后采纳、拒绝和解除。没有自然候选是正常情况，四个 M1 标签均命中内置词典。
3. AI 设置保存测试配置后重新打开，密钥不回显；切换提供商不丢草稿，留空保留／清除密钥符合预期，冲突会提示重新加载。只有愿意进行真实网络联调时才点击测试。
4. 若审核安装操作，先保存工作、退出隔离副本，再选择明确目录执行汉化／还原；检查逐项结果和不自动启动行为。日常安装与真实 API 不作为助手自动测试目标。
5. 检查 `git show --stat manager-v0.1.0-m3-review.1` 与阶段 diff，反馈问题后仅返工 M3；新快照递增 review 标签，不覆盖历史标签。

## 6. 下一阶段待办及进入条件

M4 接入代理扫描、预览、启用／移除及分项状态，完成 PyInstaller 构建、随包运行依赖、Inno Setup 安装、升级数据保留、卸载和恢复验证。**只有用户明确审核通过 M3 并要求继续，才开始 M4。** 本次仅本地提交和附注审核标签，不推送、不合并、不发布。
