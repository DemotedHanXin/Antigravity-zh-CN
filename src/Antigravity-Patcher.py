# coding: utf-8
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from antigravity_common import (
    discover_install, extract_asar, remove_tree,
    resources_dir, stop_application, validate_extracted_app,
)

DOM_TRANSLATOR_INJECTION = r"""
// Antigravity Chinese Localization Engine
(function() {
  const dictionary = {
    // Top Bar & Global Navigation
    "Goals": "目标", "Tasks": "任务", "Artifacts": "产物", "Artifact": "产物", "Scratch": "草稿", "Chat": "对话",
    "No artifacts generated": "暂无生成的产物", "No artifacts": "暂无产物",
    "Active": "进行中", "Inactive": "未激活", "Completed": "已完成", "Failed": "已失败",
    "History": "历史记录", "Settings": "设置", "System": "系统", "Network": "网络",
    "Model": "模型", "Memory": "记忆", "Tools": "工具", "Agents": "智能体",
    "Overview": "概览", "Logs": "日志", "Clear": "清除", "Save": "保存",
    "Customize Sections": "自定义分区", "Documents": "文档", "Links": "链接",
    "Cancel": "取消", "Submit": "提交", "Run": "运行", "Stop": "停止",
    "Edit": "编辑", "Delete": "删除", "Add": "添加", "Remove": "移除", "Download": "下载",
    "Monthly Limit": "每月限额", "Weekly Limit": "每周限额", "Five Hour Limit": "五小时限额",
    "Weekly Limit Remaining": "每周限额剩余", "Five Hour Limit Remaining": "五小时限额剩余",
    "limit": "限额", "limits": "限额", "weekly": "每周", "hourly": "每小时",
    "Sidebar": "侧边栏", "Display Options": "显示选项", "Message input": "消息输入框", "Record voice memo": "录制语音备忘",
    "Typeahead menu": "预输入菜单", "Group By": "分组方式", "Last Updated": "最后更新", "Last Prompt": "最新提示词", "Last prompt": "最新提示词",
    "Sort Projects": "项目排序", "Custom Order": "自定义顺序", "Repo": "仓库",
    "Display": "显示", "Auto Pin": "自动置顶", "Archived Only": "仅显示已归档",
    "Alphabetical (A-Z)": "字母顺序 (A-Z)", "Alphabetical (Z-A)": "字母倒序 (Z-A)", "Date Added": "添加日期", "Creation Date": "创建日期", "Created Date": "创建日期", "Subtitles": "副标题", "No Subtitle": "无副标题",
    "Filter": "筛选", "Scheduled": "已计划", "Environment": "环境", "None": "无", "Fast": "快速",
    "Last 7 days": "最近 7 天", "Last 24 hours": "最近 24 小时", "Last 30 days": "最近 30 天", "Last 3 months": "最近 3 个月",
    "Today": "今天", "Yesterday": "昨天", "This week": "本周", "This month": "本月", "All time": "全部时间",
    "Project": "项目", "project": "项目", "projects": "项目", "Conversation": "对话", "conversation": "对话",
    "No Project": "无项目", "No project": "无项目", "no project": "无项目",
    "No projects found": "暂无项目", "No projects found.": "暂无项目",
    "No project found": "暂无项目", "No project found.": "暂无项目",
    "found": "找到", "not found": "未找到", "Not found": "未找到",
    "Search projects": "搜索项目", "Search projects...": "搜索项目...",
    "Search Projects": "搜索项目", "Search Projects...": "搜索项目...", "Search Projects…": "搜索项目…",
    "Workspace": "工作区", "workspace": "工作区", "Minimize": "最小化", "Maximize": "最大化", "Back": "返回",
    "Folders": "文件夹", "folders": "文件夹", "including": "包括",
    "Rename": "重命名", "Mark Unread": "标记为未读", "Mark Read": "标记为已读", "Duplicate": "制作副本",
    "Mark All as Read": "全部标为已读",
    "Export": "导出", "Import": "导入", "Pin": "置顶", "Archive": "归档",
    "Conversation Archived": "对话已归档", "Conversation Unarchived": "对话已取消归档",
    "This chat is archived.": "此对话已归档。", "Undo": "撤销",
    "View archived in the sidebar ( menu).": "在侧边栏的筛选菜单中查看已归档对话。",
    "View archived in the sidebar (menu).": "在侧边栏的筛选菜单中查看已归档对话。",
    "Split": "分屏", "Split Right": "向右分屏", "Split Down": "向下分屏", "Split Left": "向左分屏", "Split Up": "向上分屏",
    "Replace With New": "替换为新建", "Replace with New": "替换为新建", "Replace with new": "替换为新建",
    "Copy Link": "复制链接", "Copy link": "复制链接", "Copy ID": "复制 ID", "Copy id": "复制 ID",
    "Copy Path": "复制路径",
    "Path copied!": "路径已复制！",
    "Copy Project Name": "复制项目名称", "Project Settings": "项目设置",
    "Show in File Explorer": "在文件资源管理器中显示",
    "Copy Conversation ID": "复制对话 ID", "Copy Conversation Link": "复制对话链接", "Duplicate Conversation": "复制对话",
    "Close Others": "关闭其他", "Close All": "全部关闭", "Close to the Right": "关闭右侧", "Close Saved": "关闭已保存",
    "Create New Project": "创建新项目", "Archive Conversation": "归档对话", "now": "刚刚",
    "Conversation Name": "对话名称", "Conversation ID": "对话 ID", "Project Name": "项目名称",
    "Set Project Name": "设置项目名称",
    "Enter project name...": "输入项目名称...", "Enter project name…": "输入项目名称…",
    "Toggle Auxiliary Pane": "切换辅助面板", "Maximize Pane": "最大化面板", "Minimize Pane": "最小化面板", "Restore Pane": "还原面板",
    "Files Changed": "已修改文件", "Files changed": "已修改文件", "File Changed": "已修改文件",
    "Modified Files": "已修改文件", "No changes to review": "暂无待审阅的更改",
    "No file changes": "暂无文件更改", "Hide Whitespace Changes": "隐藏空白字符更改",
    "Uploads": "已上传文件", "uploads": "已上传文件", "See all": "查看全部", "See All": "查看全部",
    "Background Tasks": "后台任务", "Background tasks": "后台任务", "Background Task": "后台任务",
    "Terminals": "终端", "terminals": "终端", "Delete Terminal": "删除终端", "Split Terminal": "拆分终端",
    "Add Terminal": "添加终端", "Add terminal": "添加终端",
    "No subagents": "暂无子智能体", "No subagents running": "暂无运行中的子智能体", "No subagent": "暂无子智能体",
    "Select Model": "选择模型", "Select model": "选择模型", "Select a model": "选择一个模型",
    "User cancelled agent execution.": "用户取消了智能体执行。",
    "Open Antigravity IDE": "打开 Antigravity IDE", "Create Project": "创建项目", 
    "Command Palette": "命令面板", "Zoom In": "放大", "Zoom Out": "缩小", "Reset Zoom": "重置缩放",
    "Delete Conversation": "删除对话", "Are you sure you want to delete this conversation? This action cannot be undone.": "您确定要删除此对话吗？此操作无法撤销。",
    "Confirm Undo": "确认撤销", "This undo action will not make any code changes.": "此撤销操作不会对代码做出任何更改。",
    "Confirm Redo": "确认重做", "This redo action will not make any code changes.": "此重做操作不会对代码做出任何更改。",
    "Undo changes up to this point": "撤销更改至此处", "Redo changes up to this point": "重做更改至此处",
    "Confirming this undo action will make the following changes:": "确认此撤销操作将做出以下更改：",
    "Confirming this undo action will not make any code changes.": "确认此撤销操作不会做出任何代码更改。",
    "Confirming this redo action will make the following changes:": "确认此重做操作将做出以下更改：",
    "Confirming this redo action will not make any code changes.": "确认此重做操作不会做出任何代码更改。",
    "Undo changes": "撤销更改", "Redo changes": "重做更改",
    "Record Audio": "录制音频", "Record Audio Ctrl+M": "录制音频 Ctrl+M",
    "Stop Recording": "停止录音", "Quote": "引用",
    "Stop Recording and Send": "停止录音并发送",
    "Send message": "发送消息", "Send message Enter": "发送消息 Enter",
    "Send Message": "发送消息",
    "Getting started with a Project": "开始使用项目",
    "Now that you've created a project, configure your project's agent settings or start a conversation.": "现在您已经创建了一个项目，接下来请配置该项目的智能体设置，或者直接开始对话。",
    "Open Settings": "打开设置", "Start first conversation": "开始首次对话",
    "Main Agent": "主智能体", "Add Context": "添加上下文",
    "Loading Antigravity": "正在加载 Antigravity", "Loading": "正在加载",
    "+ New Conversation": "+ 新建对话", "New Conversation": "新建对话", "Conversation History": "历史对话", "Scheduled Tasks": "计划任务",
    "New Conversation in Project": "在项目中新建对话",
    "Automations": "自动化", "Automation": "自动化",
    "Create with Prompt": "通过提示词创建",
    "No automations yet": "暂无自动化任务", "否 automations yet": "暂无自动化任务",
    "Run a prompt on a schedule, like a morning summary of yesterday's changes. Runs show up here.": "按计划运行提示词，例如在早晨汇总前一天的更改。运行记录会显示在此处。",
    "Run a prompt on a schedule, like a morning summary of yesterday's changes.": "按计划运行提示词，例如在早晨汇总前一天的更改。",
    "Runs show up here.": "运行记录会显示在此处。",
    "Open File": "打开文件", "New Terminal": "新建终端", "just now": "刚刚", "Just now": "刚刚",
    "Search for files in the project...": "搜索项目中的文件...",
    "Search for files in the project…": "搜索项目中的文件…",
    "No conversations yet": "暂无对话", "Open IDE": "打开 IDE", "Window": "窗口",
    "Review": "审阅", "Email": "电子邮箱", "Upgrade": "升级", "Not in Project": "未分组项目",
    "Ask anything, @ to mention, / for actions": "输入任何问题，使用 @ 提及，使用 / 执行操作",
    "Status": "状态", "Sort Conversations": "对话排序", "Worktree": "工作树",
    "Local Checkout": "本地工作", "New Worktree": "新建工作树",
    "Worktrees are available for Git repositories": "Git 仓库可使用工作树功能",
    "Select Environment": "选择环境", "Select Environment (Ctrl+.)": "选择环境 (Ctrl+.)",
    "Select Project": "选择项目", "Search Conversations": "搜索对话",
    "New Project": "新建项目", "New Remote Project": "新建远程项目", "Quick Start": "快速开始",
    "Select a folder.": "选择文件夹。",
    "Create a project whose conversations run remotely.": "创建一个项目，其对话将在远程运行。",
    "Good response": "有效回复", "Bad response": "无效回复",
    "Good Response": "有效回复", "Bad Response": "无效回复",

    // Slash Command Descriptions (command identifiers stay unchanged)
    "Ask a quick question without interrupting the main conversation.": "快速提问，不中断主对话。",
    "Run until the specified goal is completely finished.": "持续执行，直到指定目标完全达成。",
    "Compact the conversation now (summarize history to free up the context window).": "立即压缩对话（总结历史记录以释放上下文窗口空间）。",
    "Run an instruction on a recurring schedule or as a one-time timer.": "按周期计划或一次性定时执行指令。",
    "Invoke a browser agent for web tasks.": "调用浏览器智能体处理网页任务。",
    "Plan carefully before executing a task.": "执行任务前仔细制定计划。",
    "Interview me to align on a plan.": "向我提问，以便就计划达成一致。",
    "Invoke a team of agents to autonomously tackle large projects.": "调用智能体团队，自主处理大型项目。",
    "Reflect on recent successes or corrections to capture reusable skills or rules.": "回顾近期的成功经验或纠正意见，提炼可复用的技能或规则。",
    "Invoke the Boost multi-agent orchestrator for complex tasks.": "调用 Boost 多智能体编排器处理复杂任务。",

    // Cloud Resources & Remote Projects
    "Select Resource(s)": "选择资源", "Add Resource": "添加资源", "Upload Files": "上传文件",
    "Uploaded files and connected resources are mounted in your cloud environment.": "上传的文件和已连接资源会挂载到您的云端环境中。",
    "Files and resources in cloud workspaces": "云端工作区中的文件和资源",
    "Here's how uploaded files, attachments, and connected resources work in your cloud environment": "以下说明上传的文件、附件和已连接资源在云端环境中的使用方式。",
    "Stored and mounted in your cloud environment": "在云端环境中存储并挂载",
    "Uploaded project files and in-chat attachments are stored on Google servers and mounted into your cloud sandbox so your agent can read and work with them.": "上传的项目文件和对话中的附件会存储在 Google 服务器上，并挂载到您的云端沙盒中，供智能体读取和处理。",
    "Connected Google Drive and GitHub resources": "已连接的 Google 云端硬盘和 GitHub 资源",
    "Files, folders, and repositories you connect are accessible to your agent in this project, including during background or scheduled runs.": "智能体可以访问您为此项目连接的文件、文件夹和仓库，包括在后台运行或按计划运行时。",
    "Manage and delete your data anytime": "随时管理和删除您的数据",
    "Remove individual uploaded files or connected resources in Project Settings, or delete a project or conversation to remove its stored files.": "在项目设置中移除单个上传文件或已连接资源，或通过删除项目或对话来移除其存储的文件。",
    "Got it": "知道了", "Recent": "最近使用",
    "Search Remote...": "搜索远程资源...", "Search Remote…": "搜索远程资源…",
    "GitHub Repositories": "GitHub 仓库",
    "Loading Repositories...": "正在加载仓库...", "Loading Repositories…": "正在加载仓库…",
    "Avoid uploading highly sensitive data and verify actions taken by your agent.": "避免上传高度敏感的数据，并核实智能体执行的操作。",
    "Make sure you have the necessary rights to any content or files that you upload, including content of minors.": "确保您对上传的任何内容或文件（包括涉及未成年人的内容）拥有必要权利。",
    "Don't generate content that infringes on others' rights, including content that deceives, harasses, or harms.": "请勿生成侵犯他人权利的内容，包括具有欺骗、骚扰或伤害性质的内容。",
    "When using Antigravity, you must comply with Google's Prohibited Use Policy.": "使用 Antigravity 时，您必须遵守 Google 的《禁止使用政策》。",
    "Your use is subject to the Google Antigravity Terms of Service and Google Privacy Policy.": "您的使用行为受《Google Antigravity 服务条款》和《Google 隐私权政策》约束。",
    "necessary rights": "必要权利", "Prohibited Use Policy": "禁止使用政策",
    "Google Antigravity Terms of Service": "Google Antigravity 服务条款", "Google Privacy Policy": "Google 隐私权政策",

    // General Settings Page
    "Welcome to Antigravity": "欢迎使用 Antigravity", "Continue with Google": "使用 Google 账号继续",
    "Use Business Account": "使用企业账号", "Having trouble signing in?": "登录遇到问题？",
    "Business Account Sign In": "企业账号登录", "Continue with Google Cloud": "使用 Google Cloud 继续",
    "Use Advanced SSO Config": "使用高级 SSO 配置", "WIF Config": "WIF 配置",
    "Use this if your admin gave you a WIF config. Paste it below to sign in.": "如果管理员向您提供了 WIF 配置，请使用此方式。将配置粘贴到下方即可登录。",
    "Use this if your admin gave you a WIF config.": "如果管理员向您提供了 WIF 配置，请使用此方式。",
    "Paste it below to sign in.": "将配置粘贴到下方即可登录。",
    "E.g. locations/global/workforcePools...": "例如：locations/global/workforcePools...",
    "E.g. locations/global/workforcePools…": "例如：locations/global/workforcePools...",
    "Sign In with SSO": "使用 SSO 登录",
    "General": "常规", "Appearance": "外观", "Theme": "主题", "Light": "浅色", "Dark": "深色",
    "Language": "语言", "Version": "版本", "Check for Updates": "检查更新", "About": "关于",
    "No updates available": "暂无可用更新",
    "Advanced": "高级", "API Key": "API 密钥", "Account": "账号", "Profile": "个人资料",
    "Logout": "退出登录", "Sign Out": "退出登录", "Feedback": "反馈", "Privacy": "隐私",
    "Terms": "条款", "Auto-start": "开机自启", "Launch on startup": "开机时启动",
    "Notifications": "通知", "Shortcuts": "快捷键", "Keyboard Shortcuts": "键盘快捷键",
    "Global Shortcut": "全局快捷键", "Toggle Visibility": "切换显示/隐藏", "Proxy": "代理",
    "Update": "更新", "Updates": "更新", "Check for update": "检查更新",
    "Models": "模型", "Customizations": "自定义", "Browser": "浏览器", "App": "应用", "Application": "应用", "Applications": "应用",
    "Projects": "项目", "Conversations": "对话", "Provide Feedback": "提供反馈",
    "Give Feedback": "提供反馈",
    "Manage your plan, credentials, and general preferences.": "管理您的套餐、凭据和常规偏好设置。",
    "Enable Telemetry": "启用遥测",
    "When toggled on, Antigravity collects usage data to help Google enhance performance and features.": "开启后，Antigravity 将收集使用数据，以帮助 Google 提升性能和功能。",
    "Marketing Emails": "营销邮件",
    "Receive product updates, tips, and promotions from Google Antigravity via email.": "通过电子邮件接收来自 Google Antigravity 的产品更新、提示和促销信息。",
    "Your Plan: Google AI Pro": "当前计划：Google AI Pro", "Your Plan:": "当前计划：",
    "You can upgrade to a Google AI Ultra plan to receive higher rate limits.": "您可以升级至 Google AI Ultra 套餐以获得更高的使用限额。",
    "By using this app, you agree to its": "使用本应用即表示您同意其",
    "By using this app, you agree to its Terms of Service": "使用本应用即表示您同意其服务条款",
    "By using this app, you agree to its 服务条款": "使用本应用即表示您同意其服务条款",
    "Terms of Service": "服务条款",
    "Remote Agents Data": "远程智能体数据",
    "Delete All Remote Agents Data": "删除所有远程智能体数据", "Delete All Data": "删除所有数据",
    "Delete All Remote Agents Data?": "删除所有远程智能体数据？",
    "This permanently deletes all of your Remote Agents conversations, projects, scheduled tasks, connected plugins and settings, and stops any running remote agents. It can't be undone. Data in the desktop app and your Google account are not affected, and you can keep using Remote Agents afterwards.": "此操作将永久删除您的所有远程智能体对话、项目、计划任务、已连接的插件和设置，并停止所有正在运行的远程智能体。此操作无法撤销。桌面应用及 Google 账号中的数据不受影响，之后您仍可继续使用远程智能体。",
    "This permanently deletes all of your Remote Agents conversations, projects, scheduled tasks, connected plugins and settings, and stops any running remote agents.": "此操作将永久删除您的所有远程智能体对话、项目、计划任务、已连接的插件和设置，并停止所有正在运行的远程智能体。",
    "It can't be undone.": "此操作无法撤销。",
    "Data in the desktop app and your Google account are not affected, and you can keep using Remote Agents afterwards.": "桌面应用及 Google 账号中的数据不受影响，之后您仍可继续使用远程智能体。",
    "Permanently delete your remote conversations, projects, scheduled tasks, connected plugins and settings. Data in the desktop app and your Google account are not affected.": "永久删除您的远程对话、项目、计划任务、已连接的插件和设置。桌面应用及 Google 账号中的数据不受影响。",
    "永久删除your remote conversations, projects, scheduled tasks, connected plugins and settings. Data in the desktop app and your Google account are not affected.": "永久删除您的远程对话、项目、计划任务、已连接的插件和设置。桌面应用及 Google 账号中的数据不受影响。",
    "Permanently delete your remote conversations, projects, scheduled tasks, connected plugins and settings.": "永久删除您的远程对话、项目、计划任务、已连接的插件和设置。",
    "永久删除your remote conversations, projects, scheduled tasks, connected plugins and settings.": "永久删除您的远程对话、项目、计划任务、已连接的插件和设置。",
    "Data in the desktop app and your Google account are not affected.": "桌面应用及 Google 账号中的数据不受影响。",
    "Configure agent execution, queued message delivery, and permissions.": "配置智能体执行、排队消息发送以及权限。",
    "Permissions": "权限",
    "Configure what the agent can do in local and remote conversations.": "配置智能体在本地和远程对话中可以执行的操作。",
    "This Computer": "本机", "Remote": "远程",
    "Controls permissions for remote conversations.": "控制远程对话的权限。",
    "Auto (Preview)": "自动（预览）", "Turbo": "极速模式",
    "Every command requires approval.": "每条命令都需要批准。",
    "Ask before sensitive operations.": "在执行敏感操作前询问。",
    "Automatically decide if commands run.": "自动决定是否执行命令。",
    "Run all commands without restrictions.": "不受限制地执行所有命令。",
    "Execution": "执行", "Agent Settings": "智能体设置", "Agent Behavior": "智能体行为",
    "File Permissions": "文件权限", "Network Permissions": "网络权限",
    "Queued Messages": "排队消息", "Configure when follow-up messages are sent.": "配置发送后续消息的时机。",
    "Queue": "排队", "Send Immediately": "立即发送", "Keyboard shortcuts": "键盘快捷键",
    "Queue until after the current run.": "加入队列，待当前运行结束后发送。",
    "Queue until after the current turn.": "加入队列，待当前轮次结束后发送。",
    "Interrupt the agent and send immediately.": "中断智能体并立即发送。",
    "Security Preset": "安全预设", 
    "Choose a predefined security preset for the agent. This controls terminal auto-execution policy, and file access policy.": "为智能体选择一个预定义的安全预设。这将控制终端自动执行策略和文件访问策略。",
    "Controls the actions the agent can take.": "控制智能体可以执行的操作。",
    "Controls the actions the agent can take": "控制智能体可以执行的操作",
    "Global Permissions": "全局权限", "Global permissions": "全局权限",
    "Tool Permissions": "工具权限", "Tool permissions": "工具权限",
    "Modify permissions for file, terminal, and MCP tools.": "修改文件、终端和 MCP 工具的权限。",
    "Modify permissions for file and terminal tools.": "修改文件和终端工具的权限。",
    "Modify permissions for file, terminal, and MCP tools": "修改文件、终端和 MCP 工具的权限",
    "Default": "默认", "Always Ask": "总是询问", "Always Proceed": "自动执行",
    "Inherit Global": "继承全局", "Inherits Global": "继承全局", "inherit global": "继承全局",
    "Inherits your Global Permissions when working in this project.": "在此项目中工作时继承您的全局权限。",
    "Inherits your Global Permissions when working in this project": "在此项目中工作时继承您的全局权限",
    "Inherits your Global Permissions": "继承您的全局权限",
    "Plan Review Policy": "计划审阅策略",
    "Whether the agent asks you to review its documents.": "智能体是否要求您审阅其文档。",
    "Whether the agent asks you to review its documents": "智能体是否要求您审阅其文档",
    "Type / and select plan to have the agent generate a plan.": "输入 / 并选择 plan 即可让智能体生成计划。",
    "Type / and select plan to have the agent generate a plan": "输入 / 并选择 plan 即可让智能体生成计划",
    "to have the agent generate a plan.": "即可让智能体生成计划。",
    "to have the agent generate a plan": "即可让智能体生成计划",
    "and select": "并选择",
    "Artifact Review Policy": "产物审阅策略",
    "Specifies Agent's behavior when asking for review on artifacts, which are documents it creates to enable a richer conversation experience.": "指定智能体在请求审阅产物时的行为。产物是指其为提供更丰富对话体验而创建的各类文档与生成物。",
    "File Access Rules": "文件访问规则", "Configure allowed and denied paths for file reads and writes.": "配置允许和拒绝的文件读取和写入路径。",
    "Network Access Rules": "网络访问规则", "Configure allowed and denied URLs for reading.": "配置允许和拒绝读取的 URL。",
    "File Reads": "文件读取", "Allow/deny agent read access to specific files or directories.": "允许/拒绝智能体对特定文件或目录的读取权限。",
    "File Writes": "文件写入", "Allow/deny agent write access to specific files or directories.": "允许/拒绝智能体对特定文件或目录的写入权限。",
    "Network Reads": "网络读取", "Allow/deny agent read access to specific URLs.": "允许/拒绝智能体对特定 URL 的读取权限。",
    "Read URLs": "URL 读取", "Allow/deny agent read access to specific URLs or domains.": "允许/拒绝智能体对特定 URL 或域名的读取权限。",
    "Allow/deny specific terminal commands.": "允许/拒绝特定的终端命令。", "e.g., npm test": "例如：npm test",
    "External tools the agent can call via Model Context Protocol.": "智能体可通过模型上下文协议 (MCP) 调用的外部工具。", "Enter tool name or server...": "输入工具名称或服务器...",
    "Allow/deny agent command execution outside the sandbox.": "允许/拒绝智能体在沙盒外部执行命令。", "e.g., curl": "例如：curl",
    "Allow": "允许", "Deny": "拒绝", "There are no customizations enabled.": "当前未启用任何自定义项。",
    "Manage Antigravity app settings.": "管理 Antigravity 应用设置。",
    "Inherits your General settings when working in this project.": "在此项目中工作时继承您的全局设置。",
    "No MCP servers installed": "未安装任何 MCP 服务器", "Use Add MCP to browse the store, or add a custom server via the MCP config.": "使用“添加 MCP”浏览商店，或通过 MCP 配置添加自定义服务器。",
    "Plugins": "插件", "Browse and enable plugins from the Build With Google catalog.": "浏览并启用“使用 Google 构建”目录中的插件。",
    "Cloud CLI MCP Server provides tools to run gcloud and bq CLIcommands in a remote sandbox environment": "Cloud CLI MCP 服务器提供了在远程沙盒环境中运行 gcloud 和 bq CLI 命令的工具。",
    "Browser Actuation Permissions": "浏览器操作权限", "Execute URLs": "URL 执行", "Allow/deny agent browser actuation access to specific URLs.": "允许/拒绝智能体对特定 URL 的浏览器操作权限。",
    "Media": "媒体", "Mentions": "提及", "Actions": "操作",
    "Enable Remote Control": "启用远程控制", "Work with local agents from another device.": "在其他设备上与本地智能体协同工作。",
    "Enter Queues after the turn": "Enter 键：在当前轮次后排队",
    "Alt+Enter Sends immediately": "Alt+Enter 键：立即发送",
    "Alt+Enter On empty prompt, sends next in queue": "Alt+Enter 键：在输入为空时，发送队列中的下一条",
    "Useful for typical development with an emphasis on security. It prioritizes safety over speed by requiring manual approval for all terminal commands and files outside the project directory.": "适用于注重安全的典型开发场景。它将安全性置于速度之上，要求对所有终端命令和项目目录之外的文件访问进行手动批准。",
    "Requires manual review for all terminal commands and file accesses outside of the working folders.": "要求对所有终端命令和工作文件夹之外的文件访问进行手动审阅。",
    "Full machine": "完整机器访问",
    "All terminal commands require review. The agent can read or write to any file in the machine.": "所有终端命令均需审阅。智能体可以读取或写入机器上的任何文件。",
    "Turbo mode": "极速模式",
    "Disables all safety barriers for maximal iteration velocity.": "禁用所有安全屏障，以获得最快的迭代速度。",
    "Custom": "自定义配置", "Manually customize individual settings.": "手动自定义各项设置。",
    "System Default": "跟随系统", "Zoom Level": "缩放比例", "Font Size": "字体大小",
    "Small": "小", "Medium": "中", "Large": "大", "Code Font": "代码字体", "Editor Font": "编辑器字体",
    "Default Model": "默认模型", "Temperature": "温度", "System Prompt": "系统提示词",
    "Search Engine": "搜索引擎", "Web Search": "网络搜索", "Enable Web Access": "启用网络访问",
    "Startup": "启动", "Launch at login": "登录时自动启动", "Hardware Acceleration": "硬件加速",
    "Current Version": "当前版本", "Up to date": "已是最新版本", "Downloading": "下载中...",
    "Downloading Update": "正在下载更新", "Restart to Update": "重启以应用更新",
    "Restart to update": "重启以更新", "Danger Zone": "危险区域", "Clear History": "清除历史记录",
    "Delete All": "全部删除", "Reset to Default": "恢复默认设置", "Restore Defaults": "恢复默认设置", "Reset to default": "恢复默认", "Restore defaults": "恢复默认设置",
    "Keybindings": "快捷键绑定", "Command": "命令", "Shortcut": "快捷键", "Action": "操作",
    "Advanced Settings": "高级设置", "Developer Tools": "开发者工具", "Toggle Developer Tools": "切换开发者工具",
    "Open Logs": "打开日志", "Proxy Server": "代理服务器", "Enable Proxy": "启用代理",
    "Auto-Updater": "自动更新程序", "Always": "始终", "Never": "从不", "Ask": "询问",
    "Contrast": "对比度", "contrast": "对比度", "Strong": "强", "strong": "强",
    "Windows Subsystem for Linux": "适用于 Linux 的 Windows 子系统 (WSL)",
    "Run the app against a Linux environment. Connecting relaunches the app into the selected WSL distro.": "在 Linux 环境中运行应用。连接后将重启应用并切换至所选的 WSL 分发版。",
    "Connect": "连接", "connect": "连接",
    "App version": "应用版本", "App Version": "应用版本",
    "Automatic Check for Updates": "自动检查更新",
    "Automatically prompt you to restart the app when a new update is available. When disabled, you can check for updates manually from the app menu.": "当有新更新可用时自动提示您重启应用。禁用后，您可以从应用菜单中手动检查更新。",
    "Invalid Media": "无效媒体", "invalid media": "无效媒体",
    "Maximum number of attachments reached": "已达到附件数量上限",
    "Maximum number of attachments reached.": "已达到附件数量上限。",
    "Save changes": "保存更改", "Apply": "应用", "OK": "确定", "Features": "功能",
    "Experimental Features": "实验性功能", "Enable": "启用", "Disable": "禁用",
    "API Configuration": "API 配置", "Account Settings": "账号设置", "Profile Settings": "个人资料",
    "Workspace Settings": "工作区设置", "Manage Projects": "管理项目",
    "Terminal & Tooling Permissions": "终端与工具权限",
    "Terminal Commands": "终端命令", "Configure allowed terminal commands.": "配置允许执行的终端命令。",
    "Commands Outside Sandbox": "沙盒外命令", "Configure allowed commands outside the sandbox.": "配置允许在沙盒外执行的命令。",
    "MCP Tools": "MCP 工具", "Configure external tools via Model Context Protocol.": "通过模型上下文协议配置外部工具。",
    "Allow write access to this path?": "允许对此路径写入吗？", "Yes, allow this time": "是，仅允许本次",
    "Yes, and always allow in this conversation": "是，并在本次对话中始终允许",
    "Yes, and always allow when not in a project": "是，并在非项目中始终允许",
    "Yes, and always allow": "是，始终允许", "No (tell the agent what to do instead)": "否 (告诉智能体改做什么)",
    "Skip": "跳过", "Submit": "提交",

    // Models & Usage Tab
    "Models & Usage": "模型与用量", "Manage your model quota and credits.": "管理您的模型配额和积分额度。",
    "Model Quota": "模型配额",
    "Within each group, models share a weekly limit and a 5-hour limit. Quota is consumed proportionally to the cost of the tokens. Thus, limits will last longer with shorter tasks or using more cost-effective models. The 5-hour limit smooths out aggregate demand to fairly distribute global capacity across all users, while your weekly limit is tied directly to your individual tier.": "同一组内的模型共享每周限额和 5 小时限额。配额按 Token 成本比例消耗。因此，较短的任务或性价比更高的模型能让配额使用得更久。5 小时限额用于平滑总体需求，在所有用户之间公平分配全球服务容量；每周限额则直接取决于您的套餐档位。",
    "Within each group, models share a weekly limit and a 5-hour limit.": "同一组内的模型共享每周限额和 5 小时限额。",
    "Quota is consumed proportionally to the cost of the tokens.": "配额按 Token 成本比例消耗。",
    "Thus, limits will last longer with shorter tasks or using more cost-effective models.": "因此，较短的任务或性价比更高的模型能让配额使用得更久。",
    "The 5-hour limit smooths out aggregate demand to fairly distribute global capacity across all users, while your weekly limit is tied directly to your individual tier.": "5 小时限额用于平滑总体需求，在所有用户之间公平分配全球服务容量；每周限额则直接取决于您的套餐档位。",
    "For paid Pro plans, Argon quota is separate. Higher Argon quota (included as part of the larger Gemini quota bucket) is available on Ultra plans.": "付费 Pro 套餐的 Argon 配额单独计算。Ultra 套餐可获得更高的 Argon 配额，该配额包含在更大的 Gemini 配额池中。",
    "For paid Pro plans, Argon quota is separate.": "付费 Pro 套餐的 Argon 配额单独计算。",
    "Higher Argon quota (included as part of the larger Gemini quota bucket) is available on Ultra plans.": "Ultra 套餐可获得更高的 Argon 配额，该配额包含在更大的 Gemini 配额池中。",
    "Models within this group:": "本组包含的模型：", "Models within this group": "本组包含的模型",
    "Plan": "订阅计划", "Model Credits": "模型积分", "Enable AI Credit Overages": "启用 AI 积分超额使用",
    "When toggled on, Antigravity will use your AI credits to fulfill model requests once you're out of model quota. Antigravity will always use your model quota first before using AI credits.": "启用后，当您的模型配额用尽时，Antigravity 将使用您的 AI 积分来完成模型请求。Antigravity 将始终优先使用模型配额。",
    "See Activity": "查看活动", "Get More AI Credits": "获取更多 AI 积分",
    "Available AI Credits:": "可用 AI 积分：",
    "Gemini Models": "Gemini 模型", "Claude and GPT models": "Claude 和 GPT 模型",
    "Usage": "用量", "Weekly limit": "每周限额", "5h limit": "5 小时限额",
    "Gemini 4 Argon Weekly Limit": "Gemini 4 Argon 每周限额",
    "Limited time": "限时", "Low": "低", "High": "高", "View Usage": "查看用量",
    "Notice": "提示", "notice": "提示", "Leaving Soon": "即将下线", "Leaving soon": "即将下线",
    "GPT-OSS will be removed from Antigravity on November 18, 2026.": "GPT-OSS 将于 2026 年 11 月 18 日从 Antigravity 中移除。",
    "Start using Gemini 3.8 Flash, our best Flash model.": "开始使用 Gemini 3.8 Flash，我们最强大的 Flash 模型。",
    "Sonnet 5.5 is now available on paid Pro and Ultra plans. Third-party model access will no longer be available on your current plan starting on November 2, 2026.": "Sonnet 5.5 现已在付费的 Pro 和 Ultra 方案中提供。从 2026 年 11 月 2 日起，您当前的方案将不再支持访问第三方模型。",

    // Customizations & Plugins
    "Connectors": "连接器", "Browse Connectors": "浏览连接器", "Manage": "管理",
    "No connectors available in this project": "此项目中暂无可用连接器",
    "Configure default behaviors, skills, and MCP servers.": "配置默认行为、技能和 MCP 服务器。",
    "Manage project folders and settings.": "管理项目文件夹和设置。",
    "Add Folder": "添加文件夹", "Delete Project": "删除项目",
    // React may render the project name, count, and description as separate text nodes.
    "Permanently delete": "永久删除",
    "active conversation": "个进行中的对话", "active conversations": "个进行中的对话",
    "active conversation.": "个进行中的对话。", "active conversations.": "个进行中的对话。",
    "archived conversation": "个已归档对话", "archived conversations": "个已归档对话",
    "archived conversation.": "个已归档对话。", "archived conversations.": "个已归档对话。",
    "active conversation and": "个进行中的对话和", "active conversations and": "个进行中的对话和",
    "Learn more.": "了解更多。", "Learn more": "了解更多",
    "Token Usage": "Token 使用量",
    "The breakdown below shows token usage from customizations like rules, skills, and MCP. If a budget is exceeded, large rules are demoted to path pointers and large customizations are excluded automatically.": "下方的明细展示了来自规则、技能和 MCP 等自定义项的 Token 使用情况。如果超出预算，大型规则将降级为路径指针，大型自定义项将被自动排除。",
    "The breakdown below shows token usage from customizations like skills, rules, and MCP. If the budget is exceeded, large customizations will be truncated automatically.": "下方的明细展示了来自技能、规则和 MCP 等自定义项的 Token 使用情况。如果超出预算，大型规则将降级为路径指针，大型自定义项将被自动排除。",
    "Skills": "技能", "Rules": "规则",
    "Installed MCP Servers": "已安装的 MCP 服务器",
    "Add MCP +": "添加 MCP +", "Add MCP": "添加 MCP", "Add MCP Servers": "添加 MCP 服务器", "Add MCP Server": "添加 MCP 服务器",
    "Copy Config File Path": "复制配置文件路径",
    "Search MCP servers by name": "按名称搜索 MCP 服务器",
    "Refresh": "刷新", "Refreshing...": "刷新中...", "Refreshing": "刷新中",
    "Analyzed": "已分析", "analyzed": "已分析",
    "Exploring file, editing file": "浏览文件、编辑文件",
    "Open MCP Config": "打开 MCP 配置",
    "No MCP Servers": "无 MCP 服务器",
    "You currently don't have any MCP Servers installed. Add an MCP server above or add a custom one via the MCP Config.": "您目前尚未安装任何 MCP 服务器。请在上方添加 MCP 服务器，或通过 MCP 配置添加自定义服务器。",
    "Build With Google Plugins": "使用 Google 插件构建", "Build with Antigravity Plugins": "使用 Antigravity 插件构建",
    "Customize": "自定义", "Hide breakdown": "隐藏明细",
    "coding agent": "编程智能体",
    "Search customizations...": "搜索自定义项...",
    "Google Workspace": "Google Workspace",
    "Build with Google": "使用 Google 构建",
    "Marketplace": "插件市场",
    "No plugins match your search.": "未找到匹配的插件。",
    "Featured": "精选", "Details": "详情",
    "Design, Creative & Media": "设计、创意与媒体",
    "Design, creative, and media tools.": "设计、创意和媒体工具。",
    "Productivity & Project Management": "效率与项目管理",
    "Plan work, track issues, sign documents, and manage your notes and files.": "规划工作、跟踪问题、签署文档，并管理笔记和文件。",
    "Cloud Hosting & Deployment": "云托管与部署",
    "Deploy and host your apps, sites, and their backends.": "部署和托管应用、网站及其后端。",
    "APIs, services, and tools to build, test, secure, and run your apps.": "用于构建、测试、运行应用并保障其安全的 API、服务和工具。",
    "Business": "商务",
    "Payments, CRM, accounting, data, identity, customer support, marketing, and workflow automation.": "支付、客户关系管理（CRM）、会计、数据、身份管理、客户支持、营销和工作流自动化。",
    "More Plugins": "更多插件", "Explore other marketplace customizations": "探索插件市场中的其他自定义项",
    "Installed": "已安装",
    "Find skills, agents, and more in the Marketplace.": "在插件市场中发现技能、智能体及更多内容。",
    "Browse the Marketplace": "浏览插件市场",
    "Skills & Rules": "技能与规则",
    "Built In": "内置",
    "Custom Agents": "自定义智能体",
    "No custom agents yet.": "暂无自定义智能体。",
    "MCP Servers": "MCP 服务器",
    "No MCP servers yet. Use Add to browse the store.": "暂无 MCP 服务器。请使用“添加”浏览商店。",
    "Create a Plugin with the Agent": "使用智能体创建插件",
    "See less": "收起",
    "Google Docs": "Google 文档",
    "Google Sheets": "Google 表格",
    "Google Slides": "Google 幻灯片",
    "Google Drive": "Google 云端硬盘",
    "Google Calendar": "Google 日历",
    "Gemini API": "Gemini API",
    "Android CLI": "Android CLI",
    "Data Agent Kit": "Data Agent Kit",
    "Dart and Flutter": "Dart 和 Flutter",
    "Google Maps Platform": "Google Maps Platform",
    "Core tools and knowledge required to develop for Android": "开发 Android 所需的核心工具和知识",
    "Modern Web Guidance": "现代 Web 开发指南",
    "Keep your coding agent up to date with the latest web best practices.": "让您的编程智能体掌握最新的 Web 最佳实践。",
    "Google Antigravity SDK": "Google Antigravity SDK",
    "Using the Antigravity Python SDK to build AI agents": "使用 Antigravity Python SDK 构建 AI 智能体",
    "Science": "科学", "Curated collection of agent skills for science.": "精选的科学领域智能体技能集合。",
    "Firebase": "Firebase",
    "Prototype, build & run modern apps users love with Firebase's backend, AI, and operational infrastructure.": "借助 Firebase 的后端、AI 和运营基础设施，设计原型、构建并运行深受用户喜爱的现代应用。",
    "Chrome DevTools": "Chrome 开发者工具",
    "Reliable automation, in-depth debugging, and performance analysis in Chrome using Chrome DevTools and Puppeteer": "使用 Chrome DevTools 和 Puppeteer 在 Chrome 中实现可靠的自动化、深度调试和性能分析",
    "Google Kubernetes Engine (Remote)": "Google Kubernetes Engine (远程)",

    // Command Palette & Conversation Filters
    "Search for commands...": "搜索命令...", "Search for commands…": "搜索命令…",
    "Collapse All Folders": "折叠全部文件夹", "Expand All Folders": "展开全部文件夹",
    "Open Keyboard Shortcuts": "打开键盘快捷键设置", "Download Diagnostics": "下载诊断信息",
    "Toggle Between Light/Dark Themes": "切换浅色／深色主题",
    "Close Tab": "关闭标签页",
    "Split Conversation Horizontally": "水平拆分对话", "Split Conversation Vertically": "垂直拆分对话",
    "Open Command Palette": "打开命令面板", "Open Project Picker": "打开项目选择器",
    "Toggle Project Selector": "切换项目选择器", "Toggle Environment Selector": "切换环境选择器",
    "New Terminal Tab": "新建终端标签页", "Outside of Project": "项目外",
    "Search for conversations...": "搜索对话...", "Search for conversations…": "搜索对话…",
    "Only Unread": "仅显示未读对话", "Only Archived": "仅显示已归档对话",
    "Only Automations": "仅显示自动化对话",

    // Shortcuts Panel
    "Configure keyboard shortcuts.": "配置键盘快捷键。",
    "Edit Shortcut": "编辑快捷键",
    "Remove Shortcut": "移除快捷键", "Add Shortcut": "添加快捷键",
    "Press keys...": "请按下快捷键...", "Press keys…": "请按下快捷键...",
    "No keyboard shortcuts found matching your filter.": "未找到符合筛选条件的快捷键。",
    "Search shortcuts...": "搜索快捷键...", "Search shortcuts…": "搜索快捷键…",
    "Keyboard shortcuts for quick navigation and control.": "用于快速导航和控制的键盘快捷键。",
    "RECOMMENDED": "推荐", "NAVIGATION": "导航", "Recommended": "推荐", "Navigation": "导航",
    "Open Conversation Picker": "打开对话选择器", "Open File Search": "打开文件搜索",
    "Go Back": "后退", "Go Forward": "前进",
    "New Tab": "新建标签页", "Reopen Closed Tab": "重新打开已关闭的标签页",
    "Focus Input": "聚焦输入框", "File Picker": "文件选择器",
    "Select Previous Conversation": "选择上一个对话", "Select Next Conversation": "选择下一个对话",
    "Move Conversation Up": "上移对话", "Move Conversation Down": "下移对话",
    "Previous Pane Tab": "上一个面板标签", "Next Pane Tab": "下一个面板标签",
    "Previous Side Panel Tab": "上一个侧边面板标签页", "Next Side Panel Tab": "下一个侧边面板标签页",
    "Toggle Side Panel": "切换侧边面板", "Toggle Maximize Side Panel": "切换侧边面板最大化状态",
    "Toggle Overview Panel": "切换概览面板", "Toggle Terminal": "切换终端",
    "Archive This Conversation": "归档当前对话",
    "Toggle Model Selector": "切换模型选择器", "Toggle Voice Recording": "切换语音录制",
    "Find in Pane": "在面板中查找", "Add to Chat/Quote": "添加到对话/引用",
    "LAYOUT CONTROLS": "布局控制", "Layout Controls": "布局控制", "Layout controls": "布局控制",
    "App Shortcuts": "应用快捷键", "Editor Shortcuts": "编辑器快捷键", 
    "Global Shortcuts": "全局快捷键", "Terminal Shortcuts": "终端快捷键", 
    "Chat Shortcuts": "对话快捷键", "Press desired key combination": "按下所需的组合键",

    // Feedback Panel
    "Feedback Type": "反馈类型", "Auth and Billing": "认证与计费", "Description": "描述",
    "Please describe the issue in detail. The more actionable your feedback, the quicker our team can address your request. Some helpful information includes:": "请详细描述您的问题。您的反馈越具体，我们的团队就能越快处理您的请求。一些有用的信息包括：",
    "Steps to reproduce the issue": "重现问题的步骤", "Expected behavior": "预期行为",
    "Actual behavior": "实际行为", "Any error messages": "任何错误消息", "Any relevant information": "任何相关信息",
    "Describe the bug you encountered...": "描述您遇到的错误...",
    "Describe the bug you encountered…": "描述您遇到的错误...",
    "Please describe the feature you'd like to see. The more detailed the requirements, the easier it will be for our team to incorporate your ideas. Some helpful information includes:": "请描述您希望增加的功能。需求描述越详细，我们的团队就越容易实现您的想法。建议提供以下信息：",
    "Please describe the feature you'd like to see.": "请描述您希望增加的功能。",
    "The more detailed the requirements, the easier it will be for our team to incorporate your ideas.": "需求描述越详细，我们的团队就越容易实现您的想法。",
    "Some helpful information includes:": "建议提供以下信息：",
    "What is missing in your workflow": "您的工作流程中缺少什么",
    "What you would like to see to address this gap in your workflow": "您希望增加哪些功能来弥补工作流程中的不足",
    "How this feature would help you and other users": "这项功能将如何帮助您和其他用户",
    "Describe the feature you would like to see...": "描述您希望增加的功能...",
    "Describe the feature you would like to see…": "描述您希望增加的功能...",
    "Please describe your auth or billing issue. More details will help our support team resolve your issue quicker. Some helpful information includes:": "请描述您遇到的身份验证或计费问题。提供更多细节有助于支持团队更快地解决问题。建议提供以下信息：",
    "Please describe your auth or billing issue.": "请描述您遇到的身份验证或计费问题。",
    "More details will help our support team resolve your issue quicker.": "提供更多细节有助于支持团队更快地解决问题。",
    "What quota or feature is being incorrectly limited": "哪项配额或功能被错误限制",
    "What functionality you expect your account tier to have available that is missing": "您认为当前账号套餐应包含、但实际缺失的功能",
    "Any error messages seen when trying to log in": "尝试登录时出现的错误信息",
    "Describe your auth or billing issue...": "描述您遇到的身份验证或计费问题...",
    "Describe your auth or billing issue…": "描述您遇到的身份验证或计费问题...",
    "Use this form if you cannot connect to Remote Control. If your instance is already connected and you are experiencing issues in the browser, report directly from the Remote Control web page so that relevant logs are included. Some helpful information includes:": "如果无法连接远程控制，请使用此表单。如果您的实例已连接，但在浏览器中遇到问题，请直接通过远程控制网页反馈，以便附带相关日志。建议提供以下信息：",
    "Use this form if you cannot connect to Remote Control.": "如果无法连接远程控制，请使用此表单。",
    "If your instance is already connected and you are experiencing issues in the browser, report directly from the Remote Control web page so that relevant logs are included.": "如果您的实例已连接，但在浏览器中遇到问题，请直接通过远程控制网页反馈，以便附带相关日志。",
    "Whether it never connects or is intermittent/flaky": "是始终无法连接，还是连接时断时续、不稳定",
    "Did restarting the desktop app help?": "重启桌面应用后是否有所改善？",
    "Describe your Remote Control issue...": "描述您遇到的远程控制问题...",
    "Describe your Remote Control issue…": "描述您遇到的远程控制问题...",
    "For any feedback that does not fit into the above categories.": "适用于不属于上述类别的其他反馈。",
    "Enter your feedback here...": "在此输入您的反馈...", "Enter your feedback here…": "在此输入您的反馈...",
    "Steps to Reproduce": "重现步骤", "Please list the steps to reproduce the issue...": "请列出重现问题的步骤...",
    "Please list the steps to reproduce the issue": "请列出重现问题的步骤",
    "Attach a screenshot (optional)": "附加截图（可选）", "Attach Antigravity server logs": "附加 Antigravity 服务器日志",
    "We recommend attaching logs. Attaching logs will help the Antigravity team act on and prioritize your feedback.": "建议附加日志。日志有助于 Antigravity 团队处理您的反馈，并确定处理优先级。",
    "We recommend attaching logs.": "建议附加日志。",
    "Attaching logs will help the Antigravity team act on and prioritize your feedback.": "日志有助于 Antigravity 团队处理您的反馈，并确定处理优先级。",
    "We'd love to hear from you.": "我们期待您的反馈。", "How can we improve?": "我们该如何改进？",
    "Thinking...": "思考中...", "Thought": "思考过程", "Agent is thinking...": "智能体正在思考...",
    "Show thought process": "显示思考过程", "Hide thought process": "隐藏思考过程",
    "Generating...": "生成中...", "Planning...": "计划中...",
    "Issue Type": "问题类型", "Bug Report": "错误报告", "Feature Request": "功能请求",
    "Remote Control Issue": "远程控制问题", "Remote control issue": "远程控制问题",
    "Legal Help": "法律帮助", "legal help": "法律帮助",
    "Visit Legal Help to ask for content changes for legal reasons.": "访问法律帮助以出于法律原因请求更改内容。",
    "Visit Legal Help to ask for content changes for legal reasons": "访问法律帮助以出于法律原因请求更改内容",
    "to ask for content changes for legal reasons.": "以出于法律原因请求更改内容。",
    "to ask for content changes for legal reasons": "以出于法律原因请求更改内容",
    "General Feedback": "常规反馈", "Describe your issue or idea...": "描述您的问题或想法...",
    "Please provide details...": "请提供详细信息...", "Include diagnostic data": "包含诊断数据",
    "Include app logs": "包含应用日志", "Send Feedback": "发送反馈",

    // Browser Tab
    "Extensions": "插件", "No extensions available": "暂无可用插件",
    "Search or enter a URL": "搜索或输入网址",
    "Built-in Browser": "内置浏览器",
    "Configure link opening and built-in browser preferences.": "配置链接打开方式和内置浏览器偏好设置。",
    "Open Links In": "链接打开方式",
    "Choose where links open by default when clicked.": "选择点击链接时默认使用的浏览器。",
    "External Browser": "外部浏览器", "Download Location": "下载位置",
    "Folder where files downloaded in the built-in browser are saved.": "内置浏览器下载文件的保存文件夹。",
    "Change...": "更改...", "Change…": "更改…", "Browsing History": "浏览历史记录",
    "Clear visited URLs and autocomplete suggestions from the built-in browser.": "清除内置浏览器中访问过的网址和自动补全建议。",
    "Browser Subagent": "浏览器子智能体",
    "Browser Settings": "浏览器设置", "Configure the browser subagent. It requires": "配置浏览器子智能体。需要安装",
    "to be installed. The browser subagent can be invoked by typing /browser in the conversation input box.": "。您可以在对话输入框中输入 /browser 来调用浏览器子智能体。",
    "Browser Javascript Execution Policy": "浏览器 JavaScript 执行策略",
    "Controls whether the agent can run custom JavaScript to automate complex browser actions.": "控制智能体是否可以运行自定义 JavaScript 来自动化复杂的浏览器操作。",
    "Disabled": "已禁用", "Block all browser JavaScript execution.": "阻止所有浏览器 JavaScript 执行。",
    "Request Review": "请求审阅", "Prompt for approval before running browser scripts.": "在运行浏览器脚本前提示批准。",
    "Allow full browser script execution without prompting.": "允许执行完整的浏览器脚本而不提示。",
    "Actuation Permissions": "操作权限", "Browser Actuation Rules": "浏览器操作规则",
    "Configure allowed and denied URLs for browser actuation.": "配置允许和拒绝进行浏览器操作的 URL。",

    // Voice Mode
    "Voice mode": "语音模式", "Microphone": "麦克风",
    "Start Voice mode": "开启语音模式",
    "Voice chat": "语音对话", "Connecting...": "正在连接...", "Connecting…": "正在连接…",
    "End": "结束", "Listening. Ask anything.": "正在聆听，请尽管提问。",
    "Listening.": "正在聆听，", "Ask anything.": "请尽管提问。",
    "Mute mic": "将麦克风静音", "Mute Antigravity": "将 Antigravity 静音",
    "Voice speed": "语速", "Voice speed,": "语速，",
    "Mute Voice Mic": "将语音模式麦克风静音", "Mute Voice Speaker": "将语音模式扬声器静音",
    "Voice": "音色", "Not set": "未设置", "Change": "更改",
    "The voice used in Voice mode. Powered by Gemini Live.": "语音模式使用的音色。由 Gemini Live 提供支持。",
    "The voice used in Voice mode.": "语音模式使用的音色。", "Powered by Gemini Live.": "由 Gemini Live 提供支持。",
    "Powered by Gemini Live · You can change this in Settings later.": "由 Gemini Live 提供支持 · 您可以稍后在设置中更改。",
    "Powered by Gemini Live · You can change this in 设置 later.": "由 Gemini Live 提供支持 · 您可以稍后在设置中更改。",
    "How loud Antigravity's voice is.": "设置 Antigravity 的语音音量。",
    "Choose Antigravity's Voice": "选择 Antigravity 的音色", "Choose Antigravity’s Voice": "选择 Antigravity 的音色",
    "Clear and friendly": "清晰亲切", "Confident and clear": "自信清晰",
    "Warm and engaging": "温暖且富有感染力", "Warm and approachable": "温暖亲和",
    "Deep and velvety": "低沉柔滑", "Light and precise": "轻柔精准",
    "Input device for voice mode and dictation.": "用于语音模式和听写的输入设备。",
    "System default": "跟随系统",

    // Notifications
    "Manage your notification preferences.": "管理通知偏好设置。",
    "Enable Notifications for Agent": "启用智能体通知",
    "Show system notifications when your action is needed or the agent finishes.": "在需要您操作或智能体完成任务时显示系统通知。",
    "Sound": "声音", "Enable Sounds for Agent": "启用智能体提示音",
    "Play a sound when your action is needed or the agent finishes.": "在需要您操作或智能体完成任务时播放提示音。",
    "Volume": "音量", "Set the volume of agent sounds.": "设置智能体提示音的音量。",

    // App Tab
    "App Settings": "应用设置", "Manage application settings.": "管理应用设置。",
    "Prevent Sleep": "阻止睡眠", "Prevent the computer from sleeping while the app is running.": "在应用运行时阻止计算机进入睡眠状态。",
    "Keep In Menu Bar": "保留在系统托盘", 
    "The app will be accessible from the menu bar and will keep running in the background when all windows are closed.": "应用将可以从系统托盘访问，并在所有窗口关闭时继续在后台运行。",
    "Keep the app accessible from the menu bar and running in the background when all windows are closed.": "应用将可以从系统托盘访问，并在所有窗口关闭时继续在后台运行。",
    "Notification Settings": "通知设置", "To modify notification settings, open your operating system's system preferences.": "要修改通知设置，请打开操作系统的系统偏好设置。",
    "Open System Preferences": "打开系统偏好设置",

    // Conversations Tab & Permissions
    "Agent settings and permissions for conversations outside of projects.": "针对项目外对话的智能体设置和权限。",
    "Settings for conversations outside of projects.": "项目外对话的设置。",
    "Inherit General": "继承全局设置", "Local Permissions": "本地权限",
    "Also includes": "还包括", "global settings": "全局设置",
    "when working in this project.": "（当在此项目中工作时）。",
    "Toggle Sidebar": "切换侧边栏", "View Split Diff": "分屏查看差异", "Collapse All": "全部折叠",
    "Toggle sidebar": "切换侧边栏",
    "Learn more about": "了解更多关于",
    "Configure the agent's visual theme and display preferences.": "配置智能体的视觉主题和显示偏好。",
    "Chat Settings": "聊天设置", "Verbose Agent Chat": "详细的智能体对话",
    "Conversation Steps": "对话步骤", "Verbose": "详细",
    "Choose how much detail is shown during a conversation.": "选择对话过程中显示的详细程度。",
    "Display and preserve intermediate thinking steps.": "显示并保留中间思考过程。",
    "Conversation Width": "对话宽度", "Configure the maximum width of the conversation panel.": "配置对话面板的最大宽度。",
    "Chat Width": "对话宽度", "Narrow": "较窄", "Wide": "较宽", "Fill": "铺满",
    "Accessibility": "辅助功能", "Screen Reader Mode": "屏幕阅读器模式",
    "Optimize the interface and terminal output for screen readers.": "针对屏幕阅读器优化界面和终端输出。",
    "Select light, dark, or inherit system settings.": "选择浅色、深色，或跟随系统设置。",
    "Light Theme": "浅色主题", "Preset": "预设", "Default Light": "默认浅色",
    "Background": "背景颜色", "Foreground": "前景颜色", "Accent": "强调色",
    "Dark Theme": "深色主题", "Default Dark": "默认深色",
    "Legacy Dark": "旧版深色",
    "Allow write access to this path?": "允许写入此路径吗？",
    "Allow read access to this path?": "允许读取此路径吗？",
    "Allow execution of this command?": "允许执行此命令吗？",
    "Yes, allow this time": "是，仅本次允许",
    "Yes, and always allow in this conversation": "是，在本次对话中始终允许",
    "Yes, and always allow when not in a project": "是，在未分组项目中始终允许",
    "Yes, and always allow": "是，始终允许",
    "tell the agent what to do instead": "告诉智能体接下来该做什么",
    "(tell the agent what to do instead)": "(告诉智能体接下来该做什么)",
    "Skip": "跳过", "Working.": "运行中。", "Working...": "运行中...",
    "Edited": "已编辑", "Viewed": "已查看", "Created": "已创建", "Deleted": "已删除", "Executed": "已执行",
    "Save rule to always allow write access to this path?": "保存规则以始终允许写入此路径吗？",
    "Save rule to always allow read access to this path?": "保存规则以始终允许读取此路径吗？",
    "Save rule to always allow execution of this command?": "保存规则以始终允许执行此命令吗？",
    "Yes, save rule in this conversation": "是，在本次对话中保存规则",
    "Yes, save rule when not in a project": "是，在未分组项目中保存规则",
    "Yes, save rule globally": "是，全局保存规则",

    // Error & Diagnostics UI
    "Our servers are experiencing high traffic right now, please try again in a minute.": "我们的服务器当前负载较高，请稍后重试。",
    "Error ID:": "错误 ID：",
    "Agent terminated due to error": "智能体因错误而终止",
    "Agent execution terminated due to error.": "智能体执行因错误而终止。",
    "Agent execution terminated due to error": "智能体执行因错误而终止",
    "You can prompt the model to try again or start a new conversation if the error persists.": "您可以提示模型重试，或者如果错误仍然存在，可以开启新的对话。",
    "See our troubleshooting guide for more help.": "查看我们的排查指南以获取更多帮助。",
    "See our troubleshooting guide for more help": "查看我们的排查指南以获取更多帮助",
    "troubleshooting guide": "排查指南", "troubleshooting_guide": "排查指南",
    "See our": "查看我们的",
    "for more help.": "以获取更多帮助。", "for more help": "以获取更多帮助",
    "Dismiss": "忽略", "Copy debug info": "复制调试信息",

    // Remote Control Feature & Prompts
    "Try Remote Control": "尝试远程控制",
    "Remote Control": "远程控制",
    "Kick off work on your computer and continue working with your agents from your phone or another device. Turn on Remote Control in app settings.": "在电脑上启动工作，并可以通过手机或其他设备继续与智能体协同工作。请在应用设置中开启“远程控制”。",
    "Kick off work on your computer and continue working with your agents from your phone or another device.": "在电脑上启动工作，并可以通过手机或其他设备继续与智能体协同工作。",
    "Turn on Remote Control in app settings.": "请在应用设置中开启“远程控制”。",
    "Turn on Remote Control in app settings": "请在应用设置中开启“远程控制”"
  };

  const voicePresetNames = new Set(['Fola', 'Arlo', 'Cleo', 'Finn', 'Gero', 'Lora', 'Neno', 'Olin', 'Tari']);

  const projectDeletionPromptRules = [
    {
      pattern: /^(Are you sure you want to delete the\s+(?:[Pp]roject|项目)\s+|确定要删除项目“)([\s\S]+?)(”吗？|\?|？)$/,
      prefix: '确定要删除项目“', suffix: '”吗？'
    },
    {
      pattern: /^(This will permanently delete\s+|这将永久删除其中的\s*)(\d+)(\s*(?:active conversations?|个进行中的对话)\s+within it\.|\s*个进行中的对话。)$/,
      prefix: '这将永久删除其中的 ', suffix: ' 个进行中的对话。'
    }
  ];
  const projectDeletionValueOwners = new WeakMap();

  function matchProjectDeletionPrompt(text) {
    for (const rule of projectDeletionPromptRules) {
      const match = text.match(rule.pattern);
      if (match) return {prefix: rule.prefix, suffix: rule.suffix, value: match[2], offset: match[1].length};
    }
    return null;
  }

  const inlineNoticeRules = [
    {
      source: ['Powered by Gemini Live · You can change this in', 'Settings', 'later.'],
      target: ['由 Gemini Live 提供支持 · 您可以稍后在', '设置', '中更改。']
    },
    {
      source: ['By using this app, you agree to its', 'Terms of Service', ''],
      target: ['使用本应用即表示您同意其', '服务条款', '']
    }
  ];

  const cloudResourceNoticeSentences = [
    "Avoid uploading highly sensitive data and verify actions taken by your agent.",
    "Make sure you have the necessary rights to any content or files that you upload, including content of minors.",
    "Don't generate content that infringes on others' rights, including content that deceives, harasses, or harms.",
    "When using Antigravity, you must comply with Google's Prohibited Use Policy.",
    "Your use is subject to the Google Antigravity Terms of Service and Google Privacy Policy."
  ];
  const cloudResourceNoticeLinks = [
    'necessary rights', 'Prohibited Use Policy',
    'Google Antigravity Terms of Service', 'Google Privacy Policy'
  ];

  function splitLinkedNotice(text, labels) {
    const parts = [];
    let offset = 0;
    for (const label of labels) {
      const index = text.indexOf(label, offset);
      if (index === -1) return null;
      parts.push(text.slice(offset, index), label);
      offset = index + label.length;
    }
    parts.push(text.slice(offset));
    return parts;
  }
  const cloudResourceNoticeSources = splitLinkedNotice(
    cloudResourceNoticeSentences.join(' '), cloudResourceNoticeLinks);
  const cloudResourceNoticeTargets = splitLinkedNotice(
    cloudResourceNoticeSentences.map(sentence => dictionary[sentence]).join(''),
    cloudResourceNoticeLinks.map(label => dictionary[label]));

  const coreWords = {
    "create": "创建", "delete": "删除", "new": "新建", "edit": "编辑", "save": "保存", "cancel": "取消", "confirm": "确认",
    "close": "关闭", "open": "打开", "stop": "停止", "start": "启动", "run": "运行", "add": "添加", "remove": "移除", "download": "下载",
    "update": "更新", "select": "选择", "clear": "清除", "search": "搜索", "find": "查找", "view": "查看", "show": "显示", "hide": "隐藏",
    "copy": "复制", "paste": "粘贴", "cut": "剪切", "rename": "重命名", "duplicate": "制作副本",
    "agent": "智能体", "agents": "智能体", "subagent": "子智能体", "subagents": "子智能体", "task": "任务", "tasks": "任务",
    "workspace": "工作区", "workspaces": "工作区", "directory": "目录", "folder": "文件夹", "file": "文件", "files": "文件",
    "command": "命令", "commands": "命令", "terminal": "终端", "console": "控制台", "output": "输出", "input": "输入",
    "error": "错误", "warning": "警告", "info": "信息", "success": "成功", "failed": "失败", "pending": "等待中", "running": "运行中",
    "yes": "是", "no": "否", "true": "真", "false": "假", "on": "开", "off": "关", "enable": "启用", "disable": "禁用",
    "global": "全局", "retry": "重试", "regenerate": "重新生成", "dismiss": "忽略",
    "allow": "允许", "ask": "询问", "deny": "拒绝", "split": "分屏", "notice": "提示"
  };

  // Verified marketplace descriptions; match the full text or an unambiguous truncated prefix.
  const marketplaceDescriptionRules = [
    // Canva
    ["Create, edit, review, resize, and brand-check Canva designs with the Canva MCP server.","通过 Canva MCP 服务器创建、编辑、审阅 Canva 设计，调整尺寸并检查品牌规范。"],
    // Figma
    ["Turn Figma designs into production code, map components with Code Connect, and create or edit Figma files in Antigravity.","将 Figma 设计转化为生产代码，通过 Code Connect 映射组件，并在 Antigravity 中创建或编辑 Figma 文件。"],
    // Mobbin
    ["Give your AI agent 600,000+ real app screens, and the skills to use them. Includes the Mobbin MCP and a skill that redesigns your screen from patterns real apps ship, in your own design system, with the references behind every change.","为您的 AI 智能体提供超过 60 万个真实应用界面及相关使用技能。包含 Mobbin MCP 和界面重设计技能，可参考真实应用的设计模式，在您自己的设计系统中重新设计界面，并为每项更改提供参考依据。"],
    // Atlassian Teamwork Graph CLI
    ["Teamwork Graph CLI is Atlassian's agent-first interface to your entire work context: Jira issues, Confluence pages, Bitbucket PRs, along with your connected third-party data sources. Purpose-built for coding agents like Antigravity (terminal or desktop), and powered by Atlassian's context graph. Try: \"draft a Jira issue from this PR and link it to the epic.\" Run /twg-setup after install to connect Atlassian Teamwork Graph CLI to Antigravity.","Teamwork Graph CLI 是 Atlassian 面向智能体的工作上下文接口，涵盖 Jira 问题、Confluence 页面、Bitbucket 拉取请求及已连接的第三方数据源。专为 Antigravity 等编程智能体设计，支持终端和桌面端，并由 Atlassian 上下文图谱提供支持。例如：“根据此拉取请求起草 Jira 问题，并关联到对应的 Epic。”安装后运行 `/twg-setup`，将其连接到 Antigravity。"],
    // Dropbox
    ["Connect Antigravity to Dropbox to search, inspect, summarize, share, collect uploads, organize folders, and clean up files with confirmation for write actions.","将 Antigravity 连接到 Dropbox，搜索、查看、总结和共享文件，收集上传内容、整理文件夹并清理文件；写入操作需要确认。"],
    // Linear
    ["The product development system for teams and agents. Manage issues, projects, and documents across your Linear workspace from Antigravity.","面向团队和智能体的产品开发系统。在 Antigravity 中管理 Linear 工作区内的问题、项目和文档。"],
    // monday.com
    ["Plan and track work in monday.com from Antigravity: create, update and assign items, write docs, and build forms that turn requests into items.","在 Antigravity 中规划和跟踪 monday.com 工作：创建、更新和分配工作项，编写文档，以及创建可将请求转化为工作项的表单。"],
    // Notion
    ["Connect Antigravity to your Notion workspace with the Notion MCP server, plus skills for research, documentation, meeting prep, specs, trackers, and project updates.","通过 Notion MCP 服务器将 Antigravity 连接到您的 Notion 工作区，并提供研究、文档编写、会议准备、规格说明、跟踪记录和项目动态更新等技能。"],
    // PandaDoc
    ["Create and send proposals, quotes, and contracts for e-signature. Track signing progress and identify documents that need follow-up.","创建并发送方案、报价单和合同以进行电子签名，跟踪签署进度，并找出需要跟进的文档。"],
    // Trello
    ["Official Trello plugin with the Trello MCP server and a skill for boards, lists, cards, checklists, Inbox, and Planner.","Trello 官方插件，包含 Trello MCP 服务器，以及用于管理看板、列表、卡片、检查清单、收件箱和规划器的技能。"],
    // Netlify
    ["Build and deploy on Netlify: functions, edge functions, blobs, database, identity, forms, image CDN, caching, and AI Gateway, plus the Netlify MCP server.","在 Netlify 上构建和部署，支持函数、边缘函数、Blob 存储、数据库、身份认证、表单、图片 CDN、缓存和 AI 网关，并提供 Netlify MCP 服务器。"],
    // Railway
    ["Deploy, configure, monitor, and troubleshoot apps, databases, and infrastructure on Railway from Antigravity with Railway's agent skill and hosted MCP server.","通过 Railway 智能体技能和托管 MCP 服务器，在 Antigravity 中部署、配置、监控和排查 Railway 上的应用、数据库及基础设施。"],
    // Vercel
    ["Build and deploy web apps and AI agents on Vercel with skills for Next.js, AI SDK, and cloud services, plus the official Vercel MCP server.","在 Vercel 上构建和部署 Web 应用及 AI 智能体，提供 Next.js、AI SDK 和云服务相关技能，以及 Vercel 官方 MCP 服务器。"],
    // Wix
    ["Build Wix apps and headless sites, and manage Wix stores, bookings, CMS and more, with Wix CLI skills and the official Wix MCP server.","通过 Wix CLI 技能和官方 MCP 服务器，构建 Wix 应用及无头网站，并管理 Wix 商店、预约、内容管理系统等功能。"],
    // WordPress
    ["Build, publish, and manage WordPress.com and Jetpack-connected sites. Draft posts, edit blocks, check traffic stats, moderate comments, and manage plugins.","构建、发布和管理 WordPress.com 网站及已连接 Jetpack 的网站。起草文章、编辑区块、查看流量统计、审核评论并管理插件。"],
    // Auth0
    ["Add Auth0 authentication to any app: login, MFA, SSO, Organizations, RBAC, custom domains, and branding. Debug auth errors and migrate from other providers.","为应用集成 Auth0 身份认证，支持登录、多因素认证（MFA）、单点登录（SSO）、组织管理、基于角色的访问控制（RBAC）、自定义域名和品牌设置。排查认证错误，并从其他服务提供商迁移。"],
    // Base44
    ["Build and deploy Base44 full-stack apps: CLI project management, JavaScript/TypeScript SDK development, and production troubleshooting skills.","构建和部署 Base44 全栈应用，提供 CLI 项目管理、JavaScript／TypeScript SDK 开发和生产环境故障排查技能。"],
    // Browserbase
    ["Give your agent a real browser: navigate, click, type, screenshot, and extract data from any site, locally or on Browserbase cloud browsers.","为智能体提供真实浏览器，可在本地或 Browserbase 云浏览器中访问网站、点击、输入、截图并提取数据。"],
    // CodeRabbit
    ["AI-powered code review and review-comment autofix, powered by CodeRabbit.","由 CodeRabbit 提供支持的 AI 代码审查，以及针对审查意见的自动修复。"],
    // Context7
    ["Up-to-date documentation lookup. Pull version-specific documentation and code examples directly from source repositories into your LLM context.","查询最新文档，直接从源码仓库获取指定版本的文档和代码示例，并加入大语言模型的上下文。"],
    // CrowdStrike Falcon
    ["Use the official CrowdStrike-hosted MCP server to work across Falcon: detections, cases, threat intel, SIEM, hosts, vulnerabilities, cloud, and more.","通过 CrowdStrike 官方托管的 MCP 服务器使用 Falcon，处理检测结果、安全事件、威胁情报、SIEM、主机、漏洞和云环境等内容。"],
    // Datadog
    ["Use Datadog directly in Antigravity through a preconfigured Datadog MCP server. Query logs, metrics, traces, dashboards, and more through natural conversation. This plugin is in preview.","通过预配置的 Datadog MCP 服务器，直接在 Antigravity 中使用 Datadog。通过自然对话查询日志、指标、追踪记录、仪表板等内容。此插件目前处于预览阶段。"],
    // Dynatrace
    ["Investigate production issues with real Dynatrace data: problems and root causes, logs, metrics, traces, and vulnerabilities, via skills and the MCP server.","通过技能和 MCP 服务器，使用真实的 Dynatrace 数据调查生产环境问题，包括问题及根本原因、日志、指标、追踪记录和漏洞。"],
    // Endor Labs Agent Kit
    ["Packaged workflows for SCA remediation, AI SAST triage, CI/CD posture, malware response, findings review, Endor Labs setup, and more.","提供用于 SCA 问题修复、AI SAST 问题分诊、CI/CD 安全态势、恶意软件响应、发现项审查和 Endor Labs 配置等任务的工作流。"],
    // Exabeam Agentic SOC
    ["Triage Exabeam New-Scale alerts and cases end to end: gather the evidence, map MITRE, reach a verdict, and record it behind an approval step.","对 Exabeam New-Scale 警报和安全事件进行端到端分诊：收集证据、映射 MITRE、得出判定，并在审批后记录结果。"],
    // Harness
    ["Build and debug pipelines, manage deployments, investigate security findings, and operate Harness with connected tools and reusable workflow skills.","通过已连接的工具和可复用工作流技能，构建与调试流水线、管理部署、调查安全发现项并操作 Harness。"],
    // Keenable
    ["Search the web and read any page as clean markdown with Keenable, a search engine built for AI agents. Keyless: no signup or API key needed.","使用专为 AI 智能体构建的 Keenable 搜索引擎搜索网页，并以简洁的 Markdown 格式读取页面。无需注册或 API 密钥。"],
    // Keenable SELECT
    ["Ask a question of the live web and get a table back. Keenable SELECT runs many searches, reads the pages and extracts the fields you need in one call. Sign in with a Keenable account.","向实时互联网提问并获得表格结果。Keenable SELECT 可在一次调用中执行多次搜索、读取页面并提取所需字段。使用 Keenable 账户登录。"],
    // Leapwork Play
    ["Create, run and debug Leapwork Play tests and runlists, build agents, and hand work to Play's AI workflows, right from Antigravity.","直接在 Antigravity 中创建、运行和调试 Leapwork Play 测试及运行列表，构建智能体，并将工作交给 Play 的 AI 工作流处理。"],
    // MongoDB Atlas (Managed MCP)
    ["Official Antigravity plugin for MongoDB Atlas (hosted MCP Server + Skills). Connect to the MongoDB-hosted Atlas MCP server, explore data, manage collections, optimize queries, generate reliable code, implement best practices, develop advanced features, and more.","MongoDB Atlas 的 Antigravity 官方插件，包含托管 MCP 服务器和技能。连接 MongoDB 托管的 Atlas MCP 服务器，探索数据、管理集合、优化查询、生成可靠代码、落实最佳实践并开发高级功能。"],
    // Parallel
    ["Search the live web and fetch page content with Parallel's hosted MCP server. Free access with no Parallel account, API key, or Parallel CLI required.","通过 Parallel 托管的 MCP 服务器搜索实时网页并获取页面内容。可免费使用，无需 Parallel 账户、API 密钥或 Parallel CLI。"],
    // PingOne
    ["Agent plugin for PingOne multi-tenant. Includes skills and a remote MCP server that lets AI agents configure and monitor your PingOne environments.","面向 PingOne 多租户环境的智能体插件。包含技能和远程 MCP 服务器，使 AI 智能体能够配置和监控您的 PingOne 环境。"],
    // Postman
    ["Equip Antigravity with specialized Postman skills for the complete API lifecycle. Discover, design, test, document, mock, monitor, and improve APIs through agent-friendly, filesystem-first workflows.","为 Antigravity 提供覆盖 API 完整生命周期的专用 Postman 技能。通过便于智能体使用、优先基于文件系统的工作流，完成 API 发现、设计、测试、文档编写、模拟、监控和改进。"],
    // Qodo
    ["Set up Qodo, explore code and repository history, review local changes, and resolve pull-request findings directly from Antigravity.","直接在 Antigravity 中配置 Qodo、浏览代码及仓库历史、审阅本地更改，并解决拉取请求审查中发现的问题。"],
    // SentinelOne Purple AI
    ["Query your SentinelOne Singularity Console from Antigravity through a self-hosted, read-only Purple AI MCP server. Requires an active console deployment, your console URL, and an API token.","通过自行托管的只读 Purple AI MCP 服务器，在 Antigravity 中查询 SentinelOne Singularity 控制台。需要已部署且可用的控制台、控制台 URL 和 API 令牌。"],
    // Sentry
    ["Set up Sentry monitoring, investigate production errors, and configure alerts and releases with expert skills and live context from your Sentry projects.","利用专业技能和 Sentry 项目的实时上下文，配置 Sentry 监控、调查生产环境错误，以及设置警报和版本发布。"],
    // Supabase
    ["Official Supabase plugin for Antigravity with Supabase skills and MCP access for project management, database work, auth, storage, and Postgres best practices.","Supabase 的 Antigravity 官方插件，提供 Supabase 技能和 MCP 访问，支持项目管理、数据库操作、身份认证、存储及 Postgres 最佳实践。"],
    // Superpowers
    ["Make your coding agent a better engineer","让您的编程智能体成为更出色的工程师。"],
    // Unity
    ["Unity's official plugin for Antigravity, with curated skills for game development, monetization, and performance optimization.","Unity 的 Antigravity 官方插件，提供游戏开发、商业变现和性能优化相关的精选技能。"],
    // VirusTotal
    ["Investigate files, URLs, domains and IP addresses with VirusTotal threat intelligence, analysis and submission recovery.","借助 VirusTotal 的威胁情报、分析和提交记录恢复功能，调查文件、URL、域名及 IP 地址。"],
    // Bigin
    ["Manage your Bigin CRM from Antigravity: review pipelines, find contacts and deals, log calls, plan follow-ups, and email customers.","在 Antigravity 中管理 Bigin CRM：查看销售流程、查找联系人和交易、记录通话、规划跟进并向客户发送邮件。"],
    // Databricks
    ["Databricks skills for the CLI, Apps, Lakebase, Model Serving, Lakeflow Jobs, Spark Declarative Pipelines, Declarative Automation Bundles (DABs), and classic-to-serverless migration.","提供 Databricks CLI、Apps、Lakebase、模型服务、Lakeflow Jobs、Spark 声明式流水线、声明式自动化包（DAB）以及从传统模式迁移至无服务器模式的相关技能。"],
    // Intercom
    ["Search Intercom conversations, contacts, and companies, spot support trends, and install the Intercom Messenger with secure identity verification.","搜索 Intercom 对话、联系人和公司，发现客户支持趋势，并安装支持安全身份验证的 Intercom Messenger。"],
    // Semrush
    ["SEO workflows on live Semrush data: keyword research, site audits, backlinks, competitor, traffic and market analytics, PPC, and AI brand visibility.","基于实时 Semrush 数据的搜索引擎优化（SEO）工作流，涵盖关键词研究、网站审计、反向链接、竞争对手分析、流量与市场分析、按点击付费广告（PPC）和 AI 品牌可见度。"],
    // Stripe
    ["Accept payments and grow your business. Stripe's official MCP server enables AI agents to manage customers, products, prices, payment links, invoices, subscriptions, and refunds, as well as search Stripe documentation.","接受付款并拓展业务。Stripe 官方 MCP 服务器使 AI 智能体能够管理客户、产品、价格、支付链接、发票、订阅和退款，并搜索 Stripe 文档。"],
    // Wispr Flow
    ["Search and read your Wispr Flow meeting notes, transcripts, scratchpad notes, and calendar events. Read-only access to your own account.","搜索和读取您的 Wispr Flow 会议笔记、转录文本、草稿笔记和日历事件。仅提供对您本人账户的只读访问。"],
    // Zapier
    ["Connect 9,000+ apps to your AI workflow. Discover, enable, and execute Zapier actions and workflows directly from your client.","将超过 9,000 个应用连接到 AI 工作流，直接从客户端发现、启用和执行 Zapier 操作及工作流。"],
    // Zoho Books
    ["Run Zoho Books from Antigravity: invoicing, bills, banking, journals, projects, items, taxes, customization and automation.","在 Antigravity 中操作 Zoho Books，处理开票、账单、银行业务、日记账、项目、商品、税务、自定义设置和自动化。"],
    // Zoho CRM
    ["Build on Zoho CRM v8: REST API, Deluge functions, ClientScript, widgets, COQL and connections, with live CRM data through your Zoho MCP server.","基于 Zoho CRM v8 开发，支持 REST API、Deluge 函数、ClientScript、小部件、COQL 和连接，并通过 Zoho MCP 服务器使用实时 CRM 数据。"],
    // Zoho Desk
    ["Zoho Desk plugin for Antigravity. Review, prioritize, and update Zoho Desk tickets directly from Antigravity through Zoho Desk MCP and includes a Ticket Prioritization Agent for triage and priority updates.","Zoho Desk 的 Antigravity 插件。通过 Zoho Desk MCP 直接审阅工单、确定优先级并更新工单，另含用于工单分诊和优先级更新的智能体。"],
    // Zoho Projects
    ["Connect Zoho Projects to Antigravity to turn tasks and issues into working code. Access project context, investigate bugs, and update work items as you develop.","将 Zoho Projects 连接到 Antigravity，把任务和问题转化为可运行的代码。在开发过程中获取项目上下文、调查缺陷并更新工作项。"],
    // Looker
    ["Connect to your managed Looker MCP server to explore data, run saved Looks, build dashboards, and validate LookML.","连接到您托管的 Looker MCP 服务器，探索数据、运行已保存的 Looks、构建仪表板并验证 LookML。"],
  ];

  // Preserve links by translating the privacy notice one sentence at a time.
  const marketplacePrivacyRules = [
    ["Google does not control the availability or functionality of third party developer tools.","Google 不控制第三方开发者工具的可用性或功能。"],
    ["Your data from third party developer tools connected to your Antigravity instance may be shared with Google.","您在与 Antigravity 实例连接的第三方开发者工具中的数据可能会与 Google 共享。"],
    ["Google will protect any such data in accordance with the Google Privacy Policy, found here:","Google 将依据 Google 隐私权政策保护此类数据，详见："],
  ];

  // Structured Prefix & Content Match Rules for Complex / Truncated Text
  const textPrefixRules = [
    // Plugins & Customizations
    ["Plugins are packaged collections of skills and MCPs to help the Agent in", "插件是技能和 MCP 的打包集合，用于帮助 "],
    ["Plugins are packaged collections of skills and MCPs", "插件是技能和 MCP 的打包集合，用于帮助 "],
    ["work with Google developer products. You can always change your choices in Settings.", " 中的智能体与 Google 开发者产品协同工作。您可以随时在“设置”中更改您的选择。"],
    ["Provides a comprehensive guide", "提供 Google Antigravity (AGY) 的综合指南、快速参考和站点地图，包括 Antigravity CLI、Antigravity 2.0、IDE、Python SDK、斜杠命令、快捷键和自定义项。"],
    ["How to render rich interactive HTML widgets inline in the chat or as standalone artifacts. Use this skill", "如何在对话中内联或作为独立产物渲染丰富的交互式 HTML 小部件。当您想要向用户显示图表、数据可视化或交互式控件时，请使用此技能。"],
    ["Automatically migrate legacy workflows", "自动将旧版工作流迁移到技能目录。它会扫描现有工作流，并创建目标..."],
    ["Guidelines for interacting with GitHub and request permissions", "关于与 GitHub 交互的指南，并在智能体环境中由于限制导致命令失败时向用户请求相应的权限。"],
    ["Comprehensive guide and reference for the Antigravity Customization System", "Antigravity 自定义系统的综合指南和参考。用于解释自定义项的工作原理、加载优先级、发现机制，并指导创建技能、规则、插件、钩子和 MCP 服务器。"],
    ["Skills providing tailored instructions for happy path", "提供 Dart 和 Flutter 开发主流程定制化指南的技能。"],
    ["Interactive guide to design and create a scheduled background automation", "设计和创建计划后台自动化的交互式指南。当用户想要创建自动化或周期性计划任务时（例如“总结我的邮件”），请使用此技能。"],
    ["How to write and run a dynamic workflow script with the `run_workflow` tool:", "如何使用 `run_workflow` 工具编写和运行动态工作流脚本：通过 Python 脚本，使用 `agent`、`parallel`、`pipeline` 和 `phase` 编排多个智能体。适用于任务可拆分为多个独立或分阶段的智能体工作单元（按文件、模块、问题或审查角度分别处理，再汇总结果），或用户要求使用工作流的情况。单个委派任务应使用子智能体；旧版工作流文件请参阅 `migrate-workflows`。"],
    ["How to manage and create plugins", "如何管理和创建插件——作为单一单元安装、启用和禁用的命名空间技能、智能体、规则、MCP 服务器和钩子捆绑包。"],
    ["Build, package, run, and debug UI extensions for Antigravity", "为 Antigravity 构建、打包、运行和调试 UI 扩展：在侧边面板中渲染的交互式 Web 面板，由使用内置 Sidecar SDK 的 Node.js sidecar 提供服务。"],
    ["Discover UI plugin panels relevant to the current task", "发现与当前任务相关的 UI 插件面板，并在对话中显示一键式快捷胶囊以在侧边面板中打开（切换）它们。"],
    ["Build and prototype location-aware applications with Google Maps Platform", "使用 Google Maps Platform 构建具有位置感知能力的应用并设计原型。"],
    ["Specialized suite of skills for data engineers and database", "专为 Google Cloud 上的数据工程师和数据库从业人员打造的专业技能套件。"],
    ["Build applications with the Gemini Interactions API and Live API", "使用 Gemini Interactions API 和 Live API 构建应用，包括文本生成、多轮对话等功能。"],
    ["Build on Google's developer platforms, including Android, Chrome, Gemini, and Google Cloud.", "基于 Google 开发者平台（包括 Android、Chrome、Gemini 和 Google Cloud）构建。"],
    ["Prototype, build & run modern apps that user", "原型设计、构建和运行现代应用程序..."],
    ["Curated collection of agent skills for science t", "为科学任务精心挑选的智能体技能集合。"],
    ["Using the Google Antigravity Python SDK to b", "使用 Google Antigravity Python SDK 构建自定义智能体..."],
    ["Search and retrieve official documentation acr", "搜索和检索官方开发者文档..."],
    ["Integration skill and tools for Google Maps Pl", "适用于 Google Maps Platform 的集成技能和工具。"],
    ["Official plugin for Dart and Flutter that installs", "Dart 和 Flutter 官方插件，提供相关工具安装和开发支持。"],
    ["This plugin provides a specialized suite of skill", "此插件提供一套专为数据处理打造的专业技能..."],
    ["Connect to Google Workspace, including Docs, Sheets, Slides, Drive, and Calendar.", "连接到 Google Workspace，包括文档、表格、幻灯片、云端硬盘和日历。"],
    ["Read, draft, and edit docs.", "读取、起草和编辑文档。"],
    ["Read, write, and format spreadsheets.", "读取、写入和格式化电子表格。"],
    ["Read, edit, and export presentations.", "读取、编辑和导出演示文稿。"],
    ["Search, upload, download, and share files.", "搜索、上传、下载和共享文件。"],
    ["Check availability, schedule events, and RSVP.", "查看空闲时间、安排活动并回复邀请。"],

    // MCP Servers Descriptions
    ["Investigate and fix software issues using AI-powered root cause analysis", "使用 AI 驱动的根本原因分析来调查和修复软件问题。此 MCP 服务器连接到您的 Antimetal 账户..."],
    ["Query and act on your marketing, analytics, CRM, e-commerce", "跨 325 多个连接器查询并处理您的营销、分析、CRM、电子商务和仓库数据..."],
    ["Query your GitLab SDLC as a knowledge graph", "将您的 GitLab SDLC 作为知识图谱进行查询。Orbit 会建立相关索引..."],
    ["Enable Antigravity to deploy apps to Google Cloud Run", "使 Antigravity 能够将应用部署到 Google Cloud Run。"],
    ["Search and reference over 600,000 real-world app screens", "搜索并参考超过 600,000 个真实的应用程序屏幕、用户流程和 UI 模式..."],
    ["Build, edit, deploy, and manage full-stack web apps with Lovable", "使用自然语言，通过 Lovable 构建、编辑、部署和管理全栈 Web 应用..."],
    ["The GKE remote MCP server provides read write access to your GKE", "GKE 远程 MCP 服务器提供对您的 GKE Kubernetes 资源的读写访问权限。"],
    ["The Dart and Flutter MCP server exposes Dart (and Flutter)", "Dart 和 Flutter MCP 服务器向兼容的 AI 助手客户端公开相关开发工具操作。"],
    ["The Firebase Model Context Protocol (MCP) Server gives AI-powered", "Firebase MCP 服务器使 AI 工具能够处理您的 Firebase 项目和应用程序代码库。"],
    ["The Genkit Model Context Protocol (MCP) Server gives AI-powered", "Genkit MCP 服务器使 AI 工具能够构建、调试和检查您的 Genkit 应用。"],
    ["The gopls Model Context Protocol (MCP) server provides tools", "gopls MCP 服务器为您的 Go 代码库提供语义代码分析、实时诊断和转换工具。"],
    ["Interact with your BigQuery data using natural language", "使用自然语言与您的 BigQuery 数据交互。允许您安全地连接到您的数据集..."],
    ["The AlloyDB for PostgreSQL remote MCP server lets you access", "AlloyDB for PostgreSQL 远程 MCP 服务器允许您访问和运行 AlloyDB 工具..."],
    ["The Bigtable Admin remote MCP server lets you manage Bigtable", "Bigtable Admin 远程 MCP 服务器允许您管理 Bigtable 资源。"],
    ["The Cloud SQL remote MCP server lets you access and run Cloud SQL", "Cloud SQL 远程 MCP 服务器允许您访问和运行 Cloud SQL 工具..."],
    ["The Spanner remote MCP server lets you access and run Spanner", "Spanner 远程 MCP 服务器允许您访问和运行 Spanner 工具..."],
    ["The Apigee API hub remote MCP server lets you manage", "Apigee API hub 远程 MCP 服务器允许您管理 API、版本、规范、操作等。"],
    ["Connect your AI assistants to Looker business intelligence", "将您的 AI 助手连接到 Looker 商业智能，通过自然语言查询实现数据探索。"],
    ["Connect your AI assistants to the Knowledge Catalog", "将您的 AI 助手连接到 Knowledge Catalog，实现数据发现和治理。"],
    ["The MCP Toolbox for Databases is an open-source MCP server", "MCP Toolbox for Databases 是一个开源 MCP 服务器，旨在简化和保护用于与数据库交互的工具的开发。"],
    ["Interact with your Oracle Database data using natural language", "使用自然语言与您的 Oracle 数据库交互。此 MCP 服务器允许您安全地连接到您的数据库以执行 SQL 查询..."],
    ["The Dev Mode MCP Server brings Figma directly into your workflow", "Dev Mode MCP 服务器通过向从 Figma 生成代码的 AI 智能体提供重要的设计信息和上下文，将 Figma 直接带入您的工作流..."],
    ["The GitHub MCP Server is a Model Context Protocol (MCP) server", "GitHub MCP 服务器提供与 GitHub API 的无缝集成，从而实现高级自动化和..."],
    ["The Google Home Developer MCP server allows you to search", "Google Home Developer MCP 服务器允许您搜索 Google Home 文档、OpenThread 和 Matter 规范文档。"],
    ["Neon MCP Server is an open-source tool that lets you interact", "Neon MCP 服务器是一个开源工具，允许您使用自然语言与您的 Neon Postgres 数据库交互。"],
    ["The Stripe Model Context Protocol server allows you to integrate", "Stripe MCP 服务器允许您通过函数调用与 Stripe API 集成。该协议支持各种交互工具..."],
    ["Interact with Redis key-value stores", "与 Redis 键值存储交互。"],
    ["A Model Context Protocol server for interacting with MongoDB", "用于与 MongoDB Atlas 交互的模型上下文协议服务器。"],
    ["Official Notion MCP Server that allows interaction with Notion", "官方 Notion MCP 服务器，允许通过 Notion API 与 Notion 工作区、页面、数据库和评论进行交互。"],
    ["Official Linear.app MCP Server for interacting with Linear", "官方 Linear.app MCP 服务器，用于与 Linear 项目、议题和工作流进行交互。"],
    ["An MCP server implementation that integrates the Perplexity", "一个集成了 Perplexity Sonar API 的 MCP 服务器实现，以提供实时的、全网范围的研究能力。"],
    ["Official PayPal MCP Server that allows integration with PayPal", "官方 PayPal MCP 服务器，允许与 PayPal API 集成，用于支付处理、交易管理和账户操作。"],
    ["The Heroku Platform MCP Server enables seamless interaction", "Heroku Platform MCP 服务器可实现与 Heroku 平台资源的无缝交互，允许 LLM 读取、管理和操作应用程序..."],
    ["The Pinecone MCP Server enables AI tools to search Pinecone", "Pinecone MCP 服务器使 AI 工具能够搜索 Pinecone 文档、配置索引、根据索引配置生成代码..."],
    ["Connect your Supabase projects to AI assistants.", "将您的 Supabase 项目连接到 AI 助手。此 MCP 服务器允许管理表、获取配置、执行 SQL 查询、管理边缘函数等..."],
    ["The Prisma MCP Server enables AI tools to interact with Prisma", "Prisma MCP 服务器使 AI 工具能够与 Prisma 交互，从而轻松创建和管理 Postgres 数据库。"],
    ["The Locofy MCP Server", "Locofy MCP 服务器使 Locofy.ai 代码能够与您的 IDE 集成并进行扩展。"],
    ["Locofy MCP Server enables Locofy.ai code", "Locofy MCP 服务器使 Locofy.ai 代码能够与您的 IDE 集成并进行扩展。"],
    ["Airweave lets agents search any app.", "Airweave 允许智能体搜索任何应用程序。"],
    ["Atlassian MCP Server for interacting with Atlassian", "用于与 Atlassian 产品交互的 Atlassian MCP 服务器。"],
    ["Interact with your Harness account using natural language", "使用自然语言与您的 Harness 账户交互。此 MCP 服务器允许 AI 智能体检查和管理 CI/CD 流水线、执行、服务..."],
    ["SonarQube MCP Server enables AI assistants to interact", "SonarQube MCP 服务器使 AI 助手能够与 SonarQube 实例交互，进行代码质量分析、项目管理和质量门限操作。"],
    ["Perform searches on ingested data in Google-owned data stores", "在 Google 拥有的数据存储中，对已摄取的数据执行搜索。"],
    ["Interact with documents stored in a Firestore database", "使用自然语言与存储在 Firestore 数据库中的文档进行交互。"],
    ["Access resources in the Cloud Logging platform using natural", "使用自然语言访问 Cloud Logging 平台中的资源。"],
    ["Manage clusters for Managed Service for Apache Kafka", "使用自然语言管理 Apache Kafka 托管服务和 Kafka Connect 的集群。"],
    ["Access resources in the Cloud Monitoring platform using natural", "使用自然语言访问 Cloud Monitoring 平台中的资源。"],
    ["Manage Pub/Sub resources and publish messages. Create, list,", "管理 Pub/Sub 资源并发布消息。创建、列出、获取、更新和删除 Pub/Sub 主题、订阅和快照，以及发布消息..."],
    ["The Cloud Quotas MCP server allows you to view quota allocations", "Cloud Quotas MCP 服务器允许您查看配额分配、请求增加配额以及管理配额调整器配置。"],
    ["Enable Antigravity to control and inspect a live Chrome browser", "使 Antigravity 能够控制和检查实时 Chrome 浏览器，利用 Chrome DevTools 的强大功能进行可靠的自动化、深度调试..."],
    ["Netlify MCP Server enables AI assistants to interact", "Netlify MCP 服务器使 AI 助手能够与 Netlify 平台交互，以管理站点、部署、域名和其他 Web 开发工作流。"],
    ["A Model Context Protocol server that provides structured thinking", "一个模型上下文协议服务器，为 LLM 对话提供结构化思考和推理能力。"],
    ["Sonatype MCP server for interacting with our dependency management", "用于与我们的依赖项管理和安全情报平台交互的 Sonatype MCP 服务器。"],
    ["The Google Maps Platform Code Assist MCP server provides", "Google Maps Platform Code Assist MCP 服务器为您喜爱的 AI 编程助手提供最新、官方的 Google Maps Platform 文档、代码..."],
    ["This MCP server provides your LLM with docs and examples to instrument your AI apps with Arize AX", "此 MCP 服务器为您的 LLM 提供文档和示例，以便使用 Arize AX 检测您的 AI 应用。它还提供对 Arize 支持的访问。将其连接到您的 IDE..."],
    ["The Postman MCP Server connects Postman to AI tools", "Postman MCP 服务器将 Postman 连接到 AI 工具，使 AI 智能体和助手能够访问工作区、管理集合和环境..."],
    ["The Stitch MCP server enables AI assistants to interact with Stitch", "Stitch MCP 服务器使 AI 助手能够与 Stitch 交互以进行设计：从文本和图像生成 UI 设计，以及访问项目和屏幕..."],
    ["The ClickHouse MCP server enables agents to securely interact", "ClickHouse MCP 服务器使智能体能够安全地与 ClickHouse 数据库交互。它提供了一个通用接口来执行 SQL、探索数据和查看..."],
    ["Perform a range of infrastructure management tasks, including: manage virtual machine", "执行一系列基础设施管理任务，包括：管理虚拟机 (VM) 实例、管理实例组管理器和实例模板..."],
    ["Access enterprise mobility data using natural language queries", "使用关于设备队列的自然语言查询、策略合规性的自动审计以及设备集成来访问企业移动数据..."],
    ["Search your Google Cloud projects using natural language", "使用自然语言搜索您的 Google Cloud 项目。"],

    // Error and Fallback Links
    ["Kick off work on your computer and continue working", "在电脑上启动工作，并可以通过手机或其他设备继续与智能体协同工作。请在应用设置中开启“远程控制”。"],
    ["Turn on Remote Control in app settings", "请在应用设置中开启“远程控制”。"],
    ["Try Remote Control", "尝试远程控制"],
    ["Agent execution terminated due to error", "智能体执行因错误而终止。"],
    ["Confirming this undo action will make the following changes", "确认此撤销操作将做出以下更改："],
    ["Confirming this undo action will not make any code changes", "确认此撤销操作不会做出任何代码更改。"],
    ["Confirming this redo action will make the following changes", "确认此重做操作将做出以下更改："],
    ["Confirming this redo action will not make any code changes", "确认此重做操作不会做出任何代码更改。"],
    ["Undo changes up to this point", "撤销更改至此处"],
    ["Redo changes up to this point", "重做更改至此处"],
    ["Our servers are experiencing high traffic", "我们的服务器当前负载较高，请稍后重试。"],
    ["Agent terminated due to error", "智能体因错误而终止"],
    ["You can prompt the model to try again", "您可以提示模型重试，或者如果错误仍然存在，可以开启新的对话。"],
    ["for more help", " 以获取更多帮助。"],
    ["See our", "查看我们的 "]
  ];

  function translateText(text) {
    if (!text || typeof text !== 'string') return text;
    let trimmed = text.trim();
    if (!trimmed) return text;

    if (dictionary[trimmed]) {
      return text.replace(trimmed, dictionary[trimmed]);
    }

    let privacyText = text;
    for (const [original, translated] of marketplacePrivacyRules) {
      privacyText = privacyText.replace(original, () => translated);
    }
    if (privacyText !== text) return privacyText;

    const normalized = trimmed.replace(/\s+/g, " ");
    if (normalized !== trimmed && dictionary[normalized]) {
      return text.replace(trimmed, () => dictionary[normalized]);
    }
    const ellipsis = normalized.match(/^(.*?)(?:\.{3}|…)$/);
    const prefix = ellipsis ? ellipsis[1].trimEnd() : "";
    const descriptions = marketplaceDescriptionRules.filter(([original]) =>
      original === normalized || (prefix.length >= 24 && original.startsWith(prefix)));
    if (descriptions.length === 1) {
      return text.replace(trimmed, () => descriptions[0][1]);
    }
    
    // Dynamic Regex Translations
    const deletionPrompt = matchProjectDeletionPrompt(trimmed);
    if (deletionPrompt) {
      return text.replace(trimmed, () => deletionPrompt.prefix + deletionPrompt.value + deletionPrompt.suffix);
    }
    let m;
    if ((m = trimmed.match(/^(?:Voice chat|语音对话)(\s*·\s*)((?:\d{1,2}:){1,2}\d{2})(\s*·\s*)(\d+(?:\.\d+)?)s$/))) {
      return text.replace(trimmed, () => "语音对话" + m[1] + m[2] + m[3] + m[4] + " 秒");
    }
    if ((m = trimmed.match(/^Voice speed,\s*(\d+(?:\.\d+)?)x$/))) {
      return text.replace(trimmed, () => "语速，" + m[1] + "x");
    }
    if ((m = trimmed.match(/^Use\s+(\S+)$/)) && voicePresetNames.has(m[1])) {
      return text.replace(trimmed, () => "使用 " + m[1]);
    }
    if ((m = trimmed.match(/^Models within this group:\s*([\s\S]+)$/))) {
      return text.replace(trimmed, () => "本组包含的模型：" + m[1]);
    }
    if ((m = trimmed.match(/^(\d+)\s+(?:on|开)\s+for this conversation$/))) {
      return text.replace(trimmed, () => "本次对话已启用 " + m[1] + " 个");
    }
    // Tooltip labels may share a text node with a user-configurable shortcut.
    if ((m = trimmed.match(/^(Select Project|Send [Mm]essage|Search Conversations|Quote|Stop Recording(?: and Send)?|Mute mic|Mute Antigravity)(\s+.+)$/))) {
      const shortcut = m[2].trim().replace(/^\((.*)\)$/, "$1");
      if (/^(?:(?:Ctrl|Cmd|Alt|Shift|Meta)\s*\+\s*)+\S+$/.test(shortcut) ||
          /^[⌘⌃⌥⇧]+\S+$/.test(shortcut) || shortcut === "Enter") {
        return text.replace(trimmed, () => dictionary[m[1]] + m[2]);
      }
    }
    if ((m = trimmed.match(/^(\d+(?:\.\d+)?)%\s+left$/))) {
      return text.replace(trimmed, () => "剩余 " + m[1] + "%");
    }
    if ((m = trimmed.match(/^(?:Permanently delete\s+|永久删除\s*)(.+?)(?:\s+including\s+|\s*包括\s*)(\d+)\s+active conversations?\s+and\s+(\d+)\s+archived conversations?\.?$/))) {
      return text.replace(trimmed, () => "永久删除 " + m[1].trim() + "，包括 " + m[2] + " 个进行中的对话和 " + m[3] + " 个已归档对话。");
    }
    if ((m = trimmed.match(/^(\d+)\s+active conversations?\s+and\s+(\d+)\s+archived conversations?(\.)?$/))) {
      return text.replace(trimmed, () => m[1] + " 个进行中的对话和 " + m[2] + " 个已归档对话" + (m[3] ? "。" : ""));
    }
    if ((m = trimmed.match(/^Permanently delete (.+?)\s+(?:including|包括)\s*(\d+)\s+active conversations?\.?$/))) {
      return text.replace(trimmed, () => "永久删除" + m[1] + "，包括 " + m[2] + " 个进行中的对话。");
    }
    if ((m = trimmed.match(/^Permanently delete (.+)$/))) {
      return text.replace(trimmed, () => "永久删除" + m[1]);
    }
    if ((m = trimmed.match(/^(\d+)\s+active conversations?(\.)?$/))) {
      return text.replace(trimmed, () => m[1] + " 个进行中的对话" + (m[2] ? "。" : ""));
    }
    if ((m = trimmed.match(/^(\d+)\s+archived conversations?(\.)?$/))) {
      return text.replace(trimmed, () => m[1] + " 个已归档对话" + (m[2] ? "。" : ""));
    }
    if (text.indexOf("of the customization budget is available") !== -1) {
      text = text.replace(/(\d+(?:\.\d+)?)% of the customization budget is available\.?/g, "自定义项预算可用额度为 $1%。");
      text = text.replace(/%\s*of the customization budget is available\.?/g, "% 的自定义项预算可用额度。");
      text = text.replace(/(^\s*)of the customization budget is available\.?/g, "$1的自定义项预算可用额度。");
    }
    if ((m = trimmed.match(/^Show (\d+) breakdowns?$/))) {
      return text.replace(trimmed, "显示 " + m[1] + " 项明细");
    }
    if ((m = trimmed.match(/^Explored (\d+) files? >$/))) {
      return text.replace(trimmed, "已浏览 " + m[1] + " 个文件 >");
    }
    if ((m = trimmed.match(/^Editing (.+) \+(\d+) -(\d+)$/))) {
      return text.replace(trimmed, "正在编辑 " + m[1] + " +" + m[2] + " -" + m[3]);
    }
    if (trimmed === "Waiting for user input") {
      return text.replace(trimmed, "等待用户输入");
    }
    if ((m = trimmed.match(/^Artifacts?\s*(\d+)$/i))) {
      return text.replace(trimmed, "产物 " + m[1]);
    }
    if ((m = trimmed.match(/^No artifacts generated\.?$/i))) {
      return text.replace(trimmed, "未生成任何产物");
    }
    if (/(?:No|否)\s*(?:projects?|项目)?\s*found/i.test(text) || text.indexOf("No projects found") !== -1 || text.indexOf("No project found") !== -1) {
      return text.replace(/(?:No|否)\s*(?:projects?|项目)?\s*found\.?|No projects found\.?|No project found\.?/gi, "暂无项目");
    }
    if ((m = trimmed.match(/^(?:No|否)\s*projects?\s*found\.?$/i))) {
      return text.replace(trimmed, "暂无项目");
    }
    if ((m = trimmed.match(/^No\s+Project$/i))) {
      return text.replace(trimmed, "无项目");
    }
    if (trimmed === "Type") return text.replace(trimmed, "输入");
    if (trimmed === "and select") return text.replace(trimmed, "并选择");
    if (trimmed === "to have the agent generate a plan." || trimmed === "to have the agent generate a plan") {
      return text.replace(trimmed, "即可让智能体生成计划。");
    }
    if (trimmed === "Visit") return text.replace(trimmed, "访问");
    if (trimmed === "Legal Help") return text.replace(trimmed, "法律帮助");
    if (trimmed === "to ask for content changes for legal reasons." || trimmed === "to ask for content changes for legal reasons") {
      return text.replace(trimmed, "以出于法律原因请求更改内容。");
    }
    if ((m = trimmed.match(/^Learn more about (.+)$/))) {
      return text.replace(trimmed, "了解更多关于 " + (dictionary[m[1]] || m[1]) + " 的信息");
    }
    if ((m = trimmed.match(/^You have used some of your weekly limit, it will fully refresh in (.*)\.$/))) {
      let timeStr = m[1].replace(/days?/g, "天").replace(/hours?/g, "小时").replace(/minutes?/g, "分钟").replace(/,/g, "");
      return text.replace(trimmed, "您已使用部分每周限额，它将在 " + timeStr + " 后完全重置。");
    }
    if ((m = trimmed.match(/^You have used some of your 5-hour limit, it will fully refresh in (.*)\.$/))) {
      let timeStr = m[1].replace(/days?/g, "天").replace(/hours?/g, "小时").replace(/minutes?/g, "分钟").replace(/,/g, "");
      return text.replace(trimmed, "您已使用部分五小时限额，它将在 " + timeStr + " 后完全重置。");
    }
    if ((m = trimmed.match(/^Resets? in\s+(.+)$/i))) {
      let timeStr = m[1]
        .replace(/(\d+)\s*d(?:ays?)?/gi, "$1天 ")
        .replace(/(\d+)\s*h(?:ours?)?/gi, "$1小时 ")
        .replace(/(\d+)\s*m(?:inutes?|ins?)?/gi, "$1分钟 ")
        .replace(/(\d+)\s*s(?:econds?|ecs?)?/gi, "$1秒 ")
        .replace(/,\s*/g, " ")
        .trim();
      return text.replace(trimmed, "将在 " + timeStr + " 后重置");
    }
    if (/^Exploring\b/i.test(trimmed) || /running command/i.test(trimmed)) {
      let translatedActions = trimmed
        .replace(/Exploring file/gi, "浏览文件")
        .replace(/running command/gi, "运行命令")
        .replace(/editing file/gi, "编辑文件")
        .replace(/,\s*/g, "、");
      return text.replace(trimmed, translatedActions);
    }
    if ((m = trimmed.match(/^Files? Changed\s*(\d+)$/i))) return text.replace(trimmed, "已修改文件 " + m[1]);
    if ((m = trimmed.match(/^Uploads?\s*(\d+)$/i))) return text.replace(trimmed, "已上传文件 " + m[1]);
    if ((m = trimmed.match(/^See all\s*\((.+?)\)$/i))) return text.replace(trimmed, "查看全部 (" + m[1] + ")");
    if ((m = trimmed.match(/^Background Tasks?\s*(\d+)$/i))) return text.replace(trimmed, "后台任务 " + m[1]);
    if ((m = trimmed.match(/^Terminals?\s*(\d+)$/i))) return text.replace(trimmed, "终端 " + m[1]);
    if ((m = trimmed.match(/^No subagents?(?:\s*running)?\.?$/i))) return text.replace(trimmed, "暂无子智能体");
    if ((m = trimmed.match(/^Available AI Credits: ([\d,]+)$/))) {
      return text.replace(trimmed, "可用 AI 积分: " + m[1]);
    }
    if ((m = trimmed.match(/^Send feedback as (.+)$/))) {
      return text.replace(trimmed, "以 " + m[1] + " 的身份发送反馈");
    }
    if ((m = trimmed.match(/^(\+?\d+) more lines$/))) {
      return text.replace(trimmed, "更多 " + m[1] + " 行");
    }
    if ((m = trimmed.match(/^(\d+) files? changed$/))) {
      return text.replace(trimmed, m[1] + " 个文件已修改");
    }
    if ((m = trimmed.match(/^See (\d+) more$/i))) return text.replace(trimmed, "查看更多 " + m[1] + " 项");
    if ((m = trimmed.match(/^Last (\d+) days?$/i))) return text.replace(trimmed, "最近 " + m[1] + " 天");
    if ((m = trimmed.match(/^Last (\d+) hours?$/i))) return text.replace(trimmed, "最近 " + m[1] + " 小时");
    if ((m = trimmed.match(/^Last (\d+) months?$/i))) return text.replace(trimmed, "最近 " + m[1] + " 个月");
    if ((m = trimmed.match(/^Version ([\d\.]+(-\w+)?)$/))) {
      return text.replace(trimmed, "版本 v" + m[1]);
    }
    if ((m = trimmed.match(/^Start using (.+?), our best (.+?) model\.?$/i))) {
      return text.replace(trimmed, "开始使用 " + m[1] + "，我们最强大的 " + m[2] + " 模型。");
    }
    if (text.indexOf("is now available on paid Pro and Ultra plans") !== -1 || text.indexOf("Third-party model access will no longer be available") !== -1) {
      return "Sonnet 5.5 现已在付费的 Pro 和 Ultra 方案中提供。从 2026 年 11 月 2 日起，您当前的方案将不再支持访问第三方模型。";
    }
    if ((m = trimmed.match(/^(\d+)\s*s(?:\s*ago)?$/i))) return text.replace(trimmed, m[1] + "秒前");
    if ((m = trimmed.match(/^(\d+)\s*m(?:\s*ago)?$/i))) return text.replace(trimmed, m[1] + "分钟前");
    if ((m = trimmed.match(/^(\d+)\s*h(?:\s*ago)?$/i))) return text.replace(trimmed, m[1] + "小时前");
    if ((m = trimmed.match(/^(\d+)\s*d(?:\s*ago)?$/i))) return text.replace(trimmed, m[1] + "天前");

    // Dynamic Time Formatter
    if (text.indexOf("Worked for") !== -1) {
      return text.replace(/Worked for ([\d\.a-z ]+)/gi, function(_, timeStr) {
        let t = timeStr.replace(/ms/g, "毫秒").replace(/s/g, "秒").replace(/m/g, "分").replace(/h/g, "小时");
        return "运行耗时 " + t;
      });
    }
    if (text.indexOf("Thought for") !== -1) {
      return text.replace(/Thought for ([\d\.a-z ]+)/gi, function(_, timeStr) {
        let t = timeStr.replace(/ms/g, "毫秒").replace(/s/g, "秒").replace(/m/g, "分").replace(/h/g, "小时");
        return "思考耗时 " + t;
      });
    }
    if (text.indexOf("Working") !== -1) {
      text = text.replace(/Working(\.*)/g, "运行中$1");
    }

    // Special Multi-segment Matches
    if (text.indexOf("Google Developer Knowledge") !== -1 || text.indexOf("official developer documentation and retrieve") !== -1) {
      return "Google Developer Knowledge MCP 服务器使 AI 驱动的开发工具能够搜索 Google 的官方开发者文档并检索相关内容...";
    }
    if (text.indexOf("Ask questions. Get answers") !== -1) {
      if (text.indexOf("PostHog") !== -1) {
        return "提出问题。获取答案。该 MCP 是您的编程智能体与之对话的服务器。用英语提问，它会针对您的 PostHog 数据运行查询并返回结果。";
      }
      return "提出问题。获取答案。该 MCP 是您的 ";
    }
    if (text.indexOf("talks to. Ask a question in English") !== -1 || text.indexOf("runs the query against your") !== -1) {
      return " 与之对话的服务器。用英语提问，它会针对您的 ";
    }
    if (text.indexOf("The answer lands") !== -1 || text.indexOf("data. The answer") !== -1) {
      return " 数据运行查询并返回结果。";
    }

    if (text.indexOf("Configure the browser subagent") !== -1) {
      text = text.replace(/Configure the browser subagent\.?/g, "配置浏览器子智能体。");
    }
    if (text.indexOf("It requires") !== -1 && text.indexOf("Configure") === -1) {
      text = text.replace(/It requires\s?/g, "需要安装 ");
    }
    if (text.indexOf("to be installed.") !== -1) {
      text = text.replace(/\s?to be installed\./g, "");
    }
    if (text.indexOf("The browser subagent can be invoked by typing") !== -1) {
      text = text.replace(/The browser subagent can be invoked by typing \/browser in the conversation input box\./g, "您可以在对话输入框中输入 /browser 来调用浏览器子智能体。");
    }

    if (text.indexOf("You currently don't have any MCP Servers installed.") !== -1) {
      text = text.replace(/You currently don't have any MCP Servers installed\./g, "您目前尚未安装任何 MCP 服务器。");
    }
    if (text.indexOf("Add an MCP server above") !== -1) {
      text = text.replace(/Add an MCP server above or add a custom one via the MCP Config\./g, "请在上方添加 MCP 服务器，或通过 MCP 配置添加自定义服务器。");
    }

    // Prefix Rules Matching
    for (let i = 0; i < textPrefixRules.length; i++) {
      if (text.indexOf(textPrefixRules[i][0]) !== -1) {
        return textPrefixRules[i][1];
      }
    }

    // Short Word Exact Replacement
    let wordsCount = trimmed.split(/\s+/).length;
    if (wordsCount <= 3) {
      let lowerText = trimmed.toLowerCase();
      if (coreWords[lowerText]) {
        return text.replace(trimmed, coreWords[lowerText]);
      }
    }
    
    return text;
  }

  function checkEmptyContainer(el) {
    if (!el || el.tagName === 'BODY' || el.tagName === 'HTML') return false;
    if (el.closest && el.closest('[data-empty-handled="true"]')) return false;
    if (el.querySelector && el.querySelector('svg, button, input')) return false;
    let t = el.textContent ? el.textContent.trim() : '';
    if (!t) return false;
    if (/^(?:No|否)\s+automations\s+yet$/.test(t) &&
        !(el.closest && el.closest('pre, code, .monaco-editor, script, style')) &&
        !(el.querySelector && el.querySelector('pre, code, .monaco-editor, script, style'))) {
      // Keep React's existing nodes when the empty label is split across text nodes or spans.
      const textNodes = [];
      const collectText = node => {
        if (node.nodeType === Node.TEXT_NODE) textNodes.push(node);
        else Array.from(node.childNodes || []).forEach(collectText);
      };
      collectText(el);
      if (textNodes.length) {
        textNodes.forEach((node, index) => {
          node.textContent = index === 0 ? "暂无自动化任务" : "";
        });
        return true;
      }
    }
    let m = t.match(/^(?:No|否)\s*(.*?)\s*found\.?$/i) || t.match(/^(.*?)\s+found\.?$/i) || t === "暂无项目" || t === "暂无对话";
    if (el.__empty_handled) return false;
    if (m) {
      let target = (m[1] || '').trim().toLowerCase();
      let label = "";
      let svg = "";
      if (target === 'projects' || target === 'project' || target === '项目' || target === '' || t === '暂无项目') {
        label = "暂无项目";
        svg = '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-1.2-1.8A2 2 0 0 0 7.55 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"></path>';
      } else if (target === 'conversations' || target === 'conversation' || target === '对话' || t === '暂无对话') {
        label = "暂无对话";
        svg = '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>';
      } else if (target === 'results' || target === 'result' || target === '结果') {
        label = "未找到结果";
        svg = '<circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>';
      } else if (target === 'artifacts' || target === 'artifact' || target === '产物') {
        label = "暂无产物";
        svg = '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line>';
      } else if (target === 'files' || target === 'file' || target === '文件') {
        label = "暂无文件";
        svg = '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path><polyline points="14 2 14 8 20 8"></polyline>';
      } else if (target === 'models' || target === 'model' || target === '模型') {
        label = "暂无模型";
        svg = '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>';
      } else if (target === 'subagents' || target === 'subagent' || target === '子智能体') {
        label = "暂无子智能体";
        svg = '<rect x="3" y="11" width="18" height="10" rx="2"></rect><circle cx="12" cy="5" r="2"></circle><path d="M12 7v4"></path><line x1="8" y1="16" x2="8" y2="16"></line><line x1="16" y1="16" x2="16" y2="16"></line>';
      }
      if (label) {
        el.setAttribute('data-empty-handled', 'true');
        el.innerHTML = '<span style="display: inline-flex; align-items: center; gap: 8px; opacity: 0.6; padding: 2px 0;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + svg + '</svg><span>' + label + '</span></span>';
        el.__empty_handled = true;
        return true;
      }
    }
    return false;
  }

  function translateProjectDeletionPrompt(el) {
    if (!el || !el.querySelectorAll || el.tagName === 'BODY' || el.tagName === 'HTML') return false;
    const raw = el.textContent || '';
    const text = raw.trim();
    if (!/^(?:Are you sure you want to delete the|确定要删除项目“|This will permanently delete|这将永久删除其中的)/.test(text)) return false;
    const prompt = matchProjectDeletionPrompt(text);
    if (!prompt) return false;
    const protectedContent = 'pre, code, .monaco-editor, textarea, input, script, style, [contenteditable="true"]';
    if ((el.closest && el.closest(protectedContent)) || el.querySelector(protectedContent)) return false;
    const start = raw.length - raw.trimStart().length + prompt.offset;
    const end = start + prompt.value.length;
    const nodes = [];
    const collect = node => {
      if (node.nodeType === Node.TEXT_NODE) nodes.push(node);
      else Array.from(node.childNodes || []).forEach(collect);
    };
    collect(el);
    const groups = [[], [], []];
    let offset = 0;
    for (const node of nodes) {
      const next = offset + node.textContent.length;
      if (next <= start) groups[0].push(node);
      else if (offset >= end) groups[2].push(node);
      else if (offset >= start && next <= end) groups[1].push(node);
      else return false;
      offset = next;
    }
    if (groups.some(group => !group.length)) return false;
    // Keep React's variable nodes and their formatting; replace only surrounding wording.
    groups[1].forEach(node => projectDeletionValueOwners.set(node, el));
    for (const [index, target] of [[0, prompt.prefix], [2, prompt.suffix]]) {
      groups[index].forEach((node, textIndex) => {
        const translated = textIndex === 0 ? target : '';
        if (node.textContent !== translated) node.textContent = translated;
      });
    }
    return true;
  }

  function translateVoiceChatDuration(node) {
    if (!/^(?:\d+(?:\.\d+)?)?s$/.test(node.textContent.trim())) return false;
    let container = node.parentElement;
    for (let depth = 0; container && depth < 4 && container.tagName !== 'BODY'; depth++, container = container.parentElement) {
      const text = (container.textContent || '').trim();
      if (/^(?:Voice chat|语音对话)\s*·\s*(?:\d{1,2}:){1,2}\d{2}\s*·\s*\d+(?:\.\d+)?s$/.test(text)) {
        node.textContent = node.textContent.replace(/s(?=\s*$)/, ' 秒');
        return true;
      }
    }
    return false;
  }

  function translateArchiveRestore(node) {
    if (node.textContent.trim() !== 'Restore' || !node.parentElement || !node.parentElement.closest) return false;
    const control = node.parentElement.closest('button, [role="button"], [role="menuitem"]');
    if (!control) return false;
    let archived = control.getAttribute('role') === 'menuitem';
    let container = control.parentElement;
    for (let depth = 0; !archived && container && depth < 3 && container.tagName !== 'BODY'; depth++, container = container.parentElement) {
      archived = /^(?:This chat is archived\.|此对话已归档。)\s*Restore$/.test((container.textContent || '').trim());
    }
    if (!archived) return false;
    node.textContent = node.textContent.replace('Restore', '取消归档');
    if (control.title === 'Restore') control.title = '取消归档';
    if (control.getAttribute('aria-label') === 'Restore') control.setAttribute('aria-label', '取消归档');
    return true;
  }

  function translateArchiveToast(el) {
    if (!el || !el.querySelectorAll || el.tagName === 'BODY' || el.tagName === 'HTML') return false;
    const text = (el.textContent || '').trim();
    if (!text.startsWith('View archived in the sidebar (') && !text.startsWith('在侧边栏的筛选')) return false;
    const protectedContent = 'pre, code, .monaco-editor, textarea, input, script, style, [contenteditable="true"]';
    if ((el.closest && el.closest(protectedContent)) || el.querySelector(protectedContent)) return false;
    const icon = el.querySelector('svg');
    if (!icon) return false;
    const source = ['View archived in the sidebar (', 'menu).'];
    const target = ['在侧边栏的筛选', '菜单中查看已归档对话。'];
    const groups = [[], []];
    let group = 0;
    const collectText = node => {
      if (node === icon) { group = 1; return; }
      if (node.nodeType === Node.TEXT_NODE) { groups[group].push(node); return; }
      Array.from(node.childNodes || []).forEach(collectText);
    };
    collectText(el);
    if (groups.some((nodes, index) => {
      const value = nodes.map(node => node.textContent).join('').replace(/\s+/g, ' ').trim();
      return !nodes.length || (value !== source[index] && value !== target[index]);
    })) return false;
    groups.forEach((nodes, index) => nodes.forEach((node, textIndex) => {
      const translated = textIndex === 0 ? target[index] : '';
      if (node.textContent !== translated) node.textContent = translated;
    }));
    return true;
  }

  function translateVoicePresetPrefix(node) {
    if (node.textContent.trim() !== 'Use' || !node.parentElement || !node.parentElement.closest) return false;
    const button = node.parentElement.closest('button, [role="button"]');
    const match = button && button.textContent.trim().match(/^Use\s+(\S+)$/);
    if (!match || !voicePresetNames.has(match[1])) return false;
    node.textContent = node.textContent.replace('Use', '使用');
    return true;
  }

  const connectorCountStates = new WeakMap();
  const connectorCountOwners = new WeakMap();

  function forgetConnectorCount(el, state) {
    state.nodes.forEach(node => {
      if (connectorCountOwners.get(node) === el) connectorCountOwners.delete(node);
    });
    connectorCountStates.delete(el);
  }

  function translateConnectorCount(el) {
    if (!el || !el.childNodes || el.tagName === 'BODY' || el.tagName === 'HTML') return false;
    let state = connectorCountStates.get(el);
    const match = (el.textContent || '').trim().match(/^(\d+)\s+(?:on|开)\s+for this conversation$/);
    if (!state && !match) return false;
    const protectedContent = 'pre, code, .monaco-editor, textarea, input, script, style, [contenteditable="true"]';
    if ((el.closest && el.closest(protectedContent)) ||
        (el.querySelector && el.querySelector(protectedContent))) return false;
    const nodes = [];
    const collectText = node => {
      if (node.nodeType === Node.TEXT_NODE) nodes.push(node);
      else Array.from(node.childNodes || []).forEach(collectText);
    };
    collectText(el);
    if (state && (state.nodes.length !== nodes.length || state.nodes.some((node, index) => node !== nodes[index]))) {
      forgetConnectorCount(el, state);
      state = null;
    }
    if (!state) {
      if (!match || !nodes.length) return false;
      const originals = nodes.map(node => node.textContent);
      const owner = originals.findIndex(text => text.trim());
      const counter = owner === -1 ? null : originals[owner].match(/^(\s*)(\d+)([\s\S]*)$/);
      if (!counter || counter[2] !== match[1]) return false;
      state = {nodes, originals, outputs: originals.slice(), owner,
        before: counter[1], after: counter[3], count: match[1]};
      connectorCountStates.set(el, state);
      nodes.forEach(node => connectorCountOwners.set(node, el));
    }
    const values = nodes.map(node => node.textContent);
    const counter = values[state.owner].match(/^(\s*)(\d+)([\s\S]*)$/);
    const updated = counter && counter[1] === state.before && counter[3] === state.after;
    if (values.some((text, index) => !(index === state.owner && updated) &&
        text !== state.originals[index] && text !== state.outputs[index])) {
      forgetConnectorCount(el, state);
      return false;
    }
    if (updated) state.count = counter[2];
    // Keep the original counter node reference so subsequent React updates remain observable.
    state.outputs = nodes.map((_, index) => index === 0 ? "本次对话已启用 " + state.count + " 个" : '');
    let changed = false;
    nodes.forEach((node, index) => {
      if (node.textContent !== state.outputs[index]) {
        node.textContent = state.outputs[index];
        changed = true;
      }
    });
    return changed;
  }

  function translateInlineNotice(el) {
    if (!el || !el.querySelectorAll || el.tagName === 'BODY' || el.tagName === 'HTML') return false;
    const normalize = text => text.replace(/\s+/g, ' ').trim();
    const text = normalize(el.textContent || '');
    const rule = inlineNoticeRules.find(({source, target}) =>
      text.startsWith(source[0]) || text.startsWith(target[0]));
    if (!rule) return false;
    const protectedContent = 'pre, code, .monaco-editor, textarea, input, script, style, [contenteditable="true"]';
    if ((el.closest && el.closest(protectedContent)) || el.querySelector(protectedContent)) return false;
    const isLabel = node => {
      const label = normalize(node.textContent || '');
      return label === rule.source[1] || label === rule.target[1];
    };
    let links = Array.from(el.querySelectorAll('a, button, [role="link"], [role="button"]')).filter(isLabel);
    if (!links.length) {
      // Some settings entries use a clickable span without an ARIA role.
      const labels = Array.from(el.querySelectorAll('*')).filter(isLabel);
      links = labels.filter(label => !labels.some(other => other !== label && other.contains(label)));
    }
    if (links.length !== 1) return false;
    const link = links[0];
    const groups = [[], [], []];
    let group = 0;
    const collectText = node => {
      if (node.nodeType === Node.TEXT_NODE) {
        groups[group].push(node);
        return;
      }
      if (node === link) group = 1;
      Array.from(node.childNodes || []).forEach(collectText);
      if (node === link) group = 2;
    };
    collectText(el);
    const values = groups.map(nodes => nodes.map(node => node.textContent).join(''));
    if (values.some((value, index) => {
      const current = normalize(value);
      return (current !== rule.source[index] && current !== rule.target[index]) ||
        (!groups[index].length && rule.target[index]);
    })) return false;
    groups.forEach((nodes, index) => nodes.forEach((node, textIndex) => {
      const translated = textIndex === 0 ? rule.target[index] : '';
      if (node.textContent !== translated) node.textContent = translated;
    }));
    return true;
  }

  function translateCloudResourceNotice(el) {
    if (!el || !el.querySelectorAll || el.tagName === 'BODY' || el.tagName === 'HTML' ||
        !cloudResourceNoticeSources || !cloudResourceNoticeTargets) return false;
    const normalize = text => text.replace(/\s+/g, ' ').trim();
    const text = normalize(el.textContent || '');
    const firstSentence = cloudResourceNoticeSentences[0];
    if (!text.startsWith(firstSentence) && !text.startsWith(dictionary[firstSentence])) return false;
    const protectedContent = 'pre, code, .monaco-editor, textarea, input, script, style, [contenteditable="true"]';
    if ((el.closest && el.closest(protectedContent)) || el.querySelector(protectedContent)) return false;
    const links = Array.from(el.querySelectorAll('a, [role="link"]'));
    if (links.length && (links.length !== cloudResourceNoticeLinks.length ||
        links.some((link, index) => {
          const label = cloudResourceNoticeLinks[index];
          const current = normalize(link.textContent || '');
          return current !== label && current !== dictionary[label];
        }))) return false;
    const sources = links.length ? cloudResourceNoticeSources : [cloudResourceNoticeSources.join('')];
    const targets = links.length ? cloudResourceNoticeTargets : [cloudResourceNoticeTargets.join('')];
    const groups = Array.from({length: sources.length}, () => []);
    let group = 0;
    const collectText = node => {
      if (node.nodeType === Node.TEXT_NODE) {
        groups[group].push(node);
        return;
      }
      const linkIndex = links.indexOf(node);
      if (linkIndex !== -1) group = linkIndex * 2 + 1;
      Array.from(node.childNodes || []).forEach(collectText);
      if (linkIndex !== -1) group = linkIndex * 2 + 2;
    };
    collectText(el);
    const values = groups.map(nodes => nodes.map(node => node.textContent).join(''));
    const current = values.map(normalize);
    if (groups.some((nodes, index) => !nodes.length ||
        (current[index] !== normalize(sources[index]) && current[index] !== normalize(targets[index])))) return false;
    // Reorder wording around the existing links without replacing links or their text nodes.
    let changed = false;
    groups.forEach((nodes, index) => {
      if (values[index] === targets[index]) return;
      nodes.forEach((node, textIndex) => {
        const translated = textIndex === 0 ? targets[index] : '';
        if (node.textContent !== translated) {
          node.textContent = translated;
          changed = true;
        }
      });
    });
    return changed;
  }

  function repairRestorePageIcon(el) {
    if (!el || !el.getAttribute || !el.textContent || el.textContent.trim() !== 'restore_page') return false;
    const host = el.closest && el.closest(
      '[data-antigravity-icon-host="restore_page"], [class*="material-symbols"], [class*="material-icons"], [data-icon="restore_page"]');
    if (host) el = host;
    if (!el.textContent || el.textContent.trim() !== 'restore_page') return false;
    const protectedContent = 'pre, code, .monaco-editor, textarea, input, script, style, [contenteditable="true"]';
    if ((el.closest && el.closest(protectedContent)) ||
        (el.querySelector && el.querySelector(protectedContent))) return false;
    const iconClass = el.getAttribute('class') || '';
    const knownIcon = /(?:^|\s)material-(?:symbols|icons)(?:-[a-z]+)?(?:\s|$)/.test(iconClass) ||
      el.getAttribute('data-icon') === 'restore_page' ||
      el.getAttribute('data-antigravity-icon-host') === 'restore_page';
    const menuItem = el.closest && el.closest('[role="menuitem"], [role="option"]');
    const menuIcon = (el.tagName === 'SPAN' || el.tagName === 'I') && menuItem &&
      /Reopen Closed Tab|重新打开已关闭的标签页/.test(menuItem.textContent || '');
    if (!knownIcon && !menuIcon) return false;
    let svg = el.querySelector('svg[data-antigravity-icon="restore_page"]');
    if (!svg) {
      svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      const attributes = {
        viewBox: '0 0 24 24', width: '1em', height: '1em', fill: 'none', stroke: 'currentColor',
        'stroke-width': '1.7', 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
        'aria-hidden': 'true', focusable: 'false', 'data-antigravity-icon': 'restore_page'
      };
      Object.entries(attributes).forEach(([name, value]) => svg.setAttribute(name, value));
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z M14 2v6h6 M8 14h5a3 3 0 0 1 0 6h-1 M10 12l-2 2 2 2');
      svg.appendChild(path);
    }
    // Preserve the original text nodes so React can still update or remove them.
    const clearText = node => {
      if (node.nodeType === Node.TEXT_NODE) node.textContent = '';
      else Array.from(node.childNodes || []).forEach(clearText);
    };
    Array.from(el.childNodes).forEach(clearText);
    if (!svg.parentNode) el.appendChild(svg);
    el.setAttribute('data-antigravity-icon-host', 'restore_page');
    el.style.display = 'inline-flex';
    el.style.alignItems = 'center';
    el.style.justifyContent = 'center';
    el.style.lineHeight = '1';
    return true;
  }

  function processNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      // Avoid modifying code snippets or editable user content.
      if (node.parentElement && node.parentElement.closest &&
          node.parentElement.closest('pre, code, .monaco-editor, textarea, input, [contenteditable="true"]')) {
        return;
      }
      if (node.parentElement) {
        const deletionOwner = projectDeletionValueOwners.get(node);
        if (deletionOwner && deletionOwner.contains(node) && translateProjectDeletionPrompt(deletionOwner)) return;
        if (deletionOwner) projectDeletionValueOwners.delete(node);
        if (translateProjectDeletionPrompt(node.parentElement) ||
            (node.parentElement.parentElement && translateProjectDeletionPrompt(node.parentElement.parentElement))) return;
        if (translateArchiveRestore(node) || translateVoiceChatDuration(node)) return;
        if (translateArchiveToast(node.parentElement) ||
            (node.parentElement.parentElement && translateArchiveToast(node.parentElement.parentElement))) return;
        if (translateInlineNotice(node.parentElement) ||
            (node.parentElement.parentElement && translateInlineNotice(node.parentElement.parentElement))) return;
        if (translateVoicePresetPrefix(node)) return;
        const connectorOwner = connectorCountOwners.get(node);
        if (connectorOwner && translateConnectorCount(connectorOwner)) return;
        if (translateConnectorCount(node.parentElement) ||
            (node.parentElement.parentElement && translateConnectorCount(node.parentElement.parentElement))) return;
        if (translateCloudResourceNotice(node.parentElement) ||
            (node.parentElement.parentElement && translateCloudResourceNotice(node.parentElement.parentElement))) return;
        if (repairRestorePageIcon(node.parentElement)) return;
        if (checkEmptyContainer(node.parentElement) ||
            (node.parentElement.parentElement && checkEmptyContainer(node.parentElement.parentElement))) {
          return;
        }
      }
      const translated = translateText(node.textContent);
      if (translated !== node.textContent) {
        node.textContent = translated;
      }
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      if (node.tagName === 'SCRIPT' || node.tagName === 'STYLE' || node.tagName === 'CODE' || node.tagName === 'PRE') return;
      if (node.closest && node.closest('.monaco-editor, [contenteditable="true"]')) return;
      const textArea = node.tagName === 'TEXTAREA';
      if (!textArea) {
        translateProjectDeletionPrompt(node);
        translateArchiveToast(node);
        translateInlineNotice(node);
        translateConnectorCount(node);
        translateCloudResourceNotice(node);
        if (repairRestorePageIcon(node)) return;
        if (checkEmptyContainer(node)) return;
      }
      if (node.placeholder) {
        const translated = translateText(node.placeholder);
        if (translated !== node.placeholder) {
          node.placeholder = translated;
        }
      }
      if (node.title) {
        const translated = translateText(node.title);
        if (translated !== node.title) {
          node.title = translated;
        }
      }
      if (node.getAttribute && node.getAttribute('aria-label')) {
        const ariaLabel = node.getAttribute('aria-label');
        const translated = translateText(ariaLabel);
        if (translated !== ariaLabel) {
          node.setAttribute('aria-label', translated);
        }
      }
      // Recursively process child nodes
      if (!textArea) Array.from(node.childNodes).forEach(processNode);
    }
  }

  const observer = new MutationObserver((mutations) => {
    mutations.forEach(mutation => {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach(node => {
          processNode(node);
        });
      } else if (mutation.type === 'characterData') {
        processNode(mutation.target);
      } else if (mutation.type === 'attributes') {
        processNode(mutation.target);
      }
    });
  });

  document.addEventListener('DOMContentLoaded', () => {
    processNode(document.body);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ['placeholder', 'title', 'aria-label']
    });
  });
})();
"""

MENU_TRANSLATOR_INJECTION = r"""
// Antigravity Chinese Localization Engine - Menu
(function() {
  const menuTranslationMap = {
    'File': '文件', 'Edit': '编辑', 'View': '视图', 'Window': '窗口', 'Help': '帮助',
    'New Conversation': '新建对话', 'New Window': '新建窗口', 'Close Window': '关闭窗口',
    'Check for Updates': '检查更新', 'Checking for Updates...': '正在检查更新...',
    'Downloading Update...': '正在下载更新...', 'Restart to Update': '重启以应用更新',
    'Undo': '撤销', 'Redo': '重做', 'Cut': '剪切', 'Copy': '复制', 'Paste': '粘贴',
    'Rename': '重命名', 'Pin': '置顶', 'Mark Unread': '标记为未读',
    'Conversation Name': '对话名称', 'Conversation ID': '对话 ID', 'Project Name': '项目名称',
    'Copy Project Name': '复制项目名称', 'Project Settings': '项目设置',
    'Show in File Explorer': '在文件资源管理器中显示',
    'Archive': '归档', 'Delete': '删除',
    'Select All': '全选', 'Minimize': '最小化', 'Close': '关闭', 'Quit Antigravity': '退出 Antigravity',
    'About Antigravity': '关于 Antigravity', 'Services': '服务', 'Hide Antigravity': '隐藏 Antigravity',
    'Hide Others': '隐藏其他', 'Show All': '显示全部', 'Force Reload': '强制重新加载',
    'Reload': '重新加载', 'Actual Size': '实际大小', 'Zoom In': '放大', 'Zoom Out': '缩小',
    'Toggle Full Screen': '切换全屏',
    'Split': '分屏', 'Split Right': '向右分屏', 'Split Down': '向下分屏',
    'Replace With New': '替换为新建', 'Replace with New': '替换为新建'
  };
  function translateMenu(menuItem) {
    if (menuItem.label && menuTranslationMap[menuItem.label]) {
      menuItem.label = menuTranslationMap[menuItem.label];
    }
    if (menuItem.submenu && menuItem.submenu.items) {
      menuItem.submenu.items.forEach(translateMenu);
    }
    if (menuItem.submenu && Array.isArray(menuItem.submenu)) {
      menuItem.submenu.forEach(translateMenu);
    }
  }

  try {
    const { Menu } = require('electron');
    if (Menu && Menu.buildFromTemplate && !Menu.__isTranslated) {
      const originalBuildFromTemplate = Menu.buildFromTemplate;
      Menu.buildFromTemplate = function(template) {
        if (template && Array.isArray(template)) {
          template.forEach(translateMenu);
        }
        return originalBuildFromTemplate.call(this, template);
      };
      Menu.__isTranslated = true;
    }
  } catch(e) {
    console.error("Menu hooking failed:", e);
  }
})();
"""

def append_once(file_path, content, marker, name):
    if not os.path.exists(file_path):
        raise ValueError(f"缺少必需汉化文件：{file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        existing = f.read()
    
    if marker in existing:
        print(f"[状态] 发现已存在的 {name}，正在热更新词典...")
        idx = existing.find("// " + marker)
        if idx == -1:
            idx = existing.find(marker)
        if idx != -1:
            clean_content = existing[:idx].rstrip()
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(clean_content + "\n" + content + "\n")
            print(f"[成功] 词典热更新完成：{name} ({os.path.basename(file_path)})")
        return
    
    with open(file_path, "a", encoding="utf-8") as f:
        f.write("\n" + content + "\n")
    print(f"[成功] 注入完成：{name} ({os.path.basename(file_path)})")

def replace_in_file(file_path, target, replacement):
    if not os.path.exists(file_path):
        return
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    if replacement in content:
        print(f"[跳过] 目标已替换 ({os.path.basename(file_path)})")
        return
    content = content.replace(target, replacement)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[成功] 执行目标替换 ({os.path.basename(file_path)})")

REQUIRED_PATCH_FILES = ('dist/preload.js', 'dist/menu.js', 'dist/tray.js')


def _inject(stage):
    append_once(stage / 'dist/preload.js', DOM_TRANSLATOR_INJECTION,
                'Antigravity Chinese Localization Engine', 'Web UI Injection')
    append_once(stage / 'dist/menu.js', MENU_TRANSLATOR_INJECTION,
                'Antigravity Chinese Localization Engine - Menu', 'Menu Translator Injection')
    replace_in_file(stage / 'dist/tray.js', "'Show Antigravity'", "'显示 Antigravity'")
    replace_in_file(stage / 'dist/tray.js', "'Quit'", "'退出'")
    updater = stage / 'dist/updater.js'
    if updater.is_file():
        content = updater.read_text(encoding='utf-8')
        localized = content
        # Scope native dialog replacements to display properties, preserving update action keys.
        for field, original, translated in (
            ('title', 'Check for Updates', '检查更新'),
            ('message', 'No updates available', '暂无可用更新'),
        ):
            pattern = r"(\b" + field + r"\s*:\s*)(['\"])" + re.escape(original) + r"\2"
            localized = re.sub(pattern, lambda match: match[1] + match[2] + translated + match[2],
                               localized)
        if localized != content:
            updater.write_text(localized, encoding='utf-8')
            print('[成功] 已汉化原生更新弹窗 (updater.js)')
    loading = stage / 'dist/loadingOverlay.js'
    if loading.is_file():
        content = loading.read_text(encoding='utf-8')
        loading.write_text(content.replace('>Loading Antigravity<', '>正在加载 Antigravity<'),
                           encoding='utf-8')


def _stamp(path):
    info = path.stat()
    return info.st_size, info.st_mtime_ns, info.st_ino


def apply_patch(app_dir=None, no_launch=True):
    """Apply localization without launching; no_launch is kept for compatibility."""
    root = discover_install(app_dir)
    resources = resources_dir(root)
    archive = resources / 'app.asar'
    disabled = resources / 'app.asar.disabled'
    app = resources / 'app'
    if archive.exists() and disabled.exists():
        raise ValueError('同时发现 app.asar 和 app.asar.disabled，可能发生软件更新。请核对两个归档版本或修复官方安装后重试；未修改任何文件。')
    source = archive if archive.is_file() else disabled
    if not source.is_file():
        raise ValueError('未找到可验证的原始 app.asar 或 app.asar.disabled；已保留现有 app 目录。')
    print('[安装目录] ' + str(root))
    print('[执行] 从原始归档完整解包并校验外置依赖，准备汉化工作目录...')
    before = _stamp(source)
    stage = Path(tempfile.mkdtemp(prefix='.antigravity-localization-stage-', dir=str(resources)))
    previous = None
    installed = False
    committed = False
    moved_archive = False
    preserve_stage = False
    prepared = False
    switch_started = False
    try:
        extract_asar(source, stage, unpacked_dir=resources / 'app.asar.unpacked')
        validate_extracted_app(stage, REQUIRED_PATCH_FILES)
        _inject(stage)
        validate_extracted_app(stage, REQUIRED_PATCH_FILES)
        prepared = True
        if _stamp(source) != before:
            raise RuntimeError('准备期间原始归档发生变化，未切换安装。请关闭更新程序后重试。')
        print('[执行] 汉化文件校验通过，正在关闭当前安装的 Antigravity...')
        stop_application(root)
        if _stamp(source) != before or (source == archive and disabled.exists()) or (source == disabled and archive.exists()):
            raise RuntimeError('安装文件在切换前发生变化，未修改当前入口。')
        switch_started = True
        if app.exists():
            # Validate the exact directory before renaming it; never follow links.
            from antigravity_common import _no_link
            _no_link(app)
            if not app.is_dir() or app.resolve().parent != resources.resolve():
                raise ValueError('现有 app 不是预期安装目录中的普通目录。')
            previous = Path(tempfile.mkdtemp(prefix='.antigravity-localization-previous-', dir=str(resources)))
            previous.rmdir()
            app.rename(previous)
        stage.rename(app)
        installed = True
        if source == archive:
            archive.rename(disabled)
            moved_archive = True
        committed = True
    except BaseException:
        if not switch_started:
            # Preparation / process-stop failures may only discard staging.
            # There has been no active layout change for us to undo.
            raise
        # Never recursively delete the active app during rollback. Rename it
        # aside first, restore a launchable layout, then remove inactive files.
        rollback_errors = []
        archive_restored = True
        if moved_archive or (source == archive and not archive.exists() and disabled.is_file() and _stamp(disabled) == before):
            try:
                disabled.rename(archive)
            except (OSError, KeyboardInterrupt) as error:
                archive_restored = archive.is_file()
                if not archive_restored:
                    rollback_errors.append('原始归档恢复失败，已保留完整的新 app：' + str(error))
        new_active = installed or (not stage.exists() and app.exists())
        if archive_restored:
            if new_active:
                if previous is None and source == disabled:
                    # The input already had no active entry. Keep the validated
                    # app instead of rolling back into that broken layout.
                    rollback_errors.append('原安装没有可恢复的活动入口，已保留通过校验的新 app。')
                else:
                    try:
                        app.rename(stage)
                    except (OSError, KeyboardInterrupt) as error:
                        if app.exists():
                            rollback_errors.append('无法隔离新 app，已保留该完整目录：' + str(error))
            if previous is not None and previous.exists() and not app.exists():
                try:
                    previous.rename(app)
                except (OSError, KeyboardInterrupt) as error:
                    rollback_errors.append('旧工作目录恢复失败，保留位置：' + str(previous) + '；' + str(error))
                    if stage.exists() and not app.exists():
                        try:
                            stage.rename(app)
                        except (OSError, KeyboardInterrupt) as recovery_error:
                            rollback_errors.append('完整的新工作目录保留位置：' + str(stage) + '；' + str(recovery_error))
                            preserve_stage = True
            if prepared and switch_started and not app.exists() and not archive.exists() and stage.exists():
                try:
                    stage.rename(app)
                except (OSError, KeyboardInterrupt) as error:
                    preserve_stage = True
                    rollback_errors.append('请保留待恢复的完整工作目录：' + str(stage) + '；' + str(error))
        if rollback_errors:
            raise RuntimeError('汉化切换中断，部分回退未完成；请勿删除原始归档或保留目录。\\n' + '\\n'.join(rollback_errors))
        raise
    finally:
        if stage.exists() and not preserve_stage:
            remove_tree(stage, resources)
    if committed and previous is not None and previous.exists():
        try:
            remove_tree(previous, resources)
        except (OSError, ValueError) as error:
            raise RuntimeError('汉化已生效，但旧工作目录未清理完成：' + str(previous) + '；' + str(error))
    print('[完成] 汉化文件与主入口校验通过；原始归档保留为 app.asar.disabled，用于还原。')
    print('[提示] 本次运行不会自动启动 Antigravity；需要使用时请手动打开软件。')
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description='安全汉化 Antigravity：完整校验归档与依赖后切换，失败保留原始程序。')
    parser.add_argument('--app-dir', help='安装目录；macOS 指定 Antigravity.app')
    parser.add_argument('--no-launch', action='store_true', help='兼容旧命令；脚本始终不自动启动软件')
    args = parser.parse_args(argv)
    try:
        apply_patch(args.app_dir)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('[错误] ' + str(error))
        return 1
    except KeyboardInterrupt:
        print('[取消] 操作已中断，请查看是否有清理或回退错误。')
        return 130


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    result = main()
    if len(sys.argv) == 1 and sys.stdin.isatty():
        try:
            input('\n执行完毕，按 Enter 键退出...')
        except (EOFError, KeyboardInterrupt):
            pass
    sys.exit(result)
