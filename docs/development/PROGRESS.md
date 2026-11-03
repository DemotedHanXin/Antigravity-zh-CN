# Windows 管理器开发进度

更新日期：2026-11-03（Asia/Shanghai）。本文件记录阶段进度与审核停点；需求、架构和验证基线见 [M0 基线与开发约定](M0-baseline.md)。

## 当前交付与审核状态

| 项目 | 状态 |
| --- | --- |
| 唯一开发分支 | `feat/DragonGirl` |
| M0 起点 | `559020e6bc398c2429d666ec8b3614e70b076402` |
| 当前阶段 | M1：真实版本接入 |
| 阶段状态 | M1 已完成，待用户审核；限定范围实机验收与最终回归通过 |
| M0 审核 | 用户已明确批准继续 M1；M0 快照为 `manager-v0.1.0-m0-review.1` |
| 最近阶段快照 | M1：`manager-v0.1.0-m1-review.1`；实际 commit SHA 见交付消息或 git rev-parse |
| 下一阶段 | M2：词典与审核流程；未开始，须 M1 完成并获用户批准 |
| 远端操作 | 本阶段不推送、不合并、不发布 |

```powershell
git rev-parse 'manager-v0.1.0-m0-review.1^{commit}'
git show --stat manager-v0.1.0-m0-review.1
```

标签是待审核快照，不代表产品发布或用户批准。文档引用标签而不写入自身 commit SHA，避免自引用。

## 固定工作流程

1. 始终在 `feat/DragonGirl` 开发；每阶段开始前检查分支和工作区，保留用户已有改动，不将无关改动纳入提交。
2. 每次只实施当前阶段；不新建功能分支、不合入 `main`、不删除现有分支。
3. 完成该阶段的相关验证，更新本文件和独立阶段记录，创建本地 commit 与附注标签。
4. 交付完成内容、文档路径、验证结果、commit SHA、标签、审核步骤和下一阶段待办，然后停止。
5. 只有用户明确表示审核通过并继续，才进入下一阶段。询问进度、指出问题或没有回复都不算批准。
6. 用户要求修改时仅返工当前阶段，使用新提交和递增审核标签；不覆盖旧标签、不改写已有审核历史。
7. 未达到交审条件时如实记录阻碍，不标记完成，也不提前实施下一阶段。推送远端、合并和发布另行安排。

M0 首次交审提交信息为 `docs: complete M0 baseline and development agreement`，标签为 `manager-v0.1.0-m0-review.1`。M1 达成交审条件后使用 `manager-v0.1.0-m1-review.1`；返工依次使用 `review.2` 等，不覆盖旧标签。标签采用 `git tag -a` 创建，并在说明中写明阶段、验证摘要和“待用户审核”。

用户于本轮明确要求：后续启动应用、查看界面和真实 API 联调由用户手动执行；助手提供命令、预期结果和反馈方式，继续负责代码修改与无界面隔离测试。不得自行恢复桌面操作或启动测试安装。

## 阶段与进入条件

| 阶段 | 工作及交审条件 | 当前状态 |
| --- | --- | --- |
| M0：基线与开发约定 | 固化需求、架构、现状与目标差异、验证基线、阶段规则 | 已交付，用户已批准继续 |
| M1：真实版本接入 | 在隔离测试安装中验证 2.28.2 的窗口、preload、动态端口和 UI 区域；跑通请求、显示、还原与管理器关闭后运行 | 已完成，待用户审核；见 [M1 记录](M1-real-integration.md) |
| M2：词典与审核流程 | 抽离内置数据、统一 DOM 管线、个人覆盖、7 天候选、采纳／拒绝、旧数据迁移；验证并发和过期 | 未开始；等待 M1 审核通过 |
| M3：统一管理器 | PySide6 页面、共享服务、后台任务、准确的状态显示和 Windows 用户绑定密钥保护 | 未开始；等待 M2 审核通过 |
| M4：代理与安装包 | 代理预览／执行／撤销入口、PyInstaller 构建、Inno Setup 安装、升级和卸载；干净环境可用 | 未开始；等待 M3 审核通过 |
| M5：发布前验收 | 完整回归、真实应用验收、支持矩阵、使用文档和候选安装包 | 未开始；等待 M4 审核通过；公开发布仍需批准 |

各阶段建立独立记录，固定包含：目标与完成内容、实现／接口／数据变化、验证命令与结果、使用与恢复方式、用户审核事项、下一阶段待办及进入条件。尚未开始的阶段不预建完成记录。

## 当前进展与下一步

第八轮同实例服务恢复已通过，用户无需继续采样。正式兼容配置固化 2.28.2 / Windows x64 的主页四个导航正文标签；匹配后停用旧广域 DOM observer，其余区域不属于本次支持范围。真实 AI 页面补译与纯 ASAR 布局启动仍未验证。最终 Python 181 项（178 通过、3 跳过）、JavaScript 161 项（160 通过、1 跳过），默认 registry 对原始样本的离线识别／暂存注入也通过。交付 `manager-v0.1.0-m1-review.1` 本地快照后停止，M2 等待明确批准。

## 过程记录

以下按当时状态记录；早期“待验证”及“registry 为空”不代表最终状态。

- 已识别 2.28.2 的主入口、窗口工厂、独立本地服务和 Electron 44 preload 差异；动态绑定和完整性检查代码已补充，真实兼容 registry 仍为空。
- 用户截图确认隔离副本已进入主界面、现有设置工具的固定文案 API 测试成功。这两项不等于实际页面 AI 翻译成功。
- 手动诊断工具已改为明确命令触发，仅生成固定标签结构报告；不自动抓取整页、截图或聊天内容。
- 首轮用户采样已成功：主路由 `/`，四个固定导航正文标签、安全窗口开关及零 preload 错误均已确认。下一步用户按 [导航桥接候选验证](../../tests/manual/README.md#第二轮导航桥接候选验证) 安装隔离候选、重启并反馈结果；这一轮强制关闭 AI。M1 commit 和标签须在整阶段完成后交审，目前不得标记 M1 完成。
- 第二轮用户安装与重启成功，四处导航中文；报告确认 96 次已授权状态请求、0 次翻译请求、0 个 preload 错误。当前进入 [受控未命中测试](../../tests/manual/README.md#第三轮受控未命中测试)，由用户运行 success／failure／disabled 模式，不使用真实密钥。M1 仍待后续还原、边界及完整回归验收。
- 首次 success 采样处于带 query 的根路由，翻译请求／提供方调用均为 0；未达到补译成功条件。当前先核对用户显示状态和操作步骤，保持页面来源限制，不把报告 status=ok 误作翻译成功。
- 不导航复测确认无 query、四处选择器吻合，但仍未发翻译请求。本地已复现并修正浏览器定时器接收者错误，53 项相关 JS 回归通过，等待用户重新安装受控候选实测；导航后的 query 适配仍为独立待办。
- 修复后用户实测已通过：报告 `ui-50de7a6751d3cff460aa9c57f1c59cad.json` 为 controlled-success，翻译请求 1 次、本地受控提供方调用 1 次、preload 错误 0；截图与限定报告均显示“自动化（测试译文）”。当前等待 failure／disabled 两模式和设置工具关闭场景的用户反馈；生产 registry 仍未启用。
- 受控 failure 实测通过：报告 `ui-9136282bfe79854e9313fbefa39f9f86.json` 确认翻译及本地提供方各 1 次、preload 错误 0，Automations 保留英文，其他三处内置中文不受影响。当前等待 disabled 零请求及设置工具关闭场景反馈；后续仍需处理导航、还原和阶段回归。
- 受控 disabled 实测通过：报告 `ui-c36ab68046dc98b29af973ae94ccfe47.json` 中授权状态请求 16 次、翻译请求和提供方调用均为 0、preload 错误 0；四个标签显示符合预期。三模式测试已齐全，当前继续隔离副本还原及导航边界验证，尚未达到阶段交审条件。
- 2026-11-03：用户 reset 完成，但随后 launch 因旧备份仍引用已移除的 `.dragongirl/bootstrap.cjs` 报 WinError 3。已修复 `--refresh-package` 的入口校验顺序，并补充 5 项回归；M1 Python 工具专项 20 项通过。当前安装的 `dist/main.js` 存在，等待用户直接重试 launch（无需再 reset）；尚未确认还原后的实际界面和登录状态。
- 2026-11-03 18:51:35（Asia/Shanghai）：修复后的用户采样 `ui-c893c37ef4f6ed0617f78916a7aedac2.json` 确认 reset 后成功进入主界面，四个导航正文标签恢复英文；bridge.mode=not_installed，全部桥接计数和 preloadErrors 均为 0。隔离组件撤回后的启动／显示通过；是否无需重新登录及设置窗口关闭仍待用户明确确认。下一步定位导航后带 query 的具体操作，不要求重跑已通过的三模式。此项不代替 Restore.py 归档布局恢复或真实 AI 请求验收。
- 用户随后明确确认：还原后无需重新登录，本轮设置工具一直关闭；此前英文回退操作为“主页 → 设置 → 返回主页”。已补充仅供手动采样的有限 query 元数据：固定参数名／固定枚举值，未知名称仅计数、未知值为 null，最多 16 对且超过 2048 字符不解析；不保存原始 URL，不放行带 query 页面 DOM。诊断及桥接／preload 专项 41 项通过。下一步在现有未注入副本重启一次，分别采样设置页和返回主页状态；不需重复安装或重跑三模式。
- 2026-11-03 19:08:33（Asia/Shanghai）：新报告 `ui-2f2f44e0a81929c7e48582482e995e45.json` 已生成，用户明确这是从设置返回后的主页。路由为 `/`、无 query/hash，新增 query 元数据为空且未截断；四个导航正文标签为英文，bridge.mode=not_installed，全部桥接计数及 preloadErrors 为 0。仅证明本次返回主页时没有参数，不能将此前带 query 的状态归因于返回主页，也不能判定翻译回退已修复。当前只需补采停留在 Settings 时的报告，并确认返回操作；无需重跑已有主页采样或三模式。
- 2026-11-03 19:10:46（Asia/Shanghai）：设置页报告 `ui-2211288c16914480cf1109bd8b0de030.json` 为根路由加两项未识别 query、无 hash、未截断；按策略跳过 DOM，preloadErrors=0，组件未安装且全部桥接计数为 0。用户确认点关闭按钮返回主页。静态前端代码也确认设置弹窗使用 query、关闭时移除设置参数；两个采样端口不同，不能当作同一实例的完整导航验收。
- 本轮复现并修复短导航恢复缺口：query 期间标签重建、关闭仅移除弹窗且轮询未观察到中间拒绝时，原 preload 会因配置版本未变化漏掉重扫。成功授权快照现带主进程生成的 `pageEpoch`，返回主页后的新代次触发受限重扫；不放开 query 页面。JS 专项 105 项（104 通过、1 跳过），Python 兼容／M1 工具专项 48 项（46 通过、2 跳过），`git diff --check` 通过。下一步由用户按 [第六轮导航恢复验证](../../tests/manual/README.md#第六轮关闭设置后的翻译恢复) 重装隔离受控候选，在同一次运行中验证；未启动应用、未调用外部 AI，尚未交审。
- 2026-11-03 19:18:57（Asia/Shanghai）：报告 `ui-f4e69ab74a2e07225b4add09043bc12a.json` 已由用户确认为关闭 Settings 后返回主页。controlled-success、端口 52349，snapshots=38、authorizedSnapshots=18、translateCalls=4、providerCalls=1、preloadErrors=0；根路由无 query/hash，显示“自动化（测试译文）”及其他三个内置中文。只读核对隔离安装的主进程运行时与源码哈希一致，preload 含新 pageEpoch 契约。用户另明确确认较快打开／关闭后也正常恢复，翻译设置工具全程关闭。这些显示恢复与独立运行项目通过；不能从累计计数推断每次调用的来源或次数，设置页期间的请求边界仍需同实例报告，M1 其他验收未完成。
- 2026-11-03 19:22:12.775 至 19:22:28.991（Asia/Shanghai）：设置页连续报告 `ui-5b49d034f6b829c3f60bb0b30df1394b.json`、`ui-6b723e7e37624d3c21e92e8fde263800.json` 同为端口 58221、controlled-success，间隔 16.216 秒。snapshots 从 14 增至 25，authorizedSnapshots 保持 4、translateCalls／providerCalls 均保持 1，preloadErrors=0；两次均为带两项未知 query 的根路由，诊断跳过 DOM。该设置页停留区间内无新增授权、翻译或提供方调用，边界实测通过。第六轮导航相关验证结束，无需重复采样；下一步核对隔离安装的 Restore.py 归档布局恢复及服务生命周期，之后完成回归、兼容配置和阶段交审。
- 第七轮准备：已只读验证隔离原始归档全部条目、主入口及 unpacked 依赖，SHA-256 为 `046fa2ba9abe96bc915eb7ed12887c067396a8a12148842ab4f4e2cd05a68feb`；尚未执行还原。用户下一步按 [归档恢复说明](../../tests/manual/README.md#第七轮原始归档恢复与隔离副本重建) 退出副本后执行明确目标的 `Restore.py --no-launch`，反馈后再核验布局。现有实验启动器仅支持解包目录，后续须 Patcher 重建再 helper reset；不能把重新解包后的启动当作纯归档布局启动验收。
- 第七轮归档切换已通过：用户确认 launch.lock 不存在，手动执行 `Restore.py --app-dir .m1-lab/install --no-launch`，退出码 0。助手只读复核 `app.asar` 存在、`app.asar.disabled`／`app` 均不存在、`app.asar.unpacked` 保留，无 `.antigravity-restore-*` 残留；归档 1085 条目及 `dist/main.js` 入口通过校验，SHA-256 与还原前完全一致。接下来由用户执行明确目标的 Patcher，再 helper reset，重建隔离包装器需要的解包副本；尚未验证重建后的启动和本轮登录保留。
- 第七轮解包重建已通过：用户执行显式目标的 Patcher 和 `m1_bridge.py reset`，两步退出码均为 0。只读复核布局回到 `app + app.asar.disabled + app.asar.unpacked`，版本 2.28.2、入口 `dist/main.js`，`.dragongirl` 和 launch.lock 均不存在；package、入口、preload、menu、tray、窗口／服务／常量模块共 8 个文件字节与原始归档一致，归档哈希未变，无安装临时目录。下一步仅需由用户通过包装器启动、capture 并确认登录保留；服务生命周期仍为源码和模拟覆盖，尚无受控实机重启证据。
- 2026-11-03 19:32:14（Asia/Shanghai）：重建后报告 `ui-60a7e4ac2540cf4c42453dddab4a2e1c.json` 为 status=ok、bridge.mode=not_installed、全部桥接计数与 preloadErrors 为 0；端口 56368、根路由无 query/hash，四个导航正文标签均为英文，用户截图一致。用户明确确认直接进入主页、无需重新登录。第七轮归档切换→解包重建→包装器启动及登录保留通过；纯归档布局启动仍未验证。当前仅准备用户显式触发的隔离服务生命周期测试入口，尚未操作真实服务；之后完成回归、兼容配置、commit 和附注标签，再交审停止。
- 第八轮入口已准备：新增仅发布请求的 `restart-service --from-report`，包装器绑定当前会话、实际语言服务子进程对象／代次／PID／端口和安全 Hub 主页，排他写入并同步 claim 后最多尝试一次。capture 增加有限生命周期字段；不按进程名称操作，不自动采集重启后的 UI。完整 Python 回归 177 项（174 通过、3 跳过），JavaScript 155 项（154 通过、1 跳过），Python 3.8 语法及 `git diff --check` 通过，独立审阅无剩余阻塞问题。未执行真实服务重启；下一步按 [第八轮手动验证](../../tests/manual/README.md#第八轮同一应用实例内的服务恢复) 安装受控候选、启动新版包装器并采集当前主页基线，随后由用户显式触发。M1 尚未完成、未创建阶段提交或标签。
- 2026-11-03 19:43:18（Asia/Shanghai）：首份生命周期基线 `ui-0aefb81a0b202b3411258c0003586d70.json` 为 controlled-success，snapshots=11、authorizedSnapshots=10、translateCalls=1、providerCalls=1、preloadErrors=0；主页四个标签显示预期中文，服务 generation=1，新增元数据已生效。核对时 appPid 136772 和 servicePid 128052 均不存在、launch.lock 不存在，用户确认采样后已关闭应用或启动终端；尚未发送重启请求。该报告不能用于新会话，不算服务恢复失败。下一步无需重装，重新 launch 并 capture，保持应用和启动终端运行到本轮验证结束。
- 第八轮首次真实触发：有效基线 `ui-b5a24d10520ad85021a40679652a39d3.json`，主程序 PID 28960、服务 generation=1／PID 95968／端口 60109。回执 `service-restart-ea55e816b39535fdf019dc22f5ee0c51.json` 于 19:51:03.224（Asia/Shanghai）确认 signal_sent；16.741 秒后的 `ui-c4c41b7b74c7adcfe87d57d4784d7b5d.json` 保持同 session／appPid，服务已换为 generation=2／PID 121024／端口 53209，但 status=no_eligible_window、windows=[]，尚不能判定窗口重连通过。用户随后确认主页和测试译文已经恢复；下一步仅补采当前恢复状态以核对新服务窗口，不重复触发服务重启。
- 第八轮最终通过：2026-11-03 19:54:55.053（Asia/Shanghai）的 `ui-a8ad2d9da734111136c688d8e73d288d.json` 为 status=ok、preloadErrors=0。同 session／appPid=28960／windowId=1，窗口已连接 generation=2 的端口 53209，根路由无 query/hash，四标签中文含测试译文；snapshots=230、authorizedSnapshots=216、translateCalls=2、providerCalls=1。用户确认主页恢复。回执到采样的 231.829 秒不是实际恢复耗时，不外推连续崩溃或真实 AI。原始过程报告保留，当前不再要求重复任何已通过实机步骤。
