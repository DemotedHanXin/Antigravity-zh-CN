# M2：词典与审核流程

日期：2026-11-03（Asia/Shanghai）。分支：`feat/DragonGirl`；起点：M1 提交 `3435cbaf6c215e7eab8957cbc0c5aabb79a33e3f`。用户已明确审核通过 M1 并要求继续 M2。**M2 已完成，待用户审核；M3 未开始。** 本地交审标签：`manager-v0.1.0-m2-review.1`；实际提交 SHA 在交付消息中报告。

## 1. 阶段目标及实际完成内容

已实现个人词典 → 内置词典／规则 → 有效待确认译文 → AI 的统一优先级，保留英文原文和译文来源；内置精确数据独立维护。候选首次生成后保留 7 × 24 小时，复用不续期；采纳进入个人词典，拒绝持续抑制直到用户解除。有效候选在 AI 关闭时也可复用，关闭 AI 只禁止新请求。组件及设置工具在启动／读取时与每 60 秒清理，DOM 另按最近候选期限撤回显示；两者都退出时无后台清理服务。

内置数据从 M1 的实际 JS 定义提取：683 次精确词典定义合并为 676 个有效键，保留 7 个重复键的最后值；另有 70 个核心词、106 条有序前缀规则、36 个菜单词条。四组摘要、重复值和代表性输出固化在 [基线 fixture](../../tests/fixtures/builtin-baseline.json)。正则及匹配函数保留为代码，原静态行为回归通过。

保留 M1 的四标签、窗口和页面安全边界。实际应用、界面及真实 API 操作仍由用户手动完成；本轮源码和测试不读写日常配置或安装。不实施 M3 的 PySide6 管理器、密钥保护或 M4 安装包。

## 2. 主要实现、接口及数据格式变化

已实现的共享协议：

- `config.json`、`personal-dictionary.json` 升级 schemaVersion=2；旧运行时拒绝新格式。旧 autoSave 迁移为 false 的弃用字段，新 AI 结果全部进入候选。
- 保留旧手工词条；旧 AI 词条标记 `legacy-ai`，含义为历史保存、未人工审核，不转移到候选中自动过期。新采纳条目标记 `accepted`。
- `pending-translations/state.json` 保存候选 entries、独立 rejected 记录与每原文 epochs。候选时间为整数 UTC 毫秒 `createdAt`、`expiresAt`，后者等于前者加 604800000；`now >= expiresAt` 视为过期。
- 多文件更新在 `.translation.lock` 下，通过固定路径的 `.translation-journal.json` 保存完整待提交状态，故障恢复后继续提交；无效 journal 不猜测、不覆盖。锁不自动抢占，进程异常退出留下锁仍须核实后处理。
- Node Store.read() 与 Python UserStore.read_state() 返回 `{config,dictionary,candidates}`，一致读取前恢复事务、迁移并清理到期项。运行时持久化候选使用配置／词典版本与原文 epoch，拒绝过期、拒绝或人工修改前发出的旧响应。
- IPC snapshot 增加 candidatesRevision、候选及拒绝状态；成功落盘后刷新快照，由 DOM 的候选层显示，不让旧请求跨越审核版本直接写界面。候选版本参与旧显示／请求失效。
- `translation_service.py` 提供不含凭据的结构化词典和审核接口；`Translation-Dictionary.py` 为命令行入口。旧 Tkinter 工具停止展示已废弃的自动保存开关，统一图形审核页留给 M3。

同一提供方／模型下，相同原文跨不同安全 context 也共用一次生成和一个候选，首次请求提供 context。保存多个不同原文不因其他候选的新建而互相取消；人工操作、拒绝、解除及到期则推进原文 epoch，使旧结果无权恢复。

时间在取得锁后和实际审核／复用决定前重新核对，避免候选在排队或读取 I/O 期间到期却被采纳。时间倒退时未来候选不显示、不重复请求，时钟恢复后可重新显示且不延长原期限。两侧严格拒绝损坏 UTF-8、非有限 JSON 数值及不兼容 schema，原文键采用相同边缘空白规则；候选／拒绝／epoch 的来源并集最多 10000，避免清理本身溢出。单文件最多 4 MiB，恢复 journal 最多 16 MiB；超限拒绝，不静默截断。

纯定时清理不推进 Tk 编辑草稿的词典版本；外部编辑后保存旧草稿仍报冲突，需要用户显式刷新。CLI 和后续 GUI 共用 `DictionaryService.execute()` 的结构化结果，成功为 `ok:true`，失败包含固定 code 和脱敏 message；不会导出提供商配置或密钥。

## 3. 验证命令、结果、跳过项及未验证范围

最终验证：

| 检查 | 结果 |
| --- | --- |
| 完整 Python unittest | 218 项：214 通过、4 跳过、0 失败 |
| 完整 JavaScript node:test | 194 项：193 通过、1 跳过、0 失败 |
| 最终小改专项 | UTF-8/BOM 最后收紧后 Node 存储 14 项通过；M1 审核元数据更新后兼容专项 32 项（30 通过、2 跳过） |
| 内置提取 | 12 项数据／行为一致性测试，包含冻结资源定位、缺失资源、重复键及旧 JS 输出 |
| 原始样本离线注入 | 从 M1 原始归档只读提取 8 个相关文件到临时目录，默认 registry 识别通过；M2 注入生成的 preload／窗口模块／bootstrap 语法正确，11 项 runtimeIntegrity 摘要一致 |
| Python 3.8 语法 | 12 份改动或新增 Python 文件通过 AST feature_version 检查；不代表使用 3.8 解释器执行过 |
| 独立审阅 | 过期采纳、UTF-8 保留、空白规则、来源容量、跨语言事务及运行时回调复核通过，无剩余阻塞项 |
| 文档与补丁 | 7 份 Markdown 的 64 个本地路径／锚点通过，git diff --check 通过 |

新增测试覆盖实际生成 preload、覆盖／恢复默认、候选跨启动复用、7 天等号边界、休眠跨期、到期采纳、拒绝／解除时在途响应、不同来源并发保存、跨 context 同原文去重、事务中断恢复、Python／Node 双向迁移及旧运行时拒绝新格式。读取陷阱继续验证 M1 白名单外不采集边界。

```powershell
$m2TestTemp = Join-Path (Get-Location).Path '.m2-lab-unit-tests'
New-Item -ItemType Directory -Path $m2TestTemp -Force | Out-Null
$env:TEMP = $m2TestTemp
$env:TMP = $m2TestTemp
python -X utf8 -B -m unittest discover -s tests
node --test --test-reporter=spec tests/js/*.test.cjs
git diff --check
```

测试只使用工作区临时用户目录、虚拟密钥和本机网络 fixture，不启动真实应用或调用外部 AI。Node 的本机 TLS／代理测试经工具批准运行；TEMP/TMP 只设置于测试进程。Python 跳过为 POSIX 权限及三项 Windows 符号链接权限条件；JS 一项 Windows 符号链接条件跳过。

本阶段未重新安装或启动实际 Antigravity，未迁移日常数据、验证真实 AI、查看原生 GUI 或构建冻结包。M2 的界面更新证据来自实际生成 preload 的 VM／DOM 回归，应用来源和四标签结构沿用已获批准的 M1 实测；不将这两类证据混为新的真机验收。机器断电、磁盘硬件故障和所有文件系统行为未实测，不承诺断电级原子回滚。

## 4. 使用方式、已知问题及恢复方法

命令行入口位于 `src/localization/Translation-Dictionary.py`；提供 list、pending、set、restore-default、accept、reject、unblock、cleanup。默认使用当前用户目录，可显式传入 `--data-dir` 指定实验目录。版本敏感写入必须提供刚读取的 revision。工具不会调用 AI；解除拒绝只改变许可，是否后续补译由运行中的翻译组件决定。

本阶段未执行真实用户数据迁移。升级后的源程序首次读取旧数据时将迁移，不能把源码 Git 回退当作用户数据降级；旧运行时对 schema2 暂停增强翻译，不覆盖文件。部署时应同时更新应用内组件与管理工具，本次没有自动部署。

以下示例从仓库根目录操作独立 `.m2-lab/review`，无需应用或 API：

```powershell
$m2Cli = 'src/localization/Translation-Dictionary.py'
$m2Data = '.m2-lab/review'
$view = python -B $m2Cli --data-dir $m2Data list --query 'New Conversation' | ConvertFrom-Json
python -B $m2Cli --data-dir $m2Data set --source 'New Conversation' --translation '我的新对话' --revision $view.dictionaryRevision
python -B $m2Cli --data-dir $m2Data list --query 'New Conversation'
$view = python -B $m2Cli --data-dir $m2Data list --query 'New Conversation' | ConvertFrom-Json
python -B $m2Cli --data-dir $m2Data restore-default --source 'New Conversation' --revision $view.dictionaryRevision
python -B $m2Cli --data-dir $m2Data pending
```

有候选时，先运行 pending 获取 `candidatesRevision` 和原文；用 accept／reject／unblock 的 `--source` 与 `--revision` 执行审核。候选已经到期、被删除或列表版本变更时拒绝采纳；不要沿用旧版本号覆盖。CLI 不提供伪造候选或跳过期限的生产开关，七天及并发场景可运行 `tests/test_m2_storage.py`、`tests/js/m2-storage.test.cjs` 和 DOM／preload 测试复核。

恢复 journal 落盘之前失败，不修改目标状态；落盘之后失败，可能已完成部分文件，下一次取得共用锁后继续提交同一状态。遇到错误先重新读取，不将“命令报错”解释为全部撤销，也不删除 journal。进程异常退出留下的锁不自动抢占；核实进程和文件状态后再处理。缺失、损坏或未知格式数据不会自动重建覆盖。

## 5. 用户审核内容

审核：内置提取是否保持旧词条、个人覆盖与恢复默认、候选七天固定期限、持久拒绝、历史 AI 保留标记、并发和故障恢复，以及结构化 CLI 使用步骤。交付本地提交及 `manager-v0.1.0-m2-review.1`；不推送、不合并、不发布。

```powershell
git show --stat manager-v0.1.0-m2-review.1
git diff manager-v0.1.0-m1-review.1 manager-v0.1.0-m2-review.1
git cat-file -t manager-v0.1.0-m2-review.1
git rev-parse 'manager-v0.1.0-m2-review.1^{commit}'
```

标签表示供审核的快照，不表示用户已批准或发布。返工使用新的 commit 和递增 review 标签，不覆盖本次标签。

## 6. 下一阶段待办及进入条件

M3：统一 PySide6 管理器、共享服务界面、后台任务、准确状态和 Windows 用户绑定密钥保护。只有 M2 完成并获得用户明确审核通过后开始。
