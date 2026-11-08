# 虹光日夜 UI 设计 · v1.2

本目录保存 Antigravity 中文助手的设计文档与预览，延续“状态首页＋首次引导”和“柔和圆角卡片”的选择。正式应用仍按 Python + PySide6 规划，当前可运行软件与验证结果见 [项目状态](../PROJECT_STATUS.md)。

根目录放设计文档、HTML 交互预览与 PNG 效果预览；背景原图、参考海报、设计参数和素材清单统一放在 `assets/`。

```text
design/
├── README.md
├── WINDOWS_APP_PLAN.md
├── FRONTEND_STYLE_PLAN.md
├── frontend-style-preview.html
├── ui-home-light.png
├── ui-home-dark.png
├── ui-dictionary-light.png
└── assets/
    ├── frontend-tokens.json
    ├── manifest.json
    ├── Gemini_Background_Light_1920x1080.png
    ├── Gemini_Background_Dark_1920x1080.png
    └── Gemini_Poster_Clean.png
```

| 文件 | 内容 |
| --- | --- |
| [Windows 应用总计划](WINDOWS_APP_PLAN.md) | 产品范围、用户流程、架构与开发阶段 |
| [前端样式开发计划](FRONTEND_STYLE_PLAN.md) | 组件状态、页面规则、Qt 落地步骤与验收标准 |
| [frontend-style-preview.html](frontend-style-preview.html) | 四页交互原型；在浏览器中打开，保留同目录的 assets 文件夹 |
| [ui-home-light.png](ui-home-light.png) | 珠光白／淡紫的日间首页效果预览 |
| [ui-home-dark.png](ui-home-dark.png) | 靛蓝／浅紫的夜间首页效果预览 |
| [ui-dictionary-light.png](ui-dictionary-light.png) | 实色表格与右侧词条编辑器效果预览 |
| [assets/frontend-tokens.json](assets/frontend-tokens.json) | 颜色、字号、圆角、尺寸、断点和背景使用参数 |
| [assets/manifest.json](assets/manifest.json) | 三份用户原图的来源、尺寸、字节数与 SHA-256 |

直接用浏览器打开 HTML 即可预览。`assets/frontend-tokens.json` 中的 `artwork` 路径以 `doc/design/` 为基准，与 HTML 中的相对路径保持一致；素材清单中的 `name` 则相对于 `assets/`。HTML 内嵌一份相同的设计参数以支持本地打开，修改参数时需同步内嵌副本及生成的样式。

PNG 为单独绘制的界面构图稿，1440×900，已目视检查；不是浏览器或 Qt 程序截图。原图副本与用户提供文件的哈希一致，未修改原图。

原型可以切换主题、页面、紧凑窗口和示例状态；可查找、修改、新增示例词条，查看未保存提示、操作确认与首次引导。所有变化仅在内存中，刷新即重置，不读取安装或系统代理，不写真实词典。

设计稿用于确认视觉，HTML 用于审阅交互；文字折行、滚动和系统窗口框以正式 Qt 实现验收为准。2026-11-05 设计交付记录包含文档/参数一致性、脚本语法及 28 组语义色对比检查；HTML 浏览器渲染与操作验收尚未完成。2026-11-08 仅整理目录与引用，不代表完成 GUI 实现或运行验收。实际应用的深浅主题、DPI、键盘与读屏验收列在开发计划中。
