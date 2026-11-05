# coding: utf-8
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from translation_integration import select_profile, prepare_bridge, preload_extension
from builtin_dictionary import load_builtin_catalog

from antigravity_common import (
    discover_install, extract_asar, remove_tree,
    resources_dir, stop_application, validate_extracted_app,
)

DOM_TRANSLATOR_INJECTION = r"""
// Antigravity Chinese Localization Engine
(function() {
  const dictionary = __BUILTIN_dictionary__;

  const coreWords = __BUILTIN_coreWords__;

  // Structured Prefix & Content Match Rules for Complex / Truncated Text
  const textPrefixRules = __BUILTIN_textPrefixRules__;

  function translateText(text) {
    if (!text || typeof text !== 'string') return text;
    let trimmed = text.trim();
    if (!trimmed) return text;

    if (dictionary[trimmed]) {
      return text.replace(trimmed, dictionary[trimmed]);
    }
    
    // Dynamic Regex Translations
    let m;
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

  function processNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      // Avoid modifying code snippets or editor content
      if (node.parentElement && node.parentElement.closest && node.parentElement.closest('pre, code, .monaco-editor')) {
        return;
      }
      if (node.parentElement) {
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
      if (checkEmptyContainer(node)) return;
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
      Array.from(node.childNodes).forEach(processNode);
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
      }
    });
  });

  document.addEventListener('DOMContentLoaded', () => {
    processNode(document.body);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true
    });
  });
})();
"""

MENU_TRANSLATOR_INJECTION = r"""
// Antigravity Chinese Localization Engine - Menu
(function() {
  const menuTranslationMap = __BUILTIN_menuTranslationMap__;
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

def _render_builtin_data(template, catalog):
    """Embed static data as JSON; translation functions and regex stay in code."""
    literals = {}
    for name in ('dictionary', 'coreWords', 'textPrefixRules', 'menuTranslationMap'):
        # Keep readable Chinese while escaping quotes and JS line separators.
        literal = json.dumps(catalog[name], ensure_ascii=False).replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
        literals[name] = literal
    # Only scan the original template, so marker-shaped translations stay data.
    return re.sub(r'__BUILTIN_(dictionary|coreWords|textPrefixRules|menuTranslationMap)__',
                  lambda match: literals[match.group(1)], template)


_builtin_catalog = load_builtin_catalog()
DOM_TRANSLATOR_INJECTION = _render_builtin_data(DOM_TRANSLATOR_INJECTION, _builtin_catalog)
MENU_TRANSLATOR_INJECTION = _render_builtin_data(MENU_TRANSLATOR_INJECTION, _builtin_catalog)
del _builtin_catalog


def append_once(file_path, content, marker, name, log=print):
    if not os.path.exists(file_path):
        raise ValueError(f"缺少必需汉化文件：{file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        existing = f.read()
    
    if marker in existing:
        log(f"[状态] 发现已存在的 {name}，正在热更新词典...")
        idx = existing.find("// " + marker)
        if idx == -1:
            idx = existing.find(marker)
        if idx != -1:
            clean_content = existing[:idx].rstrip()
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(clean_content + "\n" + content + "\n")
            log(f"[成功] 词典热更新完成：{name} ({os.path.basename(file_path)})")
        return
    
    with open(file_path, "a", encoding="utf-8") as f:
        f.write("\n" + content + "\n")
    log(f"[成功] 注入完成：{name} ({os.path.basename(file_path)})")

def replace_in_file(file_path, target, replacement, log=print):
    if not os.path.exists(file_path):
        return
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    if replacement in content:
        log(f"[跳过] 目标已替换 ({os.path.basename(file_path)})")
        return
    content = content.replace(target, replacement)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    log(f"[成功] 执行目标替换 ({os.path.basename(file_path)})")

REQUIRED_PATCH_FILES = ('dist/preload.js', 'dist/menu.js', 'dist/tray.js')


def build_dom_injection(profile=None):
    """A reviewed UI uses one observer; unreviewed versions retain legacy behavior."""
    if profile is None:
        return DOM_TRANSLATOR_INJECTION
    marker = '  const observer = new MutationObserver'
    if DOM_TRANSLATOR_INJECTION.count(marker) != 1:
        raise ValueError('词典注入结构改变，无法安全构造受限 UI 管线')
    # Keep dictionary/rule functions but never start the old unrestricted scan.
    return DOM_TRANSLATOR_INJECTION.split(marker, 1)[0] + preload_extension(profile) + '\n})();\n'


def _inject(stage, resources_root=None, log=print):
    # Match pristine, validated stage bytes before any localization changes.
    profile = select_profile(stage, resources_root=resources_root)
    dom_injection = build_dom_injection(profile)
    append_once(stage / 'dist/preload.js', dom_injection,
                'Antigravity Chinese Localization Engine', 'Web UI Injection', log=log)
    append_once(stage / 'dist/menu.js', MENU_TRANSLATOR_INJECTION,
                'Antigravity Chinese Localization Engine - Menu', 'Menu Translator Injection', log=log)
    replace_in_file(stage / 'dist/tray.js', "'Show Antigravity'", "'显示 Antigravity'", log=log)
    replace_in_file(stage / 'dist/tray.js', "'Quit'", "'退出'", log=log)
    loading = stage / 'dist/loadingOverlay.js'
    if loading.is_file():
        content = loading.read_text(encoding='utf-8')
        loading.write_text(content.replace('>Loading Antigravity<', '>正在加载 Antigravity<'),
                           encoding='utf-8')
    if profile is not None:
        prepare_bridge(stage, profile)
        log('[状态] 已安装经过精确指纹验证的 DragonGirl 桥接；AI 仍由用户配置控制。')
    else:
        log('[状态] 当前应用尚无已验证的 AI 桥接配置；仅启用现有词典汉化，不外发文案。')


def _stamp(path):
    info = path.stat()
    return info.st_size, info.st_mtime_ns, info.st_ino


def apply_patch(app_dir=None, no_launch=True, log=print, event=None):
    """Apply localization without launching; no_launch is kept for compatibility."""
    emit = event if event is not None else lambda step, status: None
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
    log('[安装目录] ' + str(root))
    log('[执行] 从原始归档完整解包并校验外置依赖，准备汉化工作目录...')
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
        _inject(stage, resources_root=resources, log=log)
        validate_extracted_app(stage, REQUIRED_PATCH_FILES)
        prepared = True
        emit('prepare', 'completed')
        if _stamp(source) != before:
            raise RuntimeError('准备期间原始归档发生变化，未切换安装。请关闭更新程序后重试。')
        log('[执行] 汉化文件校验通过，正在关闭当前安装的 Antigravity...')
        stop_application(root)
        emit('stop', 'completed')
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
        emit('activate', 'completed')
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
        emit('rollback', 'incomplete' if rollback_errors else 'completed')
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
    emit('cleanup', 'completed')
    log('[完成] 汉化文件与主入口校验通过；原始归档保留为 app.asar.disabled，用于还原。')
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description='安全汉化 Antigravity：完整校验归档与依赖后切换，失败保留原始程序。')
    parser.add_argument('--app-dir', help='安装目录；macOS 指定 Antigravity.app')
    parser.add_argument('--no-launch', action='store_true', help='兼容旧命令；汉化完成后始终只输出结果，不自动启动软件')
    parser.add_argument('--json', action='store_true', help='返回与管理器共用的结构化结果；须显式指定安装目录')
    args = parser.parse_args(argv)
    if args.json:
        from installation_service import InstallationService
        result = InstallationService().execute('apply', app_dir=args.app_dir, confirmed=True)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['ok'] else 1
    try:
        apply_patch(args.app_dir, args.no_launch)
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
