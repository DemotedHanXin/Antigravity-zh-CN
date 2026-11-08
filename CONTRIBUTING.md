# 贡献指南

本指南面向 [DemotedHanXin/Antigravity-zh-CN](https://github.com/DemotedHanXin/Antigravity-zh-CN) 当前分支。软件的下载、汉化、还原和代理使用方法见 [README.md](README.md)（[English](README_EN.md)）；实现状态与待办见 [doc/PROJECT_STATUS.md](doc/PROJECT_STATUS.md)。

## 项目来源与维护范围

- **上游原作者**：[MIMICTE](https://github.com/MIMICTE) 及上游贡献者，原仓库为 [MIMICTE/Antigravity-zh-CN](https://github.com/MIMICTE/Antigravity-zh-CN)。
- **当前分支作者与维护者**：[DemotedHanXin](https://github.com/DemotedHanXin)（Git 提交名 `Demoted_Han_Xin`）。本分支基于上游继续完善翻译、安装校验与还原保护、Windows 代理启动和快捷方式管理，并规划图形界面。
- **许可关系**：上游与当前分支均使用 MIT 许可证。新增贡献沿用该许可，保留上游的版权声明和来源，不将上游成果重新署名为当前作者独立创作。

当前可运行功能位于 `src/`。`doc/design/` 中的 Windows 应用计划、预览图和 HTML 原型属于设计交付，不能视为已经实现的 GUI 功能。

## 反馈问题

先查看当前分支的文档和已有 [Pull Requests](https://github.com/DemotedHanXin/Antigravity-zh-CN/pulls)，确认是否已有修复。截至 2026-11-08，本仓库尚未启用 Issues 和 Discussions；开放后可在本仓库提交问题，已有修复方案可直接提交 PR。上游的问题入口仅用于上游自身可复现的问题，不将本分支新增功能的问题默认转交上游。

反馈时提供：

- 操作系统、Python 和 Antigravity 版本，以及使用的分支或提交。
- 执行命令、复现步骤、预期行为与实际输出。
- 翻译问题对应的英文原文、所在页面或菜单，以及建议译法。
- 代理问题中使用的模式（HTTP／混合端口、TUN 等）及是否指定了 `--app-dir`、`--scan-root`。

分享日志和路径前移除账号、令牌、密钥等隐私信息。

## 提交修改

1. Fork 当前仓库 `DemotedHanXin/Antigravity-zh-CN`，克隆自己的 fork 并创建工作分支。
2. 按修改范围编辑源码、测试或文档。命令行脚本位于 `src/`，不要只复制单个脚本而遗漏公共模块。
3. 运行与变更有关的测试，检查文档链接与命令是否仍然有效。
4. 提交并推送自己的工作分支，在 GitHub 向 **DemotedHanXin/Antigravity-zh-CN** 的目标维护分支发起 Pull Request。
5. 在 PR 中说明问题、改动后行为、验证环境和结果；未验证的平台或功能应明确列出。

遵循现有代码风格，添加有必要的注释。安装归档处理放在 `src/antigravity_common.py`，汉化与注入逻辑放在 `src/Antigravity-Patcher.py`，还原逻辑放在 `src/Restore.py`；代理启动器与快捷方式逻辑集中在 Setup/Cleanup 脚本。

## 改进翻译

在 `src/Antigravity-Patcher.py` 的注入代码中修改 `dictionary`；动态计数、跨节点提示和菜单翻译还涉及对应规则。当前没有独立的运行时 JSON 词典或可用的图形词典编辑器。

- 准确表达原文，保持简洁、自然，同一术语使用同一译法。
- 优先限定完整文案或明确的 UI 上下文，避免宽泛替换污染代码、用户输入或用户生成内容。
- 保留占位符、快捷键、标点、链接和内联结构。
- 新增动态匹配规则时，验证目标文案能翻译，同时相邻内容和不应翻译的内容不受影响。
- 需要实际应用验证时，在可恢复的测试安装中重新运行汉化脚本；修改仓库词条本身不会自动更新已安装的应用。

| English | 中文 | 说明 |
|---------|------|------|
| Agent | 智能体 | 不翻译为"代理" |
| Workspace | 工作区 | 不翻译为"工作空间" |
| Task | 任务 | - |
| Artifact | 产物 | - |
| Settings | 设置 | 不翻译为"设置项" |
| Model | 模型 | - |
| Conversation | 对话 | 不翻译为"会话" |

## 测试与验收

在仓库根目录运行：

```powershell
python -B -m unittest discover -s tests -v
```

运行脚本仅依赖 Python 标准库。测试中的 JavaScript 规则验证需要 Node.js，DOM 验证需要 Chrome 或 Edge，Windows 快捷方式验证使用 PowerShell 和 WScript.Shell；缺少相应环境时可能跳过测试，提交时应报告跳过项。

安装文件切换的变更应覆盖无原始归档、归档损坏、文件占用、权限不足和回滚等失败路径。代理变更应验证预览、创建、清理、再次创建，以及快捷方式参数保留和自定义扫描目录。优先使用隔离的模拟安装和临时快捷方式。

涉及真实应用验收时，使用可修复或重装的测试安装，确认汉化后能手动启动、主要界面可用、还原后能手动启动。Patcher/Restore 当前始终不自动启动软件；`--no-launch` 只是兼容参数。不要把单元测试通过等同于所有 Antigravity 版本和平台均可用。

## 文档与设计文件

- [README.md](README.md) 与 [README_EN.md](README_EN.md) 的功能、路径、参数和许可说明应同步更新；不内嵌图片展示。
- [项目状态](doc/PROJECT_STATUS.md) 应区分已实现、已验证、尚未验证和计划中的功能，并注明验证日期。
- [设计目录](doc/design/README.md) 的根目录保存预览效果和设计文档，`assets/` 保存背景原图、设计参数与素材清单。移动文件时同步更新 Markdown、HTML 和 JSON 引用。
- 预览图可使用普通文件链接供查看；HTML 原型只操作示例数据。

## 行为准则

- 尊重他人
- 保持友善和专业
- 接受建设性批评
- 关注对社区最有利的事情

## 开源许可

上游的 [MIT License](https://github.com/MIMICTE/Antigravity-zh-CN/blob/main/LICENSE) 与当前仓库的 [LICENSE](LICENSE) 保持相同许可，当前保留的版权声明为 `Copyright (c) 2026 Antigravity-zh Contributors`。当前维护者的新增贡献不覆盖上游作者署名。

提交贡献表示您有权提供这些内容，并同意其按本项目 MIT 许可证发布。复制或分发本项目及其实质性部分时，应保留版权声明与许可全文；软件按许可证约定以“原样”提供。

引入第三方代码或素材时，注明来源并保留其适用的许可说明。Antigravity 本体、商标和第三方素材的权利归各自权利人，本仓库的 MIT 许可不构成对它们的额外授权。
