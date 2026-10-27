# coding: utf-8
"""Independent settings editor. Importing this module never opens GUI or network."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from urllib.parse import urlsplit
from translation_config import DataError, PROVIDERS, UserStore, validate_config


class SettingsController:
    """Headless-testable edits; saving, cancellation and reload are explicit."""
    def __init__(self, store=None):
        self.store = store or UserStore()
        self.config = None
        self.dictionary = None

    def reload(self):
        config = self.store.read_config()
        dictionary = self.store.read_dictionary()
        self.config, self.dictionary = config, dictionary
        return copy.deepcopy(config)

    def save(self, draft, plaintext_confirmed=False):
        if self.config is None:
            raise DataError('请先成功加载现有配置；不会覆盖损坏文件。')
        validate_config(draft)
        if any(profile['apiKey'] for profile in draft['providers'].values()) and not plaintext_confirmed:
            raise DataError('保存密钥前须明确确认明文保存风险。')
        self.config = self.store.save_config(draft, expected_revision=self.config['revision'])
        return copy.deepcopy(self.config)

    def entries(self, query=''):
        query = query.casefold()
        return [(key, item) for key, item in sorted(self.dictionary['entries'].items())
                if query in key.casefold() or query in item['translation'].casefold()]

    def set_entry(self, source, translation):
        self.dictionary = self.store.set_entry(source, translation,
            expected_revision=self.dictionary['revision'])

    def delete_entry(self, source):
        self.dictionary = self.store.delete_entry(source,
            expected_revision=self.dictionary['revision'])


PROBE_STATUSES = {
    'connected': '连接测试成功（固定测试文案，不代表应用桥接已验证）。',
    'invalid_configuration': '配置不完整或无效。',
    'configuration_changed': '配置在确认后发生变化；未发起请求，请重新确认。',
    'invalid_endpoint': '地址不受支持；只接受公共 HTTPS 域名。',
    'authentication_failed': '认证失败，请检查已保存的提供商和密钥。',
    'rate_limited': '提供商限流或额度不足。',
    'provider_unavailable': '提供商暂不可用。',
    'invalid_response': '提供商返回的内容无效。',
    'timeout': '连接测试超时。',
    'cancelled': '连接测试已取消。',
    'network_error': '网络请求失败。',
    'unavailable': '连接测试不可用，请检查 Node 和运行时资源。',
}


def probe_command():
    node = shutil.which('node')
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    probe = root / 'localization_runtime' / 'probe.cjs'
    if not node or not probe.is_file():
        raise DataError('连接测试需要 Node.js 和完整的运行时资源；未发起网络请求。')
    return [node, str(probe), '--confirm-network']


def run_confirmed_probe(command, timeout=70):
    """Call only following an explicit GUI confirmation; never return raw stderr."""
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, encoding='utf-8', timeout=timeout, check=False,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if len(result.stdout) > 4096:
            return 'unavailable'
        value = json.loads(result.stdout)
        status = value.get('status') if isinstance(value, dict) else None
        if status not in PROBE_STATUSES:
            return 'unavailable'
        if status == 'connected' and (value.get('ok') is not True or result.returncode != 0):
            return 'invalid_response'
        return status
    except subprocess.TimeoutExpired:
        return 'timeout'
    except (OSError, ValueError, UnicodeError):
        return 'unavailable'


def main():
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        print('无法启动设置界面：此 Python 未安装 tkinter。请使用包含 Tk 的 Python 或已打包的设置工具。')
        return 2

    class SettingsWindow:
        def __init__(self, root):
            self.root = root
            self.controller = SettingsController()
            self.draft = None
            self.active_provider = 'openai'
            self.busy = False
            self.probe_running = False
            self.probe_result = None
            root.title('DragonGirl 翻译设置')
            root.geometry('870x690')
            root.minsize(700, 540)
            outer = ttk.Frame(root, padding=12)
            outer.pack(fill='both', expand=True)
            ttk.Label(outer, text='AI 默认关闭。开启后，仅筛选的界面文案会发给所选提供商，并可能产生费用。', wraplength=800).pack(anchor='w')
            ttk.Label(outer, text='密钥按明文保存在当前用户目录；不等于加密。请勿共享文件或使用公共账户。', wraplength=800).pack(anchor='w')
            ttk.Label(outer, text='数据目录：' + str(self.controller.store.directory), wraplength=800).pack(anchor='w', pady=(3, 8))
            notebook = ttk.Notebook(outer)
            notebook.pack(fill='both', expand=True)
            config_tab = ttk.Frame(notebook, padding=10)
            dict_tab = ttk.Frame(notebook, padding=10)
            notebook.add(config_tab, text='AI 配置')
            notebook.add(dict_tab, text='个人词典')
            self.enabled = tk.BooleanVar(value=False)
            self.auto_save = tk.BooleanVar(value=False)
            ttk.Checkbutton(config_tab, text='启用 AI 补译（需要已验证的应用桥接；保存不代表桥接已可用）', variable=self.enabled).grid(row=0, column=0, columnspan=2, sticky='w')
            ttk.Checkbutton(config_tab, text='自动保存已验证的 AI 译文（关闭时仅会话缓存）', variable=self.auto_save).grid(row=1, column=0, columnspan=2, sticky='w')
            self.provider = tk.StringVar(value='openai')
            ttk.Label(config_tab, text='提供商').grid(row=2, column=0, sticky='w', pady=8)
            selector = ttk.Combobox(config_tab, textvariable=self.provider, values=PROVIDERS, state='readonly')
            selector.grid(row=2, column=1, sticky='ew')
            selector.bind('<<ComboboxSelected>>', self.switch_provider)
            self.fields = {}
            for row, (name, label) in enumerate((('baseUrl', 'API Base URL（HTTPS）'), ('model', '模型名称'), ('apiKey', 'API 密钥')), 3):
                ttk.Label(config_tab, text=label).grid(row=row, column=0, sticky='w', pady=8)
                variable = tk.StringVar()
                self.fields[name] = variable
                entry = ttk.Entry(config_tab, textvariable=variable, show='•' if name == 'apiKey' else '')
                entry.grid(row=row, column=1, sticky='ew')
                if name == 'apiKey':
                    self.key_entry = entry
            self.show_key = tk.BooleanVar(value=False)
            ttk.Checkbutton(config_tab, text='显示密钥', variable=self.show_key,
                command=lambda: self.key_entry.configure(show='' if self.show_key.get() else '•')).grid(row=6, column=1, sticky='w')
            ttk.Label(config_tab, text='地址变更会改变密钥发送目标。原生接口各用独立协议；兼容接口使用 Chat Completions。\n模型需手动填写，不会自动联网获取。Windows 文件访问权限由您的账户 ACL 控制，请自行核查。', wraplength=680).grid(row=7, column=0, columnspan=2, sticky='w', pady=12)
            actions = ttk.Frame(config_tab)
            actions.grid(row=8, column=0, columnspan=2, sticky='w')
            ttk.Button(actions, text='保存配置', command=self.save).pack(side='left', padx=(0, 8))
            ttk.Button(actions, text='取消编辑 / 重新加载', command=self.reload_confirmed).pack(side='left', padx=8)
            ttk.Button(actions, text='测试连接', command=self.test_connection).pack(side='left', padx=8)
            ttk.Button(actions, text='清除会话缓存', command=self.clear_cache).pack(side='left', padx=8)
            config_tab.columnconfigure(1, weight=1)
            self.query = tk.StringVar()
            search = ttk.Entry(dict_tab, textvariable=self.query)
            search.pack(fill='x')
            self.query.trace_add('write', lambda *_: self.render_dictionary())
            self.tree = ttk.Treeview(dict_tab, columns=('original', 'translation', 'origin'), show='headings', height=10)
            for name, label, width in (('original', '原文', 280), ('translation', '译文', 280), ('origin', '来源', 80)):
                self.tree.heading(name, text=label)
                self.tree.column(name, width=width)
            self.tree.pack(fill='both', expand=True, pady=8)
            self.tree.bind('<<TreeviewSelect>>', self.select_entry)
            self.original = tk.StringVar()
            self.translation = tk.StringVar()
            ttk.Label(dict_tab, text='原文（修改原文会创建新条目，不会自动删除旧条目）').pack(anchor='w')
            ttk.Entry(dict_tab, textvariable=self.original).pack(fill='x')
            ttk.Label(dict_tab, text='译文').pack(anchor='w')
            ttk.Entry(dict_tab, textvariable=self.translation).pack(fill='x')
            dict_actions = ttk.Frame(dict_tab)
            dict_actions.pack(anchor='w', pady=8)
            ttk.Button(dict_actions, text='保存词条', command=self.save_entry).pack(side='left')
            ttk.Button(dict_actions, text='删除词条', command=self.delete_entry).pack(side='left', padx=8)
            ttk.Button(dict_actions, text='刷新词典', command=self.refresh_dictionary).pack(side='left')
            self.status = tk.StringVar(value='尚未加载')
            ttk.Label(outer, textvariable=self.status, wraplength=800).pack(anchor='w', pady=(8, 0))
            root.protocol('WM_DELETE_WINDOW', self.close)
            self.load()

        def perform(self, operation):
            if self.busy:
                return
            self.busy = True
            try:
                operation()
            except DataError as error:
                self.status.set(str(error))
                messagebox.showerror('未完成', str(error), parent=self.root)
            except OSError:
                self.status.set('文件读取或保存失败；请检查权限、磁盘空间及锁状态。原有数据未主动清空。')
                messagebox.showerror('未完成', self.status.get(), parent=self.root)
            finally:
                self.busy = False

        def capture(self):
            if self.draft is None:
                raise DataError('现有配置加载失败，不能覆盖保存。')
            self.draft['providers'][self.active_provider] = {key: variable.get().strip() for key, variable in self.fields.items()}
            self.draft['enabled'] = self.enabled.get()
            self.draft['autoSave'] = self.auto_save.get()
            self.draft['provider'] = self.provider.get()

        def display_provider(self):
            self.show_key.set(False)
            self.key_entry.configure(show='•')
            for key, variable in self.fields.items():
                variable.set(self.draft['providers'][self.active_provider][key])

        def switch_provider(self, _event=None):
            if self.draft is None:
                return
            self.capture()
            self.active_provider = self.provider.get()
            self.display_provider()

        def load(self):
            def operation():
                self.draft = self.controller.reload()
                self.active_provider = self.draft['provider']
                self.provider.set(self.active_provider)
                self.enabled.set(self.draft['enabled'])
                self.auto_save.set(self.draft['autoSave'])
                self.display_provider()
                self.render_dictionary()
                self.status.set('配置已加载；未发起任何网络请求。')
            self.perform(operation)

        def reload_confirmed(self):
            if messagebox.askyesno('放弃未保存编辑？', '将从磁盘重新加载配置和词典。', parent=self.root):
                self.load()

        def save(self):
            def operation():
                self.capture()
                validate_config(self.draft)
                has_keys = any(item['apiKey'] for item in self.draft['providers'].values())
                if has_keys and not messagebox.askyesno('确认明文保存密钥', '密钥将以明文保存在所示用户目录。文件或账户泄露可能造成费用损失。确认保存？', parent=self.root):
                    self.status.set('已取消；未保存。')
                    return
                self.draft = self.controller.save(self.draft, plaintext_confirmed=has_keys)
                self.status.set('配置已保存；这不代表应用桥接已经验证或连接测试通过。')
            self.perform(operation)

        def test_connection(self):
            if self.probe_running:
                return
            def operation():
                command = probe_command()
                saved = self.controller.store.read_config()
                profile = saved['providers'][saved['provider']]
                if not all(profile.get(key, '').strip() for key in ('baseUrl', 'model', 'apiKey')):
                    raise DataError('请先保存完整的提供商、模型和密钥配置。')
                target = urlsplit(profile['baseUrl']).netloc
                if not messagebox.askyesno('确认发起网络测试',
                    '将使用磁盘上已保存的配置（不含尚未保存的编辑），向 ' + target +
                    ' 发送固定文案 Open settings。此操作使用您的密钥并可能产生费用。继续？', parent=self.root):
                    self.status.set('已取消连接测试；未发起网络请求。')
                    return
                command.extend(['--revision', str(saved['revision'])])
                self.probe_running = True
                self.probe_result = None
                self.status.set('正在测试已保存的配置；不发送工作区或对话内容。')
                def worker():
                    self.probe_result = run_confirmed_probe(command)
                threading.Thread(target=worker, daemon=True).start()
                self.root.after(100, self.poll_probe)
            self.perform(operation)

        def poll_probe(self):
            if self.probe_result is None:
                self.root.after(100, self.poll_probe)
                return
            self.probe_running = False
            self.status.set(PROBE_STATUSES[self.probe_result])

        def clear_cache(self):
            def operation():
                self.controller.store.clear_cache()
                # Do not advance our edit revision: another writer may also have
                # changed settings. A later save must reload, not overwrite it.
                self.status.set('已写入缓存失效标记；桥接下次读取时生效。再次保存配置前请重新加载。')
            self.perform(operation)

        def render_dictionary(self):
            if self.controller.dictionary is None:
                return
            self.tree.delete(*self.tree.get_children())
            for index, (original, item) in enumerate(self.controller.entries(self.query.get())):
                self.tree.insert('', 'end', iid=str(index), values=(original, item['translation'], item['source']))

        def select_entry(self, _event=None):
            selected = self.tree.selection()
            if selected:
                values = self.tree.item(selected[0], 'values')
                self.original.set(values[0])
                self.translation.set(values[1])

        def save_entry(self):
            def operation():
                if self.controller.dictionary is None:
                    raise DataError('词典未成功加载。')
                self.controller.set_entry(self.original.get(), self.translation.get())
                self.render_dictionary()
                self.status.set('词条已保存为手工条目，不会被 AI 自动覆盖。')
            self.perform(operation)

        def delete_entry(self):
            if not self.original.get().strip():
                return
            if not messagebox.askyesno('删除词条', '确认删除此原文对应的词条？在途 AI 结果不会恢复已删除条目。', parent=self.root):
                return
            def operation():
                if self.controller.dictionary is None:
                    raise DataError('词典未成功加载。')
                self.controller.delete_entry(self.original.get())
                self.original.set('')
                self.translation.set('')
                self.render_dictionary()
                self.status.set('词条已删除。')
            self.perform(operation)

        def refresh_dictionary(self):
            def operation():
                self.controller.dictionary = self.controller.store.read_dictionary()
                self.render_dictionary()
                self.status.set('词典已刷新。')
            self.perform(operation)

        def close(self):
            if self.probe_running:
                messagebox.showinfo('连接测试进行中', '请等待测试返回或超时后关闭，避免留下未完成的网络请求。', parent=self.root)
                return
            if messagebox.askyesno('关闭设置', '未点击保存的编辑会被丢弃。确定关闭？', parent=self.root):
                self.root.destroy()

    try:
        root = tk.Tk()
    except tk.TclError:
        print('无法启动图形界面：缺少可用显示环境。未修改任何配置。')
        return 2
    SettingsWindow(root)
    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
