# M1：真实版本接入

更新日期：2026-11-03（Asia/Shanghai）。分支：`feat/DragonGirl`。

**状态：M1 已完成，待用户审核；M2 未开始。** 主界面、受控三模式、正常及快速导航恢复、设置工具关闭时运行、设置页边界、归档恢复／解包重建／登录保留及同一实例内服务恢复均已通过。最终离线回归和兼容配置核验通过。交审标签为 `manager-v0.1.0-m1-review.1`，最终 commit SHA 在交付消息中报告；标签只表示待审核，不代表发布或用户批准。

正式兼容配置为 `antigravity-2.28.2-win32-x64-navigation`，仅匹配已核对指纹的 2.28.2 / Windows x64 样本及其外置服务。**匹配后关闭旧的广域 DOM observer，仅支持无 query/hash 的主页四个导航正文标签：New Conversation、Automations、Customizations、Settings。** 其他页面、Projects、属性文字、聊天、代码、输入、终端和内嵌网页均不在支持范围；原生菜单继续静态汉化。四个标签都命中内置词典，正式配置不会因本轮测试自动出现 AI 未命中；实验只对 Automations 人为制造未命中，用本地固定响应验证异步链路。

真实外部 AI 页面补译、纯 ASAR 布局实际启动、其他版本／平台、PySide6 管理器和安装包未验证。源码更新不会自动更改日常安装；本阶段没有部署到日常安装。完整过程记录见下文，其中历史时点的“待验证／registry 为空”不代表当前最终状态。

## 1. 阶段目标及实际完成内容

目标为 Antigravity 2.28.2 / Windows x64 的受约束翻译接入；翻译组件应在管理工具关闭后独立工作。

已完成的开发工作：

- 只读检查用户指定安装及原始归档，创建 `.m1-lab/install` 隔离副本；没有修改日常安装。用户目录、缓存、日志、临时目录独立，实验目录被 Git 忽略。
- 识别 CommonJS `dist/main.js`、`dist/preload.js`、`dist/utils.js` 窗口工厂，以及 `dist/languageServer.js` 管理的本地 HTTPS 服务。网页来自外置 `resources/bin/language_server.exe`，不能只校验 app 内 JS。
- 实现目标窗口登记、实际服务进程与动态端口绑定、精确路由校验、导航撤销和请求前后校验。
- 补充 Electron 44 不再通过 `getLastWebPreferences()` 返回 preload 字段时的处理：使用经过文件指纹确认的窗口工厂传入其构造器 preload 路径，不降低 sandbox/contextIsolation 条件。
- 对匹配 profile 的应用只启用受 UI 白名单约束的 DOM 管线，避免旧 observer 抢先处理不允许区域；本阶段仍保留现有内置词典优先顺序，个人优先和候选流程留给 M2。
- 准备用户操作的隔离助手、按命令触发的固定标签结构诊断和无界面回归。

真实证据的边界：

- 早期隔离运行确认登录引导页、动态本地端口及 sandbox/contextIsolation 开关；未证明主界面翻译。
- 用户本轮提供截图，确认隔离副本已进入主界面，左侧有 `New Conversation`、`Automations`、`Customizations`、`Projects`、`Settings`。
- 用户截图显示设置工具的固定文案连接测试成功；API 密钥不读取、不写入文档。
- 用户触发的 `ui-18bdd7b5828c5aee98d562dffb7ba844.json` 在 2026-11-02 20:58:30（Asia/Shanghai）返回 `ok`：主路由 `/`，无 query/hash，端口 54643（仅此运行实例），sandbox/contextIsolation=true、nodeIntegration=false、preloadErrors=0。
- 报告确认四个正文标签 `New Conversation`、`Automations`、`Customizations`、`Settings` 均位于 role=navigation 的祖先区域；另一个非导航区域的 aria-label 未纳入候选。`Projects` 未采集到，不猜测其选择器。
- 四个标签都能命中内置词典，不把其变中文当作 AI 成功。已准备 `tests/manual/antigravity-2.28.2.candidate.json`，限隔离测试；其中 verified 字段是安装器内部测试契约，外层 acceptanceStatus 仍为 pending-runtime-verification，绝不表示阶段验收通过。生产 registry 仍为空。
- 用户执行候选安装和重启成功，截图确认四处导航中文。第二份报告 `ui-fe9f0013d0831a07c25b515c0f6df917.json`（2026-11-02 21:07:58，Asia/Shanghai）为 ok，端口改为 62268；snapshots=116、authorizedSnapshots=96、translateCalls=0、preloadErrors=0。证明实际目标窗口 IPC 已接通，并非只靠内置中文判断桥接成功。其余 20 次请求未到达授权服务，报告未记录具体原因，不推断全部请求已获授权。
- 首次 controlled-success 报告 `ui-01ac7fac27b144cb037fe940e271b42a.json`（2026-11-02 21:17:20，Asia/Shanghai）：snapshots=63、authorizedSnapshots=26、translateCalls=0、providerCalls=0、preloadErrors=0。采样时 path=/、hasQuery=true；严格页面策略因此不采样该状态，rootFound=false 是未检查 DOM，不代表真实页面没有 root。该轮不能判为补译成功，需用户补充显示状态及进入步骤，先确认查询参数页面来源，再决定是否需要独立审核；不读出参数值，不直接放开 query。

- 用户随后补充：刚打开是中文，打开其他界面后返回主界面变为英文。初始中文是否含“测试译文”尚不确定，不推断受控调用成功。已核对安装副本 preload 包含 Automations 的未命中测试分支；下一轮先重启且不点击导航采样，再单独审核导航状态。
- 诊断词表补充固定中文“新建对话／自动化／自动化（测试译文）／自定义／设置”，用于区分内置中文和受控译文；不改变生产翻译规则或 query 拒绝策略。新版诊断需要重启包装器生效。

## 2. 主要实现、接口及数据格式变化

正式 [兼容注册表](../../localization_runtime/compatibility.json) 固化与实测候选相同的指纹、动态绑定和四标签策略，另记录受控验证范围及证据索引。实验候选保留 `isolated-lab-only` 与逐次验收防护，其测试标记不代表正式 registry 状态。用户配置仍为 schema1；M1 不改变内置词典优先顺序、不迁移词典、不实现 7 天候选。

最终收尾加强 DOM 内容读取边界：先检查路径、排除区域和选择器，再读取文案；扫描不能预读未授权属性；排队／在途节点和 mutation 处理也先复核许可。原文恢复保留受限例外：只比较组件此前写入的已登记槽位是否仍为本次译文，再恢复原文，不收集新候选。六组读取陷阱及生成 preload 回归通过，未为此再次安装或启动实际应用。既有实机证据来自相同四标签策略的实验候选。

第八轮新增仅用于隔离实验的 `m1-service-control.cjs` 和 `m1_lab.py restart-service --from-report`。capture 报告增加 `lifecycle={sessionId,appPid,service:{generation,pid,port}|null}`，服务代次按已验证 ChildProcess 对象变化递增，即使 PID／端口重用也可辨别。CLI 校验 5 分钟内已授权的受控成功主页报告、文件路径、进程记录和安全字段后，只排他发布绑定请求；不直接操作进程。包装器再次核验会话、实际 Hub 窗口、根路由和实际服务对象，先以 wx 写入并 fsync claim，再仅对该子进程发送一次 SIGTERM；每会话最多一次尝试，写入失败也消耗额度。回执独立保存，重复请求／claim／回执、状态变化、停止或采样进行中均不重复操作。未使用按名称终止或任意 PID 命令；未使用会抑制自动重启的 killLanguageServer。没有请求时不会重启，后续 UI 仍由用户单独 capture；`signal_sent` 不能代替恢复验收。

本轮成功 IPC snapshot 新增 `pageEpoch`：由主进程每次成功登记受信窗口时生成的正安全整数，普通轮询保持不变，同 URL 重新授权也会递增。服务快照返回后仍再次校验原授权 entry，成功后才附加代次；未授权响应不带代次。生成的 preload 严格校验此字段，并在代次变化时使旧工作失效、恢复原文、重新扫描已允许的标签，覆盖未被 1500ms 轮询观察到的短导航。代次只存在于运行内存，不改变用户数据 schema、配置版本或词典；query/hash 与 UI 白名单保持原限制。运行中的旧候选不会自动更新，须重新安装隔离候选并重启。

2026-11-03 新增手动诊断字段 `ui.route.query: {known: [{key, value}], unknownKeys, truncated}`：仅输出 `m1-ui-audit.cjs` 预设的名称与固定枚举值，其他名称仅计数、其他值为 null；参数最多 16 对，原始 search 超过 2048 字符不解析。这些词表仅是假设性诊断分类，不表示已确认应用使用这些参数，更不代表生产路由授权。仍在 query/hash/未知路径情况下跳过 DOM，主进程重新校验并重建输出对象，不保存原始 URL。更新只影响用户触发的实验采样，必须由用户重新 launch 才生效。

受控关闭用户实测 `ui-c36ab68046dc98b29af973ae94ccfe47.json`（2026-11-02 22:08:39，Asia/Shanghai）：controlled-disabled、snapshots=17、authorizedSnapshots=16、translateCalls=0、providerCalls=0、preloadErrors=0；主路由无 query/hash，端口 60840。Automations 为英文，其他三个标签为内置中文。证明关闭模式下实际窗口保持连接、内置词典可用且未发起翻译请求。success／failure／disabled 三组实际证据齐全；这里只验证启动时关闭，运行中关闭及在途结果失效仍主要由无界面回归覆盖。

受控失败用户实测 `ui-9136282bfe79854e9313fbefa39f9f86.json`（2026-11-02 22:05:56，Asia/Shanghai）：controlled-failure、snapshots=10、authorizedSnapshots=9、translateCalls=1、providerCalls=1、preloadErrors=0；主路由无 query/hash。固定提供方被实际调用并按测试模式抛错后，Automations 保留英文，另外三个内置标签仍显示中文，用户截图与报告一致。该项通过；未调用外部 AI，disabled 零请求场景仍待下一轮用户验证。

定时器修复后的用户实测 `ui-50de7a6751d3cff460aa9c57f1c59cad.json`（2026-11-02 21:28:29，Asia/Shanghai）：controlled-success、snapshots=12、authorizedSnapshots=11、translateCalls=1、providerCalls=1、preloadErrors=0；路由 `/` 无 query/hash，端口 54914。报告与用户截图均确认“自动化（测试译文）”，其他三处为普通内置中文。实际页面的模拟未命中→IPC→主进程受控提供方→译文显示链路已跑通，提供方为本地固定响应函数，没有外部 AI 请求。下一步验证 failure／disabled，再处理导航边界及还原。

最新受控验证 `ui-ecb3103da8012bfd3927c8a57654bcf1.json`（2026-11-02 21:22:49，Asia/Shanghai）确认：未导航时根路由无 query/hash，四处标签结构与候选完全匹配，窗口授权 7 次，但 translateCalls/providerCalls 均为 0，只有“新建对话”为中文。该轮排除了 query 与选择器变化，仍未通过补译验收。

排查中复现一个浏览器定时器兼容缺陷：DOM 管线把原始 setTimeout/clearTimeout 放入普通对象后作为方法调用，严格检查接收者的浏览器定时器会拒绝执行，Node mock 未检查 this 因而漏报。新增生成 preload 回归先失败，再将默认定时器改为箭头包装的直接调用后通过。DOM／preload／手动诊断专项 53 项全部通过。这个修复仍需用户重装隔离候选后实测，不能单凭 mock 判定真实补译问题已解决。

- 动态兼容配置新增 `windowBinding: {kind: "antigravity-local-hub-v1", paths: [...]}`，与静态精确 URL 模式分开。
- `resourcesFiles` / `uiResources` 独立绑定外置服务文件；检查入口支持显式 `--resources-dir` / `--resource-file`，没有放宽路径越界约束。
- `policy.paths` 必须与动态窗口路径集合相同；动态规则必须指定 `sourceTexts` 固定英文标签。query/hash、未审核路径和白名单外标签不进入翻译管线。
- `registerHubWindow(win, url, preloadPath)` 由唯一且经过指纹审核的窗口工厂调用；任意相同本地 URL 的其他窗口不会因此获得授权。
- 安装时生成 `runtimeIntegrity`，启动时流式校验入口、preload、窗口模块、运行时及外置服务。异常时不启用 AI 桥接，仍尝试原应用启动。
- 测试助手 `capture` 写 `capture-request.json`：`{"schemaVersion":1,"id":"32位随机十六进制"}`。运行中的新包装器消费请求，生成 `.m1-lab/evidence/ui-<id>.json`。仅返回固定标签、结构、受限路由和安全开关，未知文本／路由值不出报告。
- 用户配置仍为原 schema1；本阶段不迁移词典、不引入 7 天候选、不改变现有真实 API 配置。

## 3. 验证命令、结果与未验证范围

### 最终服务恢复结论

2026-11-03 19:54:55.053（Asia/Shanghai），`ui-a8ad2d9da734111136c688d8e73d288d.json` 返回 status=ok、preloadErrors=0。与基线及重启回执保持相同 sessionId、appPid=28960 和 windowId=1；服务 generation=2、PID 121024、端口 53209，窗口也连接该端口。路由 `/` 无 query/hash，四个导航正文显示中文，包括“自动化（测试译文）”；snapshots=230、authorizedSnapshots=216、translateCalls=2、providerCalls=1。用户另确认主页和译文已恢复。**同一应用实例内一次受控服务终止后的重新授权与显示恢复通过，无需再次重启或重复采样。**

回执到最终采样相隔 231.829 秒，仅是采样时间间隔，不能称为实际恢复耗时。16.741 秒时的 no_eligible_window 保留为过渡证据，未记录具体排除原因；不能据此推断永久故障，也不从累计计数强行归因某次缓存命中。不外推为连续崩溃压力测试或真实 AI 请求验收。

### 最终无界面回归

收尾配置与 DOM 边界修复后的完整结果如下；下文历史数量保持各自时点。

| 检查 | 最终结果 |
| --- | --- |
| Python unittest | 181 项：178 通过、3 跳过、0 失败 |
| JavaScript node:test | 161 项：160 通过、1 跳过、0 失败 |
| 默认 registry 与原始样本 | 从原始归档提取 8 个相关文件至临时目录，使用实际外置服务指纹；无 profile mock 的 select_profile 与暂存注入通过，11 项 runtimeIntegrity 摘要一致 |
| 生成 JavaScript | preload、窗口模块和 bootstrap 的 Node 语法检查通过；没有执行应用 |
| Python 3.8 语法 | 8 份改动／新增 Python 文件通过 AST feature_version 检查；未宣称用 Python 3.8 解释器执行测试 |
| 文档与补丁 | 9 份 Markdown 的 57 个本地路径／锚点通过；阶段状态一致，git diff --check 通过 |

Python 跳过为 POSIX／Windows 符号链接权限条件，JS 跳过为 Windows 符号链接权限。完整测试仅用隔离 fixture 和本机 TLS／代理服务，不调用外部 AI；测试过程没有启动、停止或改动日常／实验安装。默认 registry 核验只写临时目录，结束后清理该临时目录。

### 实测过程与历史验证记录

第八轮首次真实服务重启：基线 `ui-b5a24d10520ad85021a40679652a39d3.json`（19:49:37.419，Asia/Shanghai）为正常受控主页，主程序 PID 28960、服务 generation=1／PID 95968／端口 60109。用户显式触发后，`service-restart-ea55e816b39535fdf019dc22f5ee0c51.json` 于 19:51:03.224 返回 signal_sent。恢复采样 `ui-c4c41b7b74c7adcfe87d57d4784d7b5d.json`（19:51:19.965，距信号 16.741 秒）保持同一 sessionId／appPid，服务 generation=2／PID 121024／端口 53209；preloadErrors=0，snapshots=145、authorizedSnapshots=133、translateCalls=1、providerCalls=1。但 status=no_eligible_window、windows=[]，该快照没有采到符合条件的窗口，不能单凭服务更换判定重连或译文恢复通过，也不能据此认定应用永久故障。用户随后确认主页和测试译文已恢复；仅需补采当前状态，核对窗口是否连接新服务，不再发重启请求。

2026-11-03 19:43:18（Asia/Shanghai）首份第八轮基线 `ui-0aefb81a0b202b3411258c0003586d70.json`：status=ok、controlled-success、preloadErrors=0，snapshots=11、authorizedSnapshots=10、translateCalls=1、providerCalls=1；路由 `/` 无 query/hash，四个导航正文显示预期中文，包含“自动化（测试译文）”。lifecycle 中 appPid=136772，服务 generation=1、pid=128052、port=63044，元数据已生效。随后只读核对发现两个 PID 和 launch.lock 均不存在，用户确认采样后已关闭应用或启动终端；未发布服务重启请求。此基线只能证明当时的正常启动，不能用于另一个会话的服务操作，也不构成服务恢复失败。继续时无需重装，只重新 launch、capture，并保持应用及启动终端运行。

本轮最新完整无界面回归：`python -X utf8 -B -m unittest discover -s tests` 共 177 项，174 通过、3 跳过；`node --test tests/js/*.test.cjs` 共 155 项，154 通过、1 跳过。Python 跳过为 POSIX／Windows 符号链接权限条件，JS 跳过为 Windows 符号链接权限；临时目录使用被忽略的 `.m1-lab-unit-tests`，JS 本机 TLS／代理 fixture 在获工具批准后于沙箱外运行，不调用外部 AI。新增测试覆盖请求和报告绑定、过期／非法输入、并发及失败清理、服务对象更换、主 PID／其他窗口拒绝、claim 先落盘、写入失败不延迟触发、重复请求及回执失败不重复操作、采样期间换服务不拼接报告。Python 3.8 语法检查和 `git diff --check` 通过；独立审阅未发现剩余阻塞问题。没有启动／停止真实应用或触发真实服务测试。

2026-11-03 19:32:14（Asia/Shanghai）重建后报告 `ui-60a7e4ac2540cf4c42453dddab4a2e1c.json`：status=ok、bridge.mode=not_installed，snapshots／authorizedSnapshots／translateCalls／providerCalls 及 preloadErrors 全部为 0；窗口端口 56368、路由 `/` 无 query/hash，四个导航正文标签 New Conversation／Automations／Customizations／Settings 均为英文，用户截图与报告一致。窗口安全开关正常。用户明确确认直接进入主页、无需重新登录。因此第七轮原始归档切换、解包重建后的启动／显示与登录保留通过；未启动纯 app.asar 布局，不将这两种启动混为一项。

第七轮用户继续执行明确指向隔离安装的 Patcher 和 `m1_bridge.py reset`，退出码均为 0，后者报告 pristine app rebuilt。只读复核布局回到 `app + app.asar.disabled + app.asar.unpacked`，无活动 `app.asar`、无 `.dragongirl`、无 launch.lock、无 `.antigravity-*` 临时目录；应用 2.28.2，入口 `dist/main.js`。归档哈希与还原前一致，归档／解包入口校验通过；`package.json`、`dist/main.js`、`dist/preload.js`、`dist/menu.js`、`dist/tray.js`、`dist/utils.js`、`dist/languageServer.js`、`dist/constants.js` 共 8 个文件与原始归档对应条目逐字节相同。解包重建及这些注入相关文件恢复通过，尚未启动本次重建副本或确认本轮登录保留。

第七轮用户手动还原：`Test-Path .m1-lab/launch.lock` 为 False，执行显式指向隔离安装的 `Restore.py --no-launch` 后退出码 0、报告归档恢复完成。随后只读核验 `resources/app.asar` 存在、`app.asar.disabled` 与 `app` 不存在、`app.asar.unpacked` 保留，无 `.antigravity-restore-*` 残留且 launch.lock 不存在。原始归档 1085 个条目、主入口 `dist/main.js` 和依赖校验通过，SHA-256 仍为 `046fa2ba9abe96bc915eb7ed12887c067396a8a12148842ab4f4e2cd05a68feb`，与还原前一致。原始归档布局切换和清理通过；重建解包副本后的启动及本轮登录保留仍待用户验证，未启动纯归档布局。

2026-11-03 19:22:12.775 至 19:22:28.991（Asia/Shanghai）设置页连续报告 `ui-5b49d034f6b829c3f60bb0b30df1394b.json` 与 `ui-6b723e7e37624d3c21e92e8fde263800.json`：同一窗口编号 1／端口 58221、controlled-success，间隔 16.216 秒，均 status=ok、preloadErrors=0，contextIsolation=true、sandbox=true、nodeIntegration=false。snapshots 从 14 增至 25；authorizedSnapshots 始终为 4，translateCalls 和 providerCalls 始终为 1。两次均为 `/`、hasQuery=true、hasHash=false、known=[]、unknownKeys=2、未截断；按策略跳过 DOM，matches=[]，rootFound=false 不表示真实页面没有 root。由此确认该设置停留区间状态轮询继续、没有新增授权或翻译／提供方调用，设置态来源边界通过。此证据不识别或放行未知参数，不外推为所有路由或在途导航场景均已真实验收；不需要重复已有显示恢复与工具关闭验证。

2026-11-03 19:18:57（Asia/Shanghai）报告 `ui-f4e69ab74a2e07225b4add09043bc12a.json`，用户确认采样于关闭 Settings 返回主页后。status=ok、controlled-success、端口 52349，snapshots=38、authorizedSnapshots=18、translateCalls=4、providerCalls=1、preloadErrors=0；路由 `/` 无 query/hash，四个导航正文为“新建对话／自动化（测试译文）／自定义／设置”，选择器仍与候选一致。非导航区域 New Conversation 的 aria-label 保持英文。只读核对安装副本 `.dragongirl/main.cjs` 与仓库源码 SHA-256 一致，preload 包含新 pageEpoch 校验与变化处理。用户进一步确认较快打开设置再关闭也正常恢复，本轮翻译设置工具一直关闭。因此正常及较快关闭后的显示恢复、当前受控翻译不依赖设置工具常驻已验证；未调用真实 AI。累计 4 次翻译入口、1 次受控提供方调用不足以精确归因其余调用，也不能单独证明设置页期间没有请求，仍需同一实例的设置页报告。

2026-11-03 19:10:46（Asia/Shanghai）设置页报告 `ui-2211288c16914480cf1109bd8b0de030.json` 为 status=ok、preloadErrors=0，路由 `/`、hasQuery=true、hasHash=false，query 为 known=[]、unknownKeys=2、truncated=false。按当前策略未检查 DOM，rootFound=false、matches=[] 不能解读为页面缺少 root。bridge.mode=not_installed，全部桥接计数为 0，窗口安全开关正常。用户确认通过关闭按钮返回主页。此报告端口 59161，上一份返回主页报告端口 57231，不能视为同一服务实例中的连续导航证据。

静态前端核对：隔离 `resources/bin/language_server.exe` 的内嵌 ZIP `main.js` 确认侧栏 Settings 使用 `settingsOpen=true`，另按上下文选择 `settingsScreen` 或 `settingsProjectId`；关闭弹窗移除相关设置参数。EXE SHA-256 为候选已有的 `a51a80eb1b355dc523dd9a6d7cec098ad450e3c9fb30d6001806cac86814f37b`；ZIP 本地头偏移 155946301、压缩数据偏移 155946338、压缩长度 3137065、解压长度 10652379；解压成员 SHA-256 为 `c3c5c9bb6d418e8d919cb94aa7de4df9ba449056b7d6122c32279ce72e2d2bad`。成员字节偏移约 10601736 为打开设置逻辑、4608050 为关闭处理。两项未知参数的具体名称尚无运行证据，不据此扩大诊断输出或生产许可。

无界面复现：在 query 路由期间重建导航文本并交付 childList 记录，关闭只移除弹窗，返回时配置／词典／缓存版本不变且轮询未观察到中间拒绝；修复前生成 preload 的短导航用例失败，返回后 Save 仍英文。新增授权代次后，该场景和跨轮询的 unauthorized 往返均通过。JS 专项 `node --test tests/js/bootstrap.test.cjs tests/js/runtime.test.cjs tests/js/preload.integration.test.cjs tests/js/dom.test.cjs tests/js/m1-harness.test.cjs` 共 105 项，104 通过、1 个 Windows 符号链接权限跳过；Python `test_translation_integration.py` 28 项（26 通过、2 跳过）、`test_m1*.py` 20 项全部通过，进程 TEMP/TMP 使用 `.m1-lab-unit-tests`。`git diff --check` 通过。该复现证明恢复边界缺陷，但尚未证明用户原操作具有完全相同的时序；正常恢复需等待下一次约 1500ms 轮询，仍需真实同一实例验收。

2026-11-03 19:08:33（Asia/Shanghai）新增报告 `ui-2f2f44e0a81929c7e48582482e995e45.json`，用户明确采样时已从设置返回主页。报告 status=ok，路由 `/`、hasQuery=false、hasHash=false，query 为 known=[]、unknownKeys=0、truncated=false，rootFound=true；四个导航正文标签 New Conversation／Automations／Customizations／Settings 均为英文。bridge.mode=not_installed，snapshots／authorizedSnapshots／translateCalls／providerCalls 及 preloadErrors 均为 0；contextIsolation=true、sandbox=true、nodeIntegration=false。此次使用撤回组件后的副本，不能据此验证翻译重绑定或宣布原回退问题已解决；此前带 query 报告的具体导航状态仍未确定。下一步只需补采 Settings 页面并确认返回方式。

用户补充确认：还原后无需重新登录，本轮 DragonGirl 翻译设置窗口一直关闭；此前英文回退操作为“进入主页 → 点击设置 → 返回主页”。此确认覆盖还原场景，不能外推为所有受控翻译测试期间设置工具均关闭。路由诊断新增 4 项测试覆盖固定词表、未知值脱敏、输入与数量上限、主进程报告过滤；`node --test tests/js/m1-ui-audit.test.cjs tests/js/m1-harness.test.cjs tests/js/bootstrap.test.cjs tests/js/preload.integration.test.cjs` 共 41 项通过，`git diff --check` 通过。无真实应用启动或 API 请求。

2026-11-03 18:51:35（Asia/Shanghai）用户还原后实测：`ui-c893c37ef4f6ed0617f78916a7aedac2.json`，status=ok，bridge.mode=not_installed；snapshots／authorizedSnapshots／translateCalls／providerCalls 均为 0，preloadErrors=0。目标窗口端口 56355（仅本次实例），contextIsolation=true、sandbox=true、nodeIntegration=false，路由 `/` 无 query/hash。四个导航正文标签 New Conversation／Automations／Customizations／Settings 全部为英文，截图与报告一致。由此确认 reset 撤回组件后可正常启动和显示；主界面可见不能独立证明期间没有重新登录，也不能证明设置工具关闭，二者等待用户补充。该报告未抓取聊天或输入内容。

此前完整无界面回归结果（Python 3.11.4 / Node v24.15.0；后续专项新增测试未全部计入，交审前需重跑完整回归）：

| 回归 | 总数 | 通过 | 跳过 | 失败 |
| --- | --- | --- | --- | --- |
| Python unittest | 155 | 152 | 3 | 0 |
| JavaScript node:test | 121 | 120 | 1 | 0 |

针对性验证还包括 Python 兼容策略 28 项（26 通过、2 跳过）、生成的 preload 集成 7 项、手动诊断 JavaScript mock 13 项、隔离助手 Python mock 11 项；这些已包含在完整总数中。`git diff --check` 通过。

上述完整回归后，本轮增加导航候选及手动安装入口：新增 Python 专项 3 项通过，更新后的 harness JavaScript 7 项通过（其中新增 1 项验证强制关闭 AI、空内存配置和拒绝提供商调用）。完整回归总数尚未重新统计；未执行真实安装或启动。

随后受控测试工具专项：`python -X utf8 -B -m unittest discover -s tests -p 'test_m1*.py'` 15 项通过；`node --test tests/js/m1-harness.test.cjs` 9 项通过。Python 默认沙箱临时目录的原子 rename 曾被拒绝，改用工作区 `.m1-lab-unit-tests` 后通过。实际服务逻辑在 mock 包装器中验证成功／失败／disabled 三模式，未连接网络。安装、启动和实际界面结果仍由用户执行反馈。

```powershell
python -X utf8 -B -m unittest discover -s tests
node --test tests/js/*.test.cjs
git diff --check
```

测试进程可将 TEMP/TMP 定向到被忽略的 `.m1-lab-unit-tests`，不修改系统环境变量。网络层测试仅使用本机 TLS／代理 fixture，无真实 AI 调用。Windows 符号链接权限及 POSIX 专用项目按测试条件跳过。

本轮 Python 首次完整运行曾有一个临时 fixture 重命名报 `WinError 5`，未改源码的完整复跑通过；根因未确认，不能声称已修复该环境问题。Node 沙箱内 10 项本机代理／TLS 连接失败，经工具审批在沙箱外运行相同隔离测试后通过；未连接外部 AI。专项和完整测试均未启动或查看真实应用。

已验证的真实范围为主路由 `/` 四个固定导航标签，及其中 Automations 的人为未命中受控请求／显示／失败保留英文／启动时关闭零请求；用户多次安装候选和重启成功，reset 撤回组件后已重新进入英文主界面。导航修复后正常及较快关闭设置返回主页均恢复译文，用户确认本轮翻译设置工具全程关闭；同实例设置页停留 16.216 秒期间无新增授权、翻译或提供方调用。Restore.py 归档布局恢复、内容完整性和清理，以及其后解包重建、启动与登录保留均通过。第八轮同实例服务恢复也已通过。真实 AI 页面补译、纯归档布局启动、其他页面／构建／平台以及连续服务故障未验证；运行中关闭 AI 和全部在途竞态的真机覆盖未完成，相关机制由无界面测试覆盖。安装包和 PySide6 管理器不属于 M1。

## 4. 使用方式、已知问题及恢复方法

第七轮归档恢复步骤见 [手动说明](../../tests/manual/README.md#第七轮原始归档恢复与隔离副本重建)。用户已完成 Restore→Patcher→helper reset；归档切换、内容／入口／依赖、哈希及解包重建均复核通过。当前已恢复 `resources/app`，可以继续用隔离包装器 `launch --allow-login --refresh-package --duration 1800` 启动。现有助手无法直接启动纯归档布局，因此这次重建后的启动不能替代纯 app.asar 布局启动验收；用户数据目录不参与安装布局操作。

2026-11-03（Asia/Shanghai）还原验证遇到启动器缺陷：用户 `reset` 已完成，随后带 `--refresh-package` 启动时因旧 `launch-package.json` 的 `.dragongirl/bootstrap.cjs` 已移除而报 WinError 3。只读核对当前 package.main 已为 `dist/main.js`，入口文件存在，launch.lock 不存在；失败发生在启动子进程之前。根因是刷新流程先验证旧入口存在，无法处理合法的组件移除。

修复后，旧备份仍需满足 JSON／main 格式及路径范围校验；只有复用旧备份或恢复包装器入口时才要求旧入口文件存在。显式刷新则先验证当前入口，再归档旧备份并保存当前 package。增加还原后刷新成功、未指定刷新拒绝、当前入口缺失／越界不得归档、包装器旧入口缺失拒绝、相同备份入口缺失拒绝共 5 项测试；修复前复现 2 项错误，修复后 `python -X utf8 -B -m unittest discover -s tests -p 'test_m1*.py'` 共 20 项通过（进程 TEMP/TMP 指向 `.m1-lab-unit-tests`）。未启动应用、未改动真实实验备份或登录数据。用户只需重试原 launch 命令，再 capture；还原后的界面与登录保留仍待实测。

failure 模式首次启动被遗留 `launch.lock` 阻止，尚未运行该验证。已只读核实宿主进程列表：锁记录的启动器 PID 137148、隔离应用 PID 107280 均不存在，亦未发现 Antigravity／language_server 进程；再次核对锁内容未变化后，仅把该锁归档到实验 evidence 目录，未启动或关闭应用。工具现明确提示先退出旧启动器，进程核实后才能处理遗留锁，不自动删除或抢占锁。

按照 [用户手动操作说明](../../tests/manual/README.md#本轮用户操作主界面结构采样) 操作。用户已要求今后所有实际应用启动、界面查看和真实 API 联调由自己完成；助手仅提供步骤和处理结果，继续做代码与无界面测试。

当前日常设置目录是 `%APPDATA%\Antigravity-zh-CN`；隔离副本的对应目录是 `.m1-lab/roaming/Antigravity-zh-CN`。目前不复制密钥、不要求重复配置；这一轮结构采样不会调用 AI。旧“自动保存”开关也不代表已实现 M2 的人工审核候选功能。

- 已在运行的旧包装器不会因仓库文件更新而自动更新，须由用户停止后重新 `launch`。不直接双击副本 EXE 绕过隔离包装器。
- 早期 `window-*.json/png` 可能含旧页面内容，留在被忽略的实验目录，不作为本轮反馈附件；新的包装器已取消自动整页和截图采集。
- 若请求待处理或没有报告，不反复提交；先反馈命令输出。未知路由、窗口不合格、服务未就绪会返回受限状态，不能据此放宽来源校验。
- `python -B tests/manual/m1_lab.py stop` 仅请求隔离副本退出，保留独立登录数据。候选安装后如需恢复，退出启动器并运行 `python -B tests/manual/m1_bridge.py reset`，使用原始归档按同一暂存／校验／切换流程重建未注入 app；再以 `--refresh-package` 启动。用户数据不变，日常安装不参与。

## 5. 用户审核内容

本阶段八轮用户操作已完成，手动说明保留供复现，不再要求重复采样。审核重点为四标签支持范围、严格窗口与路由绑定、受控响应与真实 AI 的区别，以及归档恢复与解包启动的区别。正式配置不含实验未命中分支；采用该配置重新汉化会收紧到四标签，不代表完整界面覆盖。

交审快照创建后，可运行以下只读命令检查；不推送、不合并、不发布。用户提出修改时仅返工 M1，创建新提交和递增标签，不覆盖已交付标签。

```powershell
git show --stat manager-v0.1.0-m1-review.1
git diff manager-v0.1.0-m0-review.1 manager-v0.1.0-m1-review.1 -- localization_runtime src/localization tests docs README.md README_EN.md PROJECT_STATUS.md .gitignore
git cat-file -t manager-v0.1.0-m1-review.1
git rev-parse 'manager-v0.1.0-m1-review.1^{commit}'
```

## 6. 接下来工作及进入条件

本阶段完成后停止，不再安排新的实际应用操作；本地快照交付供用户审核。

服务生命周期的静态依据：2.28.2 原始 `dist/languageServer.js` 约 358–414 行在服务非主动退出后自动重启（2 秒冷却、连续最多 3 次），`dist/main.js` 约 322–331 行通过 onPortChanged 将现有 Hub 窗口 loadURL 到新端口。`killLanguageServer()` 会标记主动退出，不能用于该测试；实验入口对已绑定实际 ChildProcess 的一次操作已由用户执行并验收。普通退出再启动不能替代这项证据。

完成阶段提交与 `manager-v0.1.0-m1-review.1` 后停止并等待用户审核。真实提供商调用若另行安排，仍须用户明确操作并单独记录，不把受控结果改写为真实 API 通过。

下一阶段 M2：内置词典抽离、个人覆盖、待确认目录、7 天清理、采纳／拒绝和旧数据迁移。**只有 M1 达成条件、交付并获用户明确批准后，才进入 M2。**
