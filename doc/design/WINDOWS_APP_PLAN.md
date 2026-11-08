# Antigravity 中文助手：Windows 应用规划

日期：2026-11-05。状态：产品方向已确认，开发尚未开始。

已确认：公开发布，面向不懂代码的普通用户；优先简单、可靠、可恢复；首页采用 A 状态总览，结合首次操作引导。暂定名称“Antigravity 中文助手”，最终名称、图标、收费方式待定。本轮只新增规划文件，不修改现有业务代码或真实 Antigravity 安装。

## 1. 问题与证据

用户原话：“把翻译用的词典可视化展示，并支持用户自己添加修改，把汉化和修复启动代理这两个功能添加进我的软件。”

规划时源码基线（2026-11-05；最新实现与验证结果见 [项目状态](../PROJECT_STATUS.md)）：

| 能力 | 当前入口 | 应用化还缺什么 |
| --- | --- | --- |
| 汉化 | src/Antigravity-Patcher.py / apply_patch | 可选择的安装、阶段进度、结构化结果、自定义词典输入 |
| 还原 | src/Restore.py / restore | 状态识别、清楚的操作范围、恢复结果 |
| 代理配置 | src/Setup-Proxy-Shortcuts.py / install | 可读预览、快捷方式清单、部分成功状态 |
| 代理清理 | src/Cleanup-Proxy-Shortcuts.py / plan_cleanup、apply_cleanup | 在窗口内预览和执行 |
| 翻译 | Patcher 内嵌 JavaScript 对象、数组、动态规则 | 数据独立保存、编辑、校验、覆盖合并 |
| 打包 | 现有 macOS 构建工作流 | Windows 构建；现有工作流引用根目录脚本，与当前 src 路径不符 |

规划时 app 目录没有应用实现，未发现 Windows GUI 入口或打包 spec。当时 README/PROJECT_STATUS 部分说明落后于代码，例如 CLI 已始终不自动启动；此处保留规划基线，当前使用说明与验证结果以仓库 README、项目状态、源码和测试为准。

2026-11-05 执行 `.venv/Scripts/python.exe -B -m unittest discover -s tests`：95 项，94 项通过，1 项失败。失败为 `test_marketplace_descriptions_match_full_truncated_and_wrapped_text`，实际译文与预期不同；当时根因尚未判定，不能据此宣称已满足发布条件。该结果仅为规划时的历史记录，不代表最新测试结果。源码及测试当时已有未提交修改，后续实施应保护已有工作。

外部证据核对了 3 个上游 Issue 的直接页面/接口，3 个均能重取并核对标题或正文，0 个被采用后验证失败：

- [#10 新版漏译](https://github.com/MIMICTE/Antigravity-zh-CN/issues/10)：原话“新版本也不少英文，希望能适配，包括右键菜单”。
- [#7 翻译范围](https://github.com/MIMICTE/Antigravity-zh-CN/issues/7)：原话“代码页的内容也被进行了替换”。这是报告者反馈，未在本分支复现。
- [#12 文件占用](https://github.com/MIMICTE/Antigravity-zh-CN/issues/12)：错误包含“另一个程序正在使用此文件，进程无法访问”。

这些反馈支持兼容性、翻译范围、失败恢复的重要性，但每类只有有限来源，按 vibe-check 标准仍是“线索”，不能当作三个需求各自都得到三方验证。初步 Reddit 检索多为模型回答语言问题，与界面汉化无关，未纳入结论。没有充分用户访谈、付费意愿或竞品体验数据，本方案不编造机会分数、市场优势或销量预测。公开发布前用第 21 节的小样本试用补证。

## 2. 愿景

一个全中文 Windows 桌面工具。用户打开后能看到检测到的 Antigravity 安装、汉化状态、代理入口状态；点击操作前知道将改什么，结束后知道是否完成及下一步。需要改词时，像编辑表格一样修改原文和译文。

## 3. 三句话目标

1. 目标：普通用户无需运行脚本，完成汉化或代理启动修复，并能维护自己的译文。
2. 当前办法：运行多个脚本，阅读终端输出，在源码中的 JavaScript 词典里改词。
3. 痛点：入口分散，修改容易出错，难以判断保存、生效和失败后的状态。

验收主线：首次使用者能独立选择安装、完成汉化、改一条词并重新应用、恢复英文；代理功能有独立的配置与移除路径。

## 4. 面向谁

面向使用 Antigravity 的普通 Windows 中文用户。第一轮招募 5 位不熟悉脚本的试用者，随后扩展至约 10 位。不是已招募人数。建议首发验证 Windows 11 x64；Windows 10、ARM64 是否列为正式支持要按所选依赖版本及实测决定，不能直接继承脚本的兼容性声明。

## 5. 界面与用户流程

已选择 A 状态首页 + B 首次引导；词典采用 C 的表格编辑方式，失败提示借用 D 的问题入口。

2026-11-05 补充：用户选择“更柔和的圆角卡片风”。详细样式以 [前端样式开发计划](FRONTEND_STYLE_PLAN.md) 为准，包含浅/深色参数、字体尺寸、组件全状态、四页布局、窗口缩放、Qt 实现与 UI-01～UI-07 验收。另见 [交互样式原型](frontend-style-preview.html) 和 [设计参数](assets/frontend-tokens.json)。原来的四种方向草图保留为布局决策记录，不作为最终配色和尺寸标准。

2026-11-05 素材迭代：按用户提供的 Gemini 海报及日夜背景，样式更新为“虹光日夜”。首页左侧功能、右侧人物；浅色珠光白/淡紫，深色靛蓝/浅紫；词典工作区保持实色。新增 [浅色首页](ui-home-light.png)、[深色首页](ui-home-dark.png) 与 [词典编辑稿](ui-dictionary-light.png)，以及关闭插画、紧凑窗口和资源缺失回退规则。设计版本 v1.2；PNG 是设计稿，正式软件尚未实现。

| 页面 | 用户看到什么 | 主要操作 |
| --- | --- | --- |
| 概览 | 安装路径与版本；汉化、词典待应用、代理状态各自独立 | 选择安装、应用汉化、检查代理、手动启动 |
| 翻译词典 | 搜索框，原文/译文/用途/来源/修改状态；选中后右侧编辑 | 新增、修改、恢复内置、禁用、自定义导入导出 |
| 代理启动 | 系统代理配置类型、启动器状态、将修改的快捷方式及未处理项 | 预览修复、执行修复、移除代理启动 |
| 恢复与帮助 | 归档检查、上次结果、当前会话详情、版本支持说明 | 恢复英文、导出脱敏诊断、查看帮助 |

首次引导只在找不到/找到多个安装或第一次执行时出现。已找到唯一安装时直接进入概览，不要求注册、登录或填资料。打开 30 秒内应能理解当前状态和下一步；不承诺 30 秒完成解包汉化。

正常流程：打开 → 检测并选择安装 → 检查版本/归档/进程 → 预览操作 → 用户确认保存工作并关闭目标应用 → 暂存生成 → 验证 → 切换生效 → 展示结果 → 用户主动启动。

改词流程：搜索原文 → 修改译文 → 校验 → 保存到本地 → 显示“已保存，尚未应用” → 预览并重新应用汉化 → 显示对应安装已应用的词典版本。

异常流程：预检失败 → 停止写入并提供具体处理；执行失败 → 尝试回滚 → 重新读取安装状态 → 分别展示文件切换/残留清理/启动结果。无法回滚时保留恢复材料和实际路径，不提示假成功。

边界流程：多个安装必须选择；新版本结构未知则阻止写入并说明支持范围；官方更新造成归档冲突则停止；词典导入有冲突先预览；应用期间禁止第二次操作；切换安装后重新检测；任务不可安全取消的切换阶段禁用取消按钮，并解释原因。

空状态：无安装时提供“选择安装目录”和安装说明；无自定义词条时仍显示内置词典及“添加词条”；搜索无结果显示“使用这个原文新增”；无快捷方式时解释可创建个人开始菜单入口。

## 6. 第一版与后续版本

V1 必须具备：

- 识别安装、手动选择、版本与结构预检；检测状态不靠文件是否存在就简单下结论。
- 汉化、重新应用词典、恢复英文；保留现有归档验证、暂存、回滚保护。
- 普通词条可视化搜索、添加、修改、禁用、恢复内置；中文与英文均可搜索。
- 自定义词典 JSON 导入导出；导入校验、冲突预览和明确的覆盖/保留选择。
- 代理修复预览、配置、清理；保留参数、图标、工作目录；部分成功逐项说明。
- 后台执行、阶段进度、重复操作互斥、错误恢复建议；禁止界面卡死或伪造精确百分比。
- Windows 可运行包及安装包；用户无需安装 Python；升级保留自定义词典。
- 操作详情保留在当前会话，用户主动导出脱敏报告；不新增代理备份归档或默认永久代理日志。

V2+：社区词典包、差异审核、更多批量操作、辅助翻译建议、在线词典更新。AI 翻译、自动采集界面文本、自定义正则脚本、后台自动打补丁、账号和云同步均不进入首版。

## 7. 架构与代码归属

窗口界面 → 词典/汉化/代理三个功能模块 → 本地数据与目标安装。

推荐保留 Python 核心，通过普通模块导入调用；GUI 与 CLI 共享同一业务逻辑。将带连字符的脚本逐步变为兼容入口，把可复用实现放进可正常导入的模块。避免 GUI 通过拼命令行调用外部 Python，也避免复制一份修复逻辑。

建议结构（开发时新增，不表示现已存在）：

```text
app/main.py
app/ui/                     窗口、页面、可访问性
app/features/dictionary/    词典合并、校验、导入导出
app/features/localization/  汉化/还原流程与状态检查
app/features/proxy/         计划、应用、清理、结果
app/platform/windows/       安装发现、进程、PowerShell/快捷方式
app/storage/                用户数据路径、原子写入、版本迁移
app/resources/              内置词典与翻译模板
src/                        保留原命令行入口
packaging/                  Windows spec 与安装器脚本
tests/                      模拟安装、词典、失败路径、打包冒烟
```

任务结果结构至少含：状态 success/partial/failed/cancelled、已执行步骤、失败项目、可恢复状态、下一步。进度事件以阶段为单位。每个目标安装只允许一个写任务，词典保存对任务使用不可变快照。

界面默认普通权限运行。只读词典不要求管理员权限。目标目录不可写时说明具体受阻路径；确需提升权限时只对明确操作处理，并重新校验路径和输入，不能自动放宽 PowerShell 策略。

源码和构建配置留在当前 Git 仓库；后续按用户授权提交和发布。用户可以自行构建或更换界面库。

## 8. 技术选择

| 选择 | 推荐 | 原因 | 备选 |
| --- | --- | --- | --- |
| 桌面界面 | Python + PySide6 Qt Widgets | 复用 Python，适合表格、对话框和后台任务 | Tkinter：依赖少，但复杂词典体验需更多手工处理 |
| 词典存储 | 内置 JSON + 用户 JSON 覆盖层 | 无服务器，易导出，升级不覆盖用户修改 | 数据明显复杂后再评估 SQLite |
| 可运行包 | PyInstaller onedir | 先验证依赖完整性；与仓库已有打包经验接近 | Qt 官方 pyside6-deploy |
| 公开分发 | onedir 内容封装为安装器；附 ZIP | 普通用户可安装、创建入口和卸载 | 内测只发 ZIP |
| 安装器 | Inno Setup，实施前核对适用许可 | 支持 Windows 安装和卸载 | 若分发要求变化，再选其他安装工具 |

固定经过验证的依赖版本，版本号在实施时确定。打包用 Windows 构建环境；Node 只作为翻译引擎测试工具，不成为用户机器的运行前提。PyInstaller 官方文档说明可打包 Python 运行时，且建议先验证目录包再尝试单文件模式。[文档](https://pyinstaller.org/en/stable/operating-mode.html)

Qt 提供官方部署工具作为备选。[文档](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html) Inno Setup 支持单个安装 EXE、快捷方式及卸载；商业使用许可需按实际发布方式核对。[官网](https://jrsoftware.org/isinfo.php)

## 9. 数据模型与词典规则

每条普通词条包含：稳定 ID、原文、译文、用途 ui/menu、分类、是否启用、来源、说明。匹配键为“用途 + 完整原文”，大小写按现有语义保留。不要默认在所有正文中做子串替换。

词典分三层：随程序发布的内置数据；用户新增与修改；现有动态翻译规则。界面展示有效结果及来源。用户编辑内置词条时保存覆盖项，不直接改随程序安装的数据。恢复内置即删除覆盖项；删除用户新增项与禁用内置项分开表达。

优先级：用户精确覆盖 → 内置精确匹配 → 现有动态规则。禁用项需要明确阻止同来源被后续回退规则重新翻译。保护代码、终端、输入内容和用户正文的范围优先于翻译规则，并增加误译回归验收。

UI 词典、菜单词典、固定描述规则需要保留各自用途。动态规则提供可读名称和示例供查看；首版只开放普通文本词条编辑，不能将任意正则或 JavaScript 当作可导入词典。托盘、原生更新弹窗等代码级替换显示为系统规则，解释其适用版本。

存储建议：`%LOCALAPPDATA%/AntigravityZhCN/` 下保存 settings.json、custom-dictionary.json、按安装区分的应用记录。记录含 schemaVersion、内置词典版本、用户修订号、目标版本和成功应用时间；记录仅作提示，重新打开仍核对实际安装，不能把记录当作成功证明。

保存方式：校验后写同目录临时文件，再替换目标。损坏 JSON 时保留损坏文件，显示恢复/重新导入入口，禁止静默清空。可保留一份用户词典上次有效版本；这与不产生代理备份的现有约定分开。

导入限制：只接受约定 JSON 结构、文本字段和已知用途；限制文件体积、条目数和字段长度；拒绝重复键、未知 schema 及代码字段，导入预览后再合并。自定义文本用 JSON 序列化注入模板，不通过字符串拼接生成可执行代码；覆盖引号、反斜杠、换行、美元符号、Unicode、特殊对象键等测试。

保存不等于应用。只在成功切换安装后记录该词典修订已生效。模拟文本预览只说明匹配结果，实际界面能否显示仍受 Antigravity 版本和节点范围影响。

## 10. 开发规则

一处业务逻辑只保留一个实现。界面、规则、存储分开；词典、汉化、代理按功能归组。先保留当前未提交工作，再做小范围修改。错误必须显示可执行的下一步。保护原版归档；不得根据目录名盲删文件。窗口与 CLI 对同一输入应产生相同业务结果。

技能提供的原文 House Rules 见附录，供后续项目指南采用；本轮不新增或改写 AGENTS.md。

## 11. 外部连接

仅访问本机安装文件、Windows 系统代理配置和快捷方式接口。沿用 PowerShell 与 WScript.Shell 的现有处理并收拢到一个实现。代理仅适配当前系统 HTTP/混合端口；PAC、纯 SOCKS 不在首版支持内。功能名为“修复代理启动”，不能宣传为“修复所有网络问题”。

配置成功、端口连通、账号可用和服务可达是不同结果。首版如未实现连通性测试，必须标注“未测试连接”；不因启动器存在就显示“网络正常”。不改全局代理，不关闭正在运行的应用来自动应用代理；提示用户完整退出后从修复入口启动。

## 12. 成本

本地功能无必须的服务器、数据库或 AI 接口月费，运行架构的外部服务成本可为 0。开发时间、构建资源、分发带宽和支持工作另计。正式发行的签名与时间戳服务价格待供应商和发行方式确定；不承诺免费签名或无系统提示。依赖及安装器许可在发布前形成清单，付费产品形态另行确认。没有云端轮询架构，首版也不引入持续远程检查。

## 13. 工作量估计

复杂度约 6/10：界面本身中等，难点是可靠修改另一应用的安装与保持用户词典。已有核心逻辑可复用。补入完整样式、浅深主题和缩放验收后，内测版本与打包验证粗估由 10–15 调整为 12–18 个有效开发工作日；公开稳定版本取决于实际版本兼容问题和反馈，不作固定交期承诺。

## 14. 首批用户与发布渠道

建议从当前 GitHub 项目的使用者和愿意参加测试的汉化用户中招募，实际名单待定。第一步由维护者发布测试招募和短演示，引导填写安装版本与三个任务的结果；本轮不代发消息。GitHub Releases 作为候选下载入口，首轮仅标注测试版本，不以一次测试宣称全面兼容。

## 15. 自然传播

没有已验证的增长循环。用户主动导出词典 → 向朋友分享 → 对方导入使用，是可验证的分享路径，不要求账号或强制邀请。V1 包含导入导出是为了保留和交换用户修改；不自动上传、不默认公开。发布后通过自愿反馈询问下载来源，验证是否有人因共享词典而来。单人使用即可获得价值，无网络冷启动门槛。

## 16. 发布前必须处理

- 现在：关键文件校验、任务互斥、权限范围、词典输入校验、原子保存、可恢复错误。
- 现在：键盘可操作、焦点可见、文字标签、不只靠颜色表示失败；测试 125%/150%/200% 缩放和较小窗口。
- 发布前：无 Python 的干净 Windows 测试、版本支持表、升级保留词典、卸载行为说明、依赖许可和发行签名方案。
- 发布前：诊断导出脱敏，不默认包含用户名路径、代理凭证或环境变量全集。
- 发布前：卸载助手默认只卸载助手，不悄悄撤销另一应用的汉化或代理；提供明确的操作说明。用户词典默认保留，删除由用户单独选择。
- 后续：更新适配流程、问题模板、版本回归与维护节奏。

## 17. 发布审查

必须专项检查：路径穿越/重解析点、归档损坏、文件占用、磁盘空间不足、半完成恢复、代理部分失败、导入执行代码风险、并发操作、用户数据升级与删除边界。技能提供的通用审查提示见附录；本地应用没有账号/支付时将这些项标为不适用，不能为了通用模板增加云功能。

## 18. 与开发工具协作

每阶段写清可看见的验收结果。非必要不改无关模块；发现既有问题先记录。每次小改动后执行对应检查，检查通过再继续。项目指南保持短，复杂说明留在功能文档中。操作详情先用当前会话事件流，需要时由用户导出；若日后引入持久日志，单独设计脱敏与清理上限。

## 19. 开发阶段与验收

0. 验证假设与基线（约 1 天）：展示方案给 5 位目标用户；确认他们理解保存/应用及两种恢复；查清已有 1 个失败测试，记录当前可工作快照。完成标准见第 21 节。
1. 词典数据化（约 2–3 天）：提取内置数据及用途，保留原有匹配顺序，加入用户覆盖与校验。完成标准：旧翻译回归通过，新词可保存/恢复，特殊字符不会成为执行代码。
2. 桌面界面（约 4–6 天）：依次完成前端规范 UI-01 参数与双主题、UI-02 组件状态样例、UI-03 窗口/概览/引导、UI-04 词典、UI-05 代理/恢复；先连接只读状态，再做词典编辑。完成标准：普通用户可以查改词，清楚看到尚未应用；柔和卡片风一致，宽窄布局可用，键盘和缩放验收通过。UI-06 真实任务反馈归入阶段 3，UI-07 打包视觉验收归入阶段 4，避免重复计时。
3. 汉化与代理接入（约 3–4 天）：统一业务接口、预览、后台执行、阶段事件、完整/部分/失败结果。完成标准：隔离安装中跑通汉化→再应用→还原及代理配置→清理→再配置；验证失败保护。
4. Windows 打包与内测（约 2–3 天）：可复现构建、目录包、安装器、诊断说明。完成标准：无 Python 测试机能完成主线，中文/空格路径可用，升级不丢词典，卸载边界正确。
5. 发布准备与小规模发布（约 1 天起）：处理试用反馈，补支持表、发布说明、校验值和许可文件。完成标准：发布阻断问题清零，安装/恢复人工验收有记录；正式发布行为按用户后续指令执行。

每阶段的 CHECKPOINT 见附录。按照所调用技能的要求，每阶段结束应展示结果并等待用户反馈；后续用户若明确授权连续实施，可按其最新指令调整节奏。

## 20. 未确定事项

最终产品名和图标；公开免费还是收费；支持的具体 Windows/Antigravity 版本组合；签名预算；测试者名单。暂按本地、无登录、无收费模块的首版设计。缺少上述选择不妨碍先验证词典与功能边界，但发布前需定下支持范围和发行方式。

## 21. 最关键的假设与廉价验证

假设：普通用户能理解这套“状态 → 预览 → 操作 → 结果”流程，并能区分保存词典、应用汉化、恢复英文、移除代理。

验证：用界面草图和之后的隔离演示包，让 5 位目标用户独立完成“汉化、改一个词后应用、恢复英文、配置并移除代理启动”任务，不现场口头指路。通过信号：至少 4/5 完成主要流程且正确解释两种恢复；无人误删原版或误以为保存已经生效。若未达到，先简化文案和流程，再扩大开发与公开发布。测试尚未进行，不能写成已经验证。

技术假设同步验证：词典抽离前后在相同样本上输出一致；实际支持版本的 GUI/菜单/动态内容覆盖情况需真实应用验收。

## 22. 简明词汇

- GUI：用窗口和按钮操作的软件界面。
- 内置词典：软件随安装自带的翻译。
- 用户覆盖：保留内置原文，单独存下用户选择的译文。
- 结构化结果：把成功、失败、已完成项目分别记录，方便界面准确展示。
- 原子保存：先写好新文件，再一次替换旧文件，降低保存中断风险。
- 回滚：操作失败后尝试退回可用状态。
- 打包：把程序和运行依赖一起交给用户，使其无需安装 Python。
- PRD：说明产品给谁用、怎么操作、怎样算完成的需求文档。

## 附录：技能原文与阶段检查点

### House Rules（原文）

```markdown
# House Rules for [Your App]

You're the engineer. I'm the product manager. Follow these on every change.

## How to work
- Think first: before non-trivial code, say what you'll build and ask about anything unclear. Don't guess.
- Keep it simple: build the simplest thing that solves the problem. No extra features, no "just in case" code.
- Change only what I asked: don't rewrite or "improve" unrelated code. If you spot something, tell me, don't do it.
- Aim at a finish line: work to a clear, checkable "done," then show me how each item checks out.

## How to write code
- Don't repeat yourself: one home for each piece of logic.
- Same name everywhere: if it's a "pickup," it's always a "pickup."
- Handle the sad path: every failure shows a friendly message and a way out.
- Leave a trail: log important actions (what happened, worked or failed, any error).
- Keep layers apart: screens, logic, and data storage stay separate.
- Self-contained features: each feature in its own folder.

## Definition of done (every change clears all of these)
- It works and didn't break anything that worked before.
- Build, linter, and formatter are green.
- Any test fails on the old code and passes on the new (fail-first).
- It touched only what the task needed.
- It matches the project's names and patterns.

Working is the floor, not the bar.
```

### 通用发布审查提示（原文）

- *Security audit:* "Audit my codebase for security vulnerabilities. Check authentication, authorization, input validation, rate limiting, secrets management, file upload security, CORS/CSRF protections, and timing attacks. Give me a severity rating for each issue found."
- *Scalability audit:* "Audit my codebase for scalability issues. Check for N+1 queries, unbounded database reads, missing pagination, polling vs real-time listeners, caching gaps, cold start performance, and concurrent user handling. Estimate the monthly cost impact of each issue."
- *Production readiness audit:* "Audit my codebase for production readiness. Check for error monitoring, test coverage on payment and authentication paths, accessibility basics, and deployment configuration. Tell me what will fail silently in production."

### 日志规划提示（原文）

> "Define a simple, consistent debug-logging plan for this app. Say what to log, the levels (from quiet INFO up to loud ERROR), and short category names for each feature. Write it to docs/DEBUG-LOGGING.md and follow it everywhere you write code."

本项目适配：以上日志提示中的持久化应遵循第 18 节，以会话事件和手动脱敏导出为首版默认。

### 阶段 0：验证假设与基线

具体交付与验收见第 19 节。下列为技能检查点原格式，执行时用本阶段的真实结果替换方括号和示例，不得宣称未完成的功能已实现。

```text
═══════════════════════════════════════════════════════════
🔖 CHECKPOINT: 验证假设与基线
═══════════════════════════════════════════════════════════

STOP here. Before moving to the next phase, explain to the user:

📍 WHERE WE ARE
"We just finished [phase name]. Here's what your app can do now: [plain-language description of what works]."

🔧 WHAT WE JUST BUILT
[1-3 bullet points explaining what was built, in plain language]
- Example: "We set up Supabase. This is where all your users' data gets saved. Picture a giant, organized spreadsheet your app reads from and writes to on its own."
- Example: "We added login with Google. When someone taps 'Sign in with Google,' your app asks Google to confirm who they are, and Google sends back their name and email. Your app never even sees their Google password."

💡 WHY WE BUILT IT THIS WAY
[Connect back to the decisions made during the vibe-check session]
- Example: "Remember how we talked about your users being in a rush? That's why we went with Google login instead of email and password. One tap, instead of thumbing out a password on a phone."

📋 WHAT'S NEXT
"Next up, we'll build [next phase in plain language]. This is where [what it means for the user's app]."

❓ QUESTIONS?
Ask the user: "Does all of this make sense so far? Want to see any of it actually working before we move on? Anything nagging at you?"

Wait for the user to respond before continuing.
═══════════════════════════════════════════════════════════
```

### 阶段 1：词典数据化

具体交付与验收见第 19 节。下列为技能检查点原格式，执行时用本阶段的真实结果替换方括号和示例，不得宣称未完成的功能已实现。

```text
═══════════════════════════════════════════════════════════
🔖 CHECKPOINT: 词典数据化
═══════════════════════════════════════════════════════════

STOP here. Before moving to the next phase, explain to the user:

📍 WHERE WE ARE
"We just finished [phase name]. Here's what your app can do now: [plain-language description of what works]."

🔧 WHAT WE JUST BUILT
[1-3 bullet points explaining what was built, in plain language]
- Example: "We set up Supabase. This is where all your users' data gets saved. Picture a giant, organized spreadsheet your app reads from and writes to on its own."
- Example: "We added login with Google. When someone taps 'Sign in with Google,' your app asks Google to confirm who they are, and Google sends back their name and email. Your app never even sees their Google password."

💡 WHY WE BUILT IT THIS WAY
[Connect back to the decisions made during the vibe-check session]
- Example: "Remember how we talked about your users being in a rush? That's why we went with Google login instead of email and password. One tap, instead of thumbing out a password on a phone."

📋 WHAT'S NEXT
"Next up, we'll build [next phase in plain language]. This is where [what it means for the user's app]."

❓ QUESTIONS?
Ask the user: "Does all of this make sense so far? Want to see any of it actually working before we move on? Anything nagging at you?"

Wait for the user to respond before continuing.
═══════════════════════════════════════════════════════════
```

### 阶段 2：桌面界面

具体交付与验收见第 19 节。下列为技能检查点原格式，执行时用本阶段的真实结果替换方括号和示例，不得宣称未完成的功能已实现。

```text
═══════════════════════════════════════════════════════════
🔖 CHECKPOINT: 桌面界面
═══════════════════════════════════════════════════════════

STOP here. Before moving to the next phase, explain to the user:

📍 WHERE WE ARE
"We just finished [phase name]. Here's what your app can do now: [plain-language description of what works]."

🔧 WHAT WE JUST BUILT
[1-3 bullet points explaining what was built, in plain language]
- Example: "We set up Supabase. This is where all your users' data gets saved. Picture a giant, organized spreadsheet your app reads from and writes to on its own."
- Example: "We added login with Google. When someone taps 'Sign in with Google,' your app asks Google to confirm who they are, and Google sends back their name and email. Your app never even sees their Google password."

💡 WHY WE BUILT IT THIS WAY
[Connect back to the decisions made during the vibe-check session]
- Example: "Remember how we talked about your users being in a rush? That's why we went with Google login instead of email and password. One tap, instead of thumbing out a password on a phone."

📋 WHAT'S NEXT
"Next up, we'll build [next phase in plain language]. This is where [what it means for the user's app]."

❓ QUESTIONS?
Ask the user: "Does all of this make sense so far? Want to see any of it actually working before we move on? Anything nagging at you?"

Wait for the user to respond before continuing.
═══════════════════════════════════════════════════════════
```

### 阶段 3：汉化与代理接入

具体交付与验收见第 19 节。下列为技能检查点原格式，执行时用本阶段的真实结果替换方括号和示例，不得宣称未完成的功能已实现。

```text
═══════════════════════════════════════════════════════════
🔖 CHECKPOINT: 汉化与代理接入
═══════════════════════════════════════════════════════════

STOP here. Before moving to the next phase, explain to the user:

📍 WHERE WE ARE
"We just finished [phase name]. Here's what your app can do now: [plain-language description of what works]."

🔧 WHAT WE JUST BUILT
[1-3 bullet points explaining what was built, in plain language]
- Example: "We set up Supabase. This is where all your users' data gets saved. Picture a giant, organized spreadsheet your app reads from and writes to on its own."
- Example: "We added login with Google. When someone taps 'Sign in with Google,' your app asks Google to confirm who they are, and Google sends back their name and email. Your app never even sees their Google password."

💡 WHY WE BUILT IT THIS WAY
[Connect back to the decisions made during the vibe-check session]
- Example: "Remember how we talked about your users being in a rush? That's why we went with Google login instead of email and password. One tap, instead of thumbing out a password on a phone."

📋 WHAT'S NEXT
"Next up, we'll build [next phase in plain language]. This is where [what it means for the user's app]."

❓ QUESTIONS?
Ask the user: "Does all of this make sense so far? Want to see any of it actually working before we move on? Anything nagging at you?"

Wait for the user to respond before continuing.
═══════════════════════════════════════════════════════════
```

### 阶段 4：Windows 打包与内测

具体交付与验收见第 19 节。下列为技能检查点原格式，执行时用本阶段的真实结果替换方括号和示例，不得宣称未完成的功能已实现。

```text
═══════════════════════════════════════════════════════════
🔖 CHECKPOINT: Windows 打包与内测
═══════════════════════════════════════════════════════════

STOP here. Before moving to the next phase, explain to the user:

📍 WHERE WE ARE
"We just finished [phase name]. Here's what your app can do now: [plain-language description of what works]."

🔧 WHAT WE JUST BUILT
[1-3 bullet points explaining what was built, in plain language]
- Example: "We set up Supabase. This is where all your users' data gets saved. Picture a giant, organized spreadsheet your app reads from and writes to on its own."
- Example: "We added login with Google. When someone taps 'Sign in with Google,' your app asks Google to confirm who they are, and Google sends back their name and email. Your app never even sees their Google password."

💡 WHY WE BUILT IT THIS WAY
[Connect back to the decisions made during the vibe-check session]
- Example: "Remember how we talked about your users being in a rush? That's why we went with Google login instead of email and password. One tap, instead of thumbing out a password on a phone."

📋 WHAT'S NEXT
"Next up, we'll build [next phase in plain language]. This is where [what it means for the user's app]."

❓ QUESTIONS?
Ask the user: "Does all of this make sense so far? Want to see any of it actually working before we move on? Anything nagging at you?"

Wait for the user to respond before continuing.
═══════════════════════════════════════════════════════════
```

### 阶段 5：发布准备与小规模发布

具体交付与验收见第 19 节。下列为技能检查点原格式，执行时用本阶段的真实结果替换方括号和示例，不得宣称未完成的功能已实现。

```text
═══════════════════════════════════════════════════════════
🔖 CHECKPOINT: 发布准备与小规模发布
═══════════════════════════════════════════════════════════

STOP here. Before moving to the next phase, explain to the user:

📍 WHERE WE ARE
"We just finished [phase name]. Here's what your app can do now: [plain-language description of what works]."

🔧 WHAT WE JUST BUILT
[1-3 bullet points explaining what was built, in plain language]
- Example: "We set up Supabase. This is where all your users' data gets saved. Picture a giant, organized spreadsheet your app reads from and writes to on its own."
- Example: "We added login with Google. When someone taps 'Sign in with Google,' your app asks Google to confirm who they are, and Google sends back their name and email. Your app never even sees their Google password."

💡 WHY WE BUILT IT THIS WAY
[Connect back to the decisions made during the vibe-check session]
- Example: "Remember how we talked about your users being in a rush? That's why we went with Google login instead of email and password. One tap, instead of thumbing out a password on a phone."

📋 WHAT'S NEXT
"Next up, we'll build [next phase in plain language]. This is where [what it means for the user's app]."

❓ QUESTIONS?
Ask the user: "Does all of this make sense so far? Want to see any of it actually working before we move on? Anything nagging at you?"

Wait for the user to respond before continuing.
═══════════════════════════════════════════════════════════
```
