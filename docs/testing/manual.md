# M1 隔离应用验收助手

这些文件仅用于开发验收，不随翻译运行时发布。只对工作区直接子目录 `.m1-lab` 或 `.m1-lab-*` 操作；不得将真实安装作为写入目标。这些实验目录均已被 Git 忽略，不能提交安装副本、用户数据或原始证据。

**操作约定：应用启动、界面操作和真实 API 联调由用户手动完成。助手负责准备命令、修改代码和无界面隔离测试。**

**2026-11-03 验收状态：下述八轮用户操作已完成，命令保留供复现，无需重复执行。** 第八轮最终报告 `ui-a8ad2d9da734111136c688d8e73d288d.json` 已确认同一应用／窗口连接到新服务并恢复测试译文。当前结论、支持范围和未验证项见 [M1 阶段记录](../development/M1-real-integration.md)。各轮中的“下一步／待验证”描述保留当时步骤语境。

正式 registry 已有受限的 2.28.2 四导航标签配置；实验候选仍保留 `isolated-lab-only` 和逐次运行验证标记，防止把实验安装当作生产部署。实验包装器只接受实验 profile，不要用正式 Patcher 代替下面的 `m1_bridge.py install` 后直接启动包装器。第七轮的 Patcher 重建之后必须继续 helper reset 才能启动该包装器。

从仓库根目录运行：

```powershell
# 只读验证原始归档和 x64 EXE，从安装文件创建新的隔离解包副本。
# 已存在 install 时拒绝覆盖；部分失败目录保留，选择新的 lab 重试。
python -B tests/manual/m1_lab.py prepare --source "$env:LOCALAPPDATA\Programs\antigravity"

# 启动隔离副本，保持父进程等待，60 秒后请求正常退出。
python -B tests/manual/m1_lab.py launch --duration 60

# 仅在用户明确选择亲自登录隔离副本时：允许登录所需外部连接。
# 等待期间由用户操作账号界面；此助手不会提交登录或真实 AI 请求。
python -B tests/manual/m1_lab.py launch --allow-login --duration 600

# 可从另一终端请求停止；此命令只写隔离目录的 stop 标记。
python -B tests/manual/m1_lab.py stop

# 用户明确触发固定界面标签结构采样；不启动应用，不调用 AI。
python -B tests/manual/m1_lab.py capture
```

`prepare` 排除已有解包 app、代理启动器和卸载器，从已验证的原始归档重新解包 app；保留副本的 `app.asar.disabled` 和完整外置依赖。它不复制用户 AppData、`.gemini` 或 API 配置。

`launch` 将 `m1-entry.cjs` 和 `m1-ui-audit.cjs` 复制到隔离 app，保存当前实际入口到 `launch-package.json`，再临时更改副本 package 的 main。包装层开始执行时会恢复 package 原始字节；若实际入口已经是翻译 bootstrap，则显式调用其 launch，避免 require.main 指向测试包装器导致漏启动。若之前失败导致 main 仍为包装层，只在完整原始备份存在且其他 package 字段一致时允许重试。

后续对副本安装／还原翻译组件可能改变 package。请先确认改动，再用 `launch --refresh-package`；旧备份会保存到 `package-backups/`，不会被静默丢弃。没有有效备份时不猜测原入口。

进程仅继承必要 Windows 系统变量和系统 PATH，HOME／USERPROFILE／APPDATA／LOCALAPPDATA／TEMP／TMP 等全部指向实验目录；不继承开发 URL、WSL、headless、Electron-as-Node、代理或凭据变量。独立 app_storage 关闭自动更新和后台驻留，并跳过 IDE 迁移向导。Electron 路径隔离、阻止协议注册、更新副作用与浏览器外部请求由同目录包装层完成；这不等于操作系统沙箱，也不保证原生 LS 不尝试外网连接。

默认不允许用户登录所需的浏览器外网请求。`--allow-login` 仅在用户明确授权并亲自操作登录时启用，设置 `ANTIGRAVITY_M1_LOGIN=1` 供包装层放行会话外网连接，仍阻止协议注册和更新安装。该模式通过 `urllib.request.getproxies_registry()` 读取 Windows 当前用户手动 HTTP 代理，给子进程设置相应 HTTP_PROXY／HTTPS_PROXY；无手动代理时直连。PAC、自动代理发现、带认证信息或其他不支持的代理会明确报错，不输出完整代理地址。两种模式均设置 NO_PROXY／no_proxy 绕过 `127.0.0.1,localhost,::1`，防止本地界面服务误走代理。

登录模式不采集原生进程的 stdout／stderr，避免复制登录 URL 或令牌到助手证据日志；程序自身在隔离用户目录生成的日志仍须按账号数据保护，不应读取或展示其中凭据。

父进程保持等待以免任务容器回收子进程；日志写入 `evidence/launch-*.log`。到期或 Ctrl+C 先写 stop 标记，等待 30 秒；若包装层未能退出，仅终止本次创建且仍运行的进程及其子树，并以失败返回。不会按进程名称关闭日常 Antigravity。`launch.lock` 防止同一实验目录并发启动；异常中止遗留锁时须先确认相应进程退出，再手动处理锁。

首次空白环境可能仅显示登录／引导页，不能用该页面的结果声称完整工作界面已验收。用户手工登录授权与受控翻译测试是两项独立操作；允许登录不授权助手提交账号信息、读取登录令牌或调用真实 AI。日志和证据可能含隔离账号信息，应留在被忽略的实验目录内，不向终端输出登录令牌或提交到 Git。静态安装检查、受控响应、原始界面和真实提供商结果应分开记录。

## 本轮用户操作：主界面结构采样

当前已确认用户能打开主界面且固定文案 API 测试成功。本轮只检查固定界面标签及其结构，不安装翻译组件、不调用 AI、不要求密钥或完整聊天内容。

1. 如果旧隔离副本仍在运行，在其启动终端按 Ctrl+C，等待退出；或从仓库根目录运行上面的 `stop` 命令，等待原终端显示退出。不要重新 prepare，也不要直接双击副本 EXE。
2. 在 PowerShell 中重启，使用本轮的新包装器，保持此终端打开：

   ```powershell
   Set-Location 'D:\Python\Python_Code_Set\Antigravity-zh-CN'
   python -B tests/manual/m1_lab.py launch --allow-login --duration 1800
   ```

3. 进入截图所示的空白主界面；需要时由你手动登录。保持左侧导航可见，本轮无需打开项目或输入聊天。
4. 另开 PowerShell，执行：

   ```powershell
   Set-Location 'D:\Python\Python_Code_Set\Antigravity-zh-CN'
   python -B tests/manual/m1_lab.py capture
   ```

5. 命令立即打印预期报告路径；**排队成功不代表采样成功**。运行中的新包装器通常在数秒内生成 `.m1-lab/evidence/ui-<id>.json`。反馈命令输出及该文件名即可，助手可在工作区读取这份限定报告；不要发送 `config.json`、登录日志或旧 `window-*.json/png`。需要时可自行打开新的 JSON 查看。

预期结果：报告 `status` 为 `ok`，`windows[].ui.matches` 出现上述固定导航标签，安全开关为 contextIsolation=true、sandbox=true、nodeIntegration=false；Electron 44 中 preloadReported=false 可能正常。`ok` 只表示诊断执行成功，matches 为空、route.path=null 或 hasQuery/hasHash=true 仍不能形成兼容结论。此时请返回报告，不要自行放宽白名单。

若 10 秒后仍没有结果，反馈打印的路径和启动终端状态，不必反复 capture 或删除锁。完成后可 Ctrl+C／stop 正常退出；独立登录数据会保留。

## 诊断采样范围

启动和页面加载不自动采样。只有 `capture-request.json` 中的显式请求才会触发采样；请求独占、完整发布，已有请求和报告不覆盖。诊断只对副本实际语言服务的本地 HTTPS 窗口工作，验证安全开关和服务进程。

允许标签仅为 `New Conversation`、`Automations`、`Customizations`、`Projects`、`Settings` 和三个固定登录按钮标签。返回标签的结构路径、有限 role、受限路由、安全开关与错误计数；不返回任意属性值、元素 ID、CSS 类、输入值、整页文本／HTML或截图。聊天、代码、输入框、终端、内嵌网页等区域在读取文本前排除，未知标签丢弃；渲染进程返回值还会再次验证并重建字段。

后续受控验证还允许五个固定中文显示值“新建对话／自动化／自动化（测试译文）／自定义／设置”，用于区分内置命中和受控译文；其余中文同样丢弃。早期报告没有这五个值，翻译后可能只剩非翻译区域的英文属性。

路径只返回预设固定路径；其他路径返回 null，query/hash 只返回是否存在，不返回值，也不采样其内容。这是用于发现首批固定 UI 的开发工具，不是自动生成兼容配置的工具。

现有设置工具默认读写 `%APPDATA%\Antigravity-zh-CN`，隔离副本读写 `.m1-lab/roaming/Antigravity-zh-CN`。这轮不复制真实 API 配置；是否打开设置工具不影响采样。

## 第二轮：导航桥接候选验证

首轮已确认主路由 `/` 和四个导航正文标签。本轮使用仓库内固定的实验候选，通过原生产安装器的暂存、校验、切换及回滚流程安装到 `.m1-lab/install`，不写入正式兼容 registry。

1. 在启动终端按 Ctrl+C，并等待退出信息。`launch.lock` 仍存在时安装命令拒绝执行，不手工删除锁。
2. 在仓库根目录运行安装，成功后再启动：

   ```powershell
   python -B tests/manual/m1_bridge.py install
   python -B tests/manual/m1_lab.py launch --allow-login --refresh-package --duration 1800
   ```

   首条命令若报错，请停止后续步骤并反馈输出。`--refresh-package` 将原启动入口备份归档，再记录新的桥接入口。此候选不用于日常安装或分发。
3. 进入空白主界面，检查左侧四处是否变为“新建对话／自动化／自定义／设置”。可关闭 DragonGirl 设置窗口，再确认这些标签仍显示中文；不要把这项检查当作 AI 翻译成功，四处目前均为内置词典命中。
4. 另开终端进入仓库，运行 `python -B tests/manual/m1_lab.py capture`，等待报告生成。反馈安装／启动命令输出、四处显示情况和新的 `ui-*.json` 文件名。

此模式由测试包装器强制提供 disabled 的空内存配置，拒绝提供商调用，不读取或修改真实／隔离 API 配置。报告应包含 `bridge.mode = navigation-only-ai-disabled`、`bridge.authorizedSnapshots > 0`、`bridge.translateCalls = 0` 和 `preloadErrors = 0`。如果标签已变中文，原英文限定采样的 matches 为空是正常现象；仍需报告证明 IPC 授权成功。

如需恢复：先退出启动器，运行 `python -B tests/manual/m1_bridge.py reset`。它从原始归档重建不含注入的解包 app，保留登录数据；通用安装器可能输出“汉化”字样，但最后的 `pristine app rebuilt` 表示这次跳过全部注入。随后用上述带 `--refresh-package` 的启动命令重启。不要删除原始 `app.asar.disabled` 或用户数据。

待本轮结果确认后，再安排未命中词条的受控响应与失败还原测试；真实 AI 调用另给用户操作步骤。

## 第三轮：受控未命中测试

第二轮已确认四处中文和实际窗口 IPC 授权。本轮只在实验副本对 `Automations` 绕过同步词典命中，令其进入异步补译链路。源码词典、正式 registry 和其他标签不变。提供方是内存中的固定响应函数，不连接真实 API、不读磁盘密钥、不保存译文。固定译文不是 AI 生成结果。

先在运行终端 Ctrl+C，等待退出。下面均使用绝对路径，可在任意 PowerShell 工作目录执行：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_bridge.py" install --controlled
```

仅在安装成功后运行：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_lab.py" launch --allow-login --refresh-package --translation-test success --duration 1800
```

主界面预期显示“自动化（测试译文）”，另外三处仍为普通内置中文。可关闭翻译设置工具后再次观察。保持应用运行，在另一终端采样：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_lab.py" capture
```

反馈标签显示和报告文件名。预期 bridge.mode=controlled-success、authorizedSnapshots>0、translateCalls>0、providerCalls>0、preloadErrors=0。计数证明经过异步服务；固定响应未经过实际 API 网络层。

成功模式确认后，用同一安装分别验证失败和禁用：每次先退出当前启动器，把启动命令中的 `--translation-test success` 改成 `--translation-test failure` 或 `--translation-test disabled` 再运行，随后 capture。无需重新安装。

| 模式 | Automations 预期显示 | 预期提供方计数 |
| --- | --- | --- |
| success | 自动化（测试译文） | providerCalls > 0 |
| failure | Automations，保留英文 | providerCalls > 0，可受冷却控制重试 |
| disabled | Automations，保留英文 | translateCalls = 0、providerCalls = 0 |

每次启动计数重置，失败／禁用恢复验证目前是重启场景，不能替代运行中关闭及在途响应失效验收。回到普通导航候选可退出后重新运行不带 `--controlled` 的 install，再按第二轮命令启动；回到完全未注入的隔离副本用 reset。所有切换均需等旧启动器退出。

## 第四轮：隔离副本还原验证

本轮启动／显示已由用户于 2026-11-03 完成：`ui-c893c37ef4f6ed0617f78916a7aedac2.json` 确认四个导航标签英文、bridge.mode=not_installed、全部桥接计数和 preloadErrors 为 0。以下步骤保留供复现，当前无需重复执行；是否无需重新登录、设置窗口是否关闭仍待用户确认。

受控 success／failure／disabled 三轮已确认。现在验证退出实验翻译组件后，原应用可继续启动，登录数据保留。保持翻译设置窗口关闭，在启动终端 Ctrl+C，等待退出信息，再执行：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_bridge.py" reset
```

成功后启动：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_lab.py" launch --allow-login --refresh-package --duration 1800
```

主界面停留 5 秒，在另一终端采样：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_lab.py" capture
```

预期四个导航标签均恢复英文，bridge.mode=not_installed，所有桥接计数为 0，preloadErrors=0。反馈 reset 输出及报告文件名，同时确认本轮是否保持设置窗口关闭、是否仍保留登录状态。任一步报错则停在该步。

2026-11-03 已修复旧启动器在 reset 后错误检查历史 `.dragongirl/bootstrap.cjs` 的问题。若此前 reset 已成功、launch 报该路径的 WinError 3，使用更新后的脚本直接重试上面的 `launch --allow-login --refresh-package --duration 1800`，无需重复 reset 或手工删除 `launch-package.json`。刷新会验证当前入口并保留旧备份到 `package-backups`；仍指向包装器但原入口缺失时会拒绝启动，不猜测入口。

这个 reset 使用原始归档和生产暂存／校验／切换流程重建未注入的解包 app，并移除 app 内的 .dragongirl 目录；保留实验用户数据和原始 app.asar.disabled。它验证实验注入的完整撤回，不等同于验证 Restore.py 切回 app.asar 的归档布局。后者及带参数路由仍是单独的验证事项，不能从本轮结果推断完成。

## 第五轮：设置导航的有限路由诊断

用户已确认第四轮无需重新登录、设置工具一直关闭。此前英文回退的触发顺序是“主页 → 设置 → 返回主页”。这轮继续使用已 reset 的英文副本，仅识别导航路由，不安装组件、不调用 AI。

1. 在旧启动终端按 Ctrl+C，等退出完成；如果已经退出，直接进行下一步。
2. 重新启动以加载更新的诊断模块：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_lab.py" launch --allow-login --refresh-package --duration 1800
```

3. 点击左下角 Settings，停留在设置界面，在另一终端运行下面的 capture；等该 JSON 文件生成后再继续操作（通常数秒）。记下这个“设置页”的报告路径。
4. 按此前的方式返回主页，再运行一次相同的 capture；记下“返回主页”的报告路径，并说明是点关闭、返回箭头还是其他入口返回的。

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_lab.py" capture
```

只反馈两个报告路径及返回操作，不需要复制完整网址或参数值。新版报告仅记录固定词表中的参数名／枚举值，未知名称只计数、未知值为 null；仍不采集带 query/hash 页面的 DOM。若参数不在诊断词表内，报告会如实保留未知计数，不将其视为已支持。生产桥接与 DOM 路由限制未改变。

## 第六轮：关闭设置后的翻译恢复

第五轮已确认设置页为带 query 的根路由，返回主页无 query，用户通过关闭按钮返回。两份报告来自不同端口，尚未验证同一实例的完整往返。源码现已修复短导航时漏掉重扫的问题；本轮由用户安装并验证修复，仍只使用本地固定响应，不读取真实 API 配置。

1. 全程关闭 DragonGirl 翻译设置工具。在旧隔离启动终端按 Ctrl+C，等待退出完成、PowerShell 提示符恢复；若已退出，直接继续。遇到遗留锁时反馈报错，不盲目删除。
2. 安装新版隔离受控候选：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_bridge.py" install --controlled
```

3. 安装成功后启动，保持该终端打开：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_lab.py" launch --allow-login --refresh-package --duration 1800 --translation-test success
```

4. 本轮中途不要重启或重装。以下三个状态各等待约 3 秒，在另一终端执行一次 capture，并等报告生成后再继续：
   - 初始主页：应显示“自动化（测试译文）”及其他三个内置中文标签。
   - 点击“设置”，停留在设置面板：此状态仍不采集 DOM、不补译设置内容。
   - 点击关闭按钮返回主页：约 3 秒后应重新显示“自动化（测试译文）”及其他三个内置中文标签。

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_lab.py" capture
```

5. 再较快地打开设置并点击关闭按钮，不在设置页等待或采样；返回后等待约 3 秒，确认中文同样恢复。若未恢复，再 capture 一次并反馈，不反复安装。

反馈三个报告路径（按初始主页／设置页／返回主页标明）、正常及较快关闭后是否恢复译文，并确认翻译设置工具全程关闭。报告应保持同一窗口／服务端口、controlled-success 模式和零 preload 错误；设置页跳过 DOM，返回后恢复允许的根路由。提供方调用可能复用会话缓存，不要求每次返回都新增调用。该结果仍不代替真实 AI 提供方、服务重启或 Restore.py 归档布局验收。

## 第七轮：原始归档恢复与隔离副本重建

第六轮导航恢复、设置工具关闭时运行、设置页连续停留零新增请求均已通过。本轮验证 `Restore.py` 将隔离安装切回原始 `app.asar`；后续再重建可由现有包装器启动的解包副本。所有命令明确指定 `.m1-lab/install`，实际操作仍由用户执行，每步成功后才继续。

2026-11-03 只读预检已验证原始归档全部条目、入口和 unpacked 依赖；`app.asar.disabled` SHA-256 为 `046fa2ba9abe96bc915eb7ed12887c067396a8a12148842ab4f4e2cd05a68feb`。这不是还原执行结果。

1. 在原隔离启动终端按 Ctrl+C，等待退出完成、PowerShell 提示符恢复。必要时可从另一个终端运行 `m1_lab.py stop` 请求退出。检查锁应为 False；若仍存在，反馈报错，不盲目删除或继续：

```powershell
Test-Path -LiteralPath "D:\Python\Python_Code_Set\Antigravity-zh-CN\.m1-lab\launch.lock"
```

2. 切回原始归档，不自动启动：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\src\localization\Restore.py" --app-dir "D:\Python\Python_Code_Set\Antigravity-zh-CN\.m1-lab\install" --no-launch
$LASTEXITCODE
```

预期退出码 0，提示原版归档已恢复。此时先反馈输出，由助手只读核验 `app.asar` 存在且哈希不变、`app.asar.disabled` 和 `app` 不存在、`app.asar.unpacked` 保留、无残留恢复目录。退出码 1 或 2 时停止反馈；2 表示归档已就位但清理未完成。

3. 归档布局核验后，恢复现有隔离助手需要的解包目录。现有 `m1_lab.installation()` 要求 `resources/app` 存在，所以此时不能直接运行 `m1_bridge.py reset`。先运行明确指向隔离安装的 Patcher，再由 helper reset 去掉词典注入，两步均不会启动应用：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\src\localization\Antigravity-Patcher.py" --app-dir "D:\Python\Python_Code_Set\Antigravity-zh-CN\.m1-lab\install" --no-launch
$LASTEXITCODE
```

仅在上一步退出码为 0 时继续：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_bridge.py" reset
$LASTEXITCODE
```

预期退出码 0、提示 pristine app rebuilt；布局回到 `app + app.asar.disabled + app.asar.unpacked`。翻译配置和隔离登录目录不在操作范围内。

4. 仅通过现有包装器启动并采样，确认英文导航及登录保留：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_lab.py" launch --allow-login --refresh-package --duration 1800
```

在另一终端：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_lab.py" capture
```

本轮证明归档布局恢复与之后重建隔离解包副本的启动；现有包装器不支持纯 `app.asar` 布局的实际启动，不把这两项混为一项。不要直接双击副本 EXE 绕过路径隔离。

## 第八轮：同一应用实例内的服务恢复

第七轮已通过，用户确认重建后直接进入英文主页、无需重新登录。本轮验证同一 Electron 主进程内，语言服务退出后原应用自动重启服务，翻译组件重新绑定并恢复译文。`restart-service` 会由实验包装器主动向当前隔离语言服务子进程发送一次 SIGTERM；页面可能短暂断开。命令只允许受控成功模式，每个应用会话最多一次尝试，不调用真实 AI。

1. 在当前隔离启动终端 Ctrl+C 并等待退出。安装受控候选，再启动新版包装器（它会复制新增的服务测试模块）。安装失败时反馈输出，不继续启动：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_bridge.py" install --controlled
```

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_lab.py" launch --allow-login --refresh-package --duration 1800 --translation-test success
```

2. 主页显示“自动化（测试译文）”后，在另一终端 capture 并等待报告生成。保持主窗口在主页；采样之后也必须保持隔离应用和启动它的 PowerShell 终端运行，直到本轮验证结束。本轮中途不重启应用或打开设置：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_lab.py" capture
```

新报告包含 `lifecycle.sessionId`、`appPid` 和服务 `generation/pid/port`，不含用户内容或原始 URL。报告须为当前实例、5 分钟内、已授权的 controlled-success 主页报告；旧报告不满足要求。可以先把报告路径发给助手核对，再获取替换好路径的下一条命令；等待回复期间也保持应用和启动终端运行。若已经关闭，无需重新安装，但必须重新 launch 和 capture，不能复用上次会话报告。

3. 将下面占位文字替换为刚生成报告的完整绝对路径，显式请求一次受控服务重启：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_lab.py" restart-service --from-report "<刚生成的 ui 报告绝对路径>"
```

CLI 本身仅排他发布请求；运行中的包装器重新核验会话、服务对象／代次／PID／端口、实际 Hub 窗口、安全开关和精确根路由后才对该子进程操作。发送前先写不可覆盖并同步落盘的 claim，已有 claim／回执或发生写入失败均不会重复触发。输出给出 `service-restart-<id>.json` 回执路径；`signal_sent` 只表示信号已发出，不代表恢复成功。若报告过期，重新 capture；若回执拒绝、失败或未生成，反馈路径与输出，不反复发请求或自行删除 claim。

4. 等主页重新出现、译文恢复后再等约 3 秒，执行一次 capture。若约 60 秒仍未恢复，反馈现象和回执，不手动结束其他进程：

```powershell
python -B "D:\Python\Python_Code_Set\Antigravity-zh-CN\tests\manual\m1_lab.py" capture
```

反馈重启前报告、服务操作回执、重启后报告三条路径，以及应用窗口是否一直保持、主页译文是否恢复。验收需确认 sessionId／appPid 与窗口保持，服务 generation 增加，受控译文及授权恢复、preloadErrors=0；端口或 PID 可能重用，不能只靠端口变化判断服务重启。会话缓存可能复用提供方结果，不要求 providerCalls 必须增加。
