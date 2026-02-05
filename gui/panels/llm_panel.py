"""
LLM 配置面板 - 表格式管理多个 LLM 配置
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import Callable, Dict, Any, List


class LLMPanel(ttk.Frame):
    """LLM 配置面板"""
    
    # 提供商选项及默认 Base URL（与官方 llm_constants.py 保持一致）
    PROVIDERS = {
        "ollama": "http://localhost:11434/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "openai": "https://api.openai.com/v1",
        "moonshot": "https://api.moonshot.cn/v1",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4",
        "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
        "cerebras": "https://api.cerebras.ai/v1",
        "claude": "https://api.anthropic.com/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1",
        "custom": ""
    }
    
    # 中断键选项
    INTERRUPT_KEYS = ["ESC", "Backspace", "Delete"]
    
    # 处理方式定义（只保留润色和翻译）
    PROCESSOR_LABELS = {
        "润色": "润色：",
        "翻译": "翻译："
    }
    
    def __init__(self, parent, config: Dict[str, Any], on_change: Callable = None):
        """
        初始化 LLM 配置面板
        
        Args:
            parent: 父容器
            config: LLM 配置字典
            on_change: 配置变更回调
        """
        super().__init__(parent, padding=12)
        self.config = config
        self.on_change = on_change
        
        # LLM 配置列表，每项: {provider, base_url, api_key, model, status}
        self.llm_configs: List[Dict] = config.get('configs', [])
        
        # 确保每个配置有状态字段
        for cfg in self.llm_configs:
            if 'status' not in cfg:
                cfg['status'] = '❓'
        
        # 处理方式绑定（使用中文键名）
        processors = config.get('processors', {})
        # 兼容旧配置：尝试读取旧键名
        self.processor_vars = {
            "润色": tk.StringVar(value=processors.get('润色', processors.get('light', processors.get('deep', '')))),
            "翻译": tk.StringVar(value=processors.get('翻译', processors.get('translate', '')))
        }
        
        # 中断键显示映射
        interrupt_key = config.get('interrupt_key', 'escape')
        # 兼容旧值
        key_map = {'escape': 'ESC', 'backspace': 'Backspace', 'delete': 'Delete'}
        display_key = key_map.get(interrupt_key, interrupt_key)
        self.interrupt_var = tk.StringVar(value=display_key)
        
        self._create_ui()
        self._refresh_table()
        self._update_processor_options()
    
    def _create_ui(self):
        """创建界面"""
        # ==================== LLM 配置列表区域 ====================
        list_section = ttk.LabelFrame(self, text="LLM 配置列表", padding=8)
        list_section.pack(fill='both', expand=True, pady=(0, 12))
        
        # 表格
        columns = ("status", "provider", "model", "base_url")
        self.tree = ttk.Treeview(
            list_section,
            columns=columns,
            show="headings",
            height=3,
            selectmode="browse"
        )
        
        self.tree.heading("status", text="状态")
        self.tree.heading("provider", text="提供商")
        self.tree.heading("model", text="模型")
        self.tree.heading("base_url", text="Base URL")
        
        self.tree.column("status", width=50, anchor="center")
        self.tree.column("provider", width=80)
        self.tree.column("model", width=140)
        self.tree.column("base_url", width=180)
        
        self.tree.pack(fill='both', expand=True)
        self.tree.bind("<Double-1>", lambda e: self._edit_config())
        
        # 按钮区
        btn_frame = ttk.Frame(list_section)
        btn_frame.pack(fill='x', pady=(8, 0))
        
        ttk.Button(
            btn_frame,
            text="+ 添加",
            command=self._add_config,
            bootstyle="success-outline"
        ).pack(side='left', padx=(0, 8))
        
        ttk.Button(
            btn_frame,
            text="✎ 编辑",
            command=self._edit_config,
            bootstyle="info-outline"
        ).pack(side='left', padx=(0, 8))
        
        ttk.Button(
            btn_frame,
            text="- 删除",
            command=self._delete_config,
            bootstyle="danger-outline"
        ).pack(side='left', padx=(0, 8))
        
        ttk.Button(
            btn_frame,
            text="🔗 测试全部",
            command=self._test_all_configs,
            bootstyle="warning-outline"
        ).pack(side='left')
        
        # ==================== 处理方式区域 ====================
        proc_section = ttk.LabelFrame(self, text="处理方式", padding=8)
        proc_section.pack(fill='x')
        
        self.processor_combos = {}
        
        for proc_key, label_text in self.PROCESSOR_LABELS.items():
            row = ttk.Frame(proc_section)
            row.pack(fill='x', pady=3)
            
            ttk.Label(row, text=label_text, width=10).pack(side='left')
            
            combo = ttk.Combobox(
                row,
                textvariable=self.processor_vars[proc_key],
                state="readonly",
                width=30
            )
            combo.pack(side='left', padx=(8, 0))
            combo.bind("<<ComboboxSelected>>", lambda e: self._on_config_change())
            
            self.processor_combos[proc_key] = combo
        
        # 中断键
        interrupt_row = ttk.Frame(proc_section)
        interrupt_row.pack(fill='x', pady=(8, 0))
        
        ttk.Label(interrupt_row, text="中断键：", width=10).pack(side='left')
        interrupt_combo = ttk.Combobox(
            interrupt_row,
            textvariable=self.interrupt_var,
            values=self.INTERRUPT_KEYS,
            state="readonly",
            width=12
        )
        interrupt_combo.pack(side='left', padx=(8, 0))
        interrupt_combo.bind("<<ComboboxSelected>>", lambda e: self._on_config_change())
    
    def _refresh_table(self):
        """刷新表格数据"""
        # 清空
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 填充
        for i, cfg in enumerate(self.llm_configs):
            self.tree.insert("", "end", iid=str(i), values=(
                cfg.get('status', '❓'),
                cfg.get('provider', ''),
                cfg.get('model', ''),
                self._truncate_url(cfg.get('base_url', ''))
            ))
    
    def _truncate_url(self, url: str, max_len: int = 25) -> str:
        """截断 URL 显示"""
        if len(url) > max_len:
            return url[:max_len] + "..."
        return url
    
    def _update_processor_options(self):
        """更新处理方式下拉选项"""
        options = []
        for cfg in self.llm_configs:
            label = f"{cfg.get('provider', '')} / {cfg.get('model', '')}"
            options.append(label)
        
        for combo in self.processor_combos.values():
            combo['values'] = options
    
    def _get_config_label(self, cfg: Dict) -> str:
        """获取配置的显示标签"""
        return f"{cfg.get('provider', '')} / {cfg.get('model', '')}"
    
    def _add_config(self):
        """添加配置"""
        dialog = LLMConfigDialog(self, title="添加 LLM 配置")
        self.wait_window(dialog)
        
        if dialog.result:
            dialog.result['status'] = '❓'
            self.llm_configs.append(dialog.result)
            self._refresh_table()
            self._update_processor_options()
            self._on_config_change()
    
    def _edit_config(self):
        """编辑配置"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要编辑的配置")
            return
        
        idx = int(selection[0])
        cfg = self.llm_configs[idx]
        
        dialog = LLMConfigDialog(self, title="编辑 LLM 配置", config=cfg)
        self.wait_window(dialog)
        
        if dialog.result:
            dialog.result['status'] = '❓'  # 编辑后重置状态
            self.llm_configs[idx] = dialog.result
            self._refresh_table()
            self._update_processor_options()
            self._on_config_change()
    
    def _delete_config(self):
        """删除配置"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要删除的配置")
            return
        
        if messagebox.askyesno("确认", "确定要删除此配置吗？"):
            idx = int(selection[0])
            del self.llm_configs[idx]
            self._refresh_table()
            self._update_processor_options()
            self._on_config_change()
    
    def _test_all_configs(self):
        """测试全部配置"""
        if not self.llm_configs:
            messagebox.showinfo("提示", "没有配置可测试")
            return
        
        # 在后台线程测试
        def do_test():
            for i, cfg in enumerate(self.llm_configs):
                try:
                    success = self._test_single_config(cfg)
                    cfg['status'] = '✅' if success else '❌'
                except Exception as e:
                    cfg['status'] = '❌'
                
                # 更新 UI
                self.after(0, self._refresh_table)
            
            self.after(0, lambda: messagebox.showinfo("完成", "测试完成"))
        
        # 先全部设为测试中
        for cfg in self.llm_configs:
            cfg['status'] = '⏳'
        self._refresh_table()
        
        threading.Thread(target=do_test, daemon=True).start()
    
    def _test_single_config(self, cfg: Dict) -> bool:
        """测试单个配置"""
        import requests
        
        provider = cfg.get('provider', '')
        base_url = cfg.get('base_url', '').rstrip('/')
        api_key = cfg.get('api_key', '')
        model = cfg.get('model', '')
        
        try:
            if provider == 'ollama':
                # Ollama 测试：获取模型列表
                # 移除 OpenAI 兼容接口的 /v1 后缀，改用 native API
                ollama_url = base_url[:-3] if base_url.endswith('/v1') else base_url
                resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
                return resp.status_code == 200

            else:
                # OpenAI 兼容 API 测试
                headers = {"Authorization": f"Bearer {api_key}"}
                resp = requests.get(f"{base_url}/models", headers=headers, timeout=10)
                return resp.status_code == 200
        except:
            return False
    
    def _on_config_change(self):
        """配置变更"""
        self.config['configs'] = self.llm_configs
        self.config['processors'] = {
            key: var.get() for key, var in self.processor_vars.items()
        }
        self.config['interrupt_key'] = self.interrupt_var.get()
        
        if self.on_change:
            self.on_change()
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        # 保存时去掉 status 字段
        configs_clean = []
        for cfg in self.llm_configs:
            clean = {k: v for k, v in cfg.items() if k != 'status'}
            configs_clean.append(clean)
        
        # 将显示值转换回内部值
        display_to_key = {'ESC': 'escape', 'Backspace': 'backspace', 'Delete': 'delete'}
        interrupt_display = self.interrupt_var.get()
        interrupt_key = display_to_key.get(interrupt_display, interrupt_display.lower())
        
        return {
            'configs': configs_clean,
            'processors': {
                key: var.get() for key, var in self.processor_vars.items()
            },
            'interrupt_key': interrupt_key
        }


class LLMConfigDialog(tk.Toplevel):
    """LLM 配置编辑对话框"""
    
    PROVIDERS = {
        "ollama": "http://localhost:11434/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "openai": "https://api.openai.com/v1",
        "moonshot": "https://api.moonshot.cn/v1",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4",
        "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
        "cerebras": "https://api.cerebras.ai/v1",
        "claude": "https://api.anthropic.com/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta",
        "custom": ""
    }
    
    COMMON_MODELS = {
        "ollama": [],  # 动态获取
        "deepseek": ["deepseek-chat", "deepseek-reasoner"],
        "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1", "o1-mini", "o3-mini"],
        "moonshot": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "zhipu": ["glm-4-plus", "glm-4-flash", "glm-4", "glm-3-turbo"],
        "volcengine": ["doubao-pro-4k", "doubao-lite-4k", "doubao-pro-32k"],
        "cerebras": ["llama3.1-8b", "llama3.1-70b"],
        "claude": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307", "claude-3-opus-20240229"],
        "gemini": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "custom": []
    }
    
    def __init__(self, parent, title: str, config: Dict = None):
        super().__init__(parent)
        self.result = None
        self.config = config or {}
        
        self.title(title)
        self.transient(parent)
        self.grab_set()
        
        # 变量
        self.provider_var = tk.StringVar(value=self.config.get('provider', 'ollama'))
        self.base_url_var = tk.StringVar(value=self.config.get('base_url', self.PROVIDERS['ollama']))
        self.api_key_var = tk.StringVar(value=self.config.get('api_key', ''))
        self.model_var = tk.StringVar(value=self.config.get('model', ''))
        
        self._create_ui()
        self._update_provider_ui()
        
        # 居中
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_ui(self):
        """创建界面"""
        main = ttk.Frame(self, padding=16)
        main.pack(fill='both', expand=True)
        
        # 提供商
        row1 = ttk.Frame(main)
        row1.pack(fill='x', pady=(0, 8))
        
        ttk.Label(row1, text="提供商：", width=10).pack(side='left')
        self.provider_combo = ttk.Combobox(
            row1,
            textvariable=self.provider_var,
            values=list(self.PROVIDERS.keys()),
            state="readonly",
            width=20
        )
        self.provider_combo.pack(side='left', padx=(8, 0))
        self.provider_combo.bind("<<ComboboxSelected>>", self._on_provider_change)
        
        # Base URL
        row2 = ttk.Frame(main)
        row2.pack(fill='x', pady=(0, 8))
        
        ttk.Label(row2, text="Base URL：", width=10).pack(side='left')
        self.base_url_entry = ttk.Entry(
            row2,
            textvariable=self.base_url_var,
            width=35
        )
        self.base_url_entry.pack(side='left', padx=(8, 0))
        
        # API Key
        row3 = ttk.Frame(main)
        row3.pack(fill='x', pady=(0, 8))
        
        ttk.Label(row3, text="API Key：", width=10).pack(side='left')
        self.api_key_entry = ttk.Entry(
            row3,
            textvariable=self.api_key_var,
            show="*",
            width=28
        )
        self.api_key_entry.pack(side='left', padx=(8, 0))
        
        self.show_key = False
        self.show_btn = ttk.Button(
            row3,
            text="显示",
            width=4,
            command=self._toggle_key_visibility,
            bootstyle="secondary-outline"
        )
        self.show_btn.pack(side='left', padx=(8, 0))
        
        # 模型
        row4 = ttk.Frame(main)
        row4.pack(fill='x', pady=(0, 8))
        
        ttk.Label(row4, text="模型：", width=10).pack(side='left')
        self.model_combo = ttk.Combobox(
            row4,
            textvariable=self.model_var,
            width=25
        )
        self.model_combo.pack(side='left', padx=(8, 0))
        
        self.sync_btn = ttk.Button(
            row4,
            text="🔄 同步",
            command=self._sync_models,
            bootstyle="secondary-outline"
        )
        self.sync_btn.pack(side='left', padx=(8, 0))
        
        # 按钮区
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(16, 0))
        
        ttk.Button(
            btn_frame,
            text="取消",
            command=self.destroy,
            bootstyle="secondary"
        ).pack(side='right', padx=(8, 0))
        
        ttk.Button(
            btn_frame,
            text="保存",
            command=self._save,
            bootstyle="success"
        ).pack(side='right', padx=(8, 0))
        
        ttk.Button(
            btn_frame,
            text="测试",
            command=self._test,
            bootstyle="warning"
        ).pack(side='right')
    
    def _on_provider_change(self, event=None):
        """提供商变更"""
        provider = self.provider_var.get()
        
        # 更新 Base URL
        self.base_url_var.set(self.PROVIDERS.get(provider, ''))
        
        self._update_provider_ui()
    
    def _update_provider_ui(self):
        """根据提供商更新 UI"""
        provider = self.provider_var.get()
        
        # 更新模型列表
        models = self.COMMON_MODELS.get(provider, [])
        self.model_combo['values'] = models
        
        # 只有 Ollama 显示同步按钮
        if provider == 'ollama':
            self.sync_btn.pack(side='left', padx=(8, 0))
        else:
            self.sync_btn.pack_forget()
    
    def _toggle_key_visibility(self):
        """切换 API Key 可见性"""
        self.show_key = not self.show_key
        self.api_key_entry.configure(show="" if self.show_key else "*")
        self.show_btn.configure(text="隐藏" if self.show_key else "显示")
    
    def _sync_models(self):
        """同步 Ollama 模型"""
        import requests
        
        base_url = self.base_url_var.get().rstrip('/')
        # 移除 OpenAI 兼容接口的 /v1 后缀
        if self.provider_var.get() == 'ollama' and base_url.endswith('/v1'):
            base_url = base_url[:-3]
        
        try:
            resp = requests.get(f"{base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                models = [m['name'] for m in data.get('models', [])]
                self.model_combo['values'] = models
                messagebox.showinfo("成功", f"获取到 {len(models)} 个模型")
            else:
                messagebox.showerror("失败", f"请求失败: {resp.status_code}")
        except Exception as e:
            messagebox.showerror("失败", f"连接失败: {e}")
    
    def _test(self):
        """测试配置"""
        import requests
        
        provider = self.provider_var.get()
        base_url = self.base_url_var.get().rstrip('/')
        api_key = self.api_key_var.get()
        
        try:
            if provider == 'ollama':
                ollama_url = base_url[:-3] if base_url.endswith('/v1') else base_url
                resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
                success = resp.status_code == 200
            else:
                headers = {"Authorization": f"Bearer {api_key}"}
                resp = requests.get(f"{base_url}/models", headers=headers, timeout=10)
                success = resp.status_code == 200
            
            if success:
                messagebox.showinfo("成功", "连接测试通过！")
            else:
                messagebox.showerror("失败", f"测试失败: {resp.status_code}")
        except Exception as e:
            messagebox.showerror("失败", f"连接失败: {e}")
    
    def _save(self):
        """保存配置"""
        model = self.model_var.get().strip()
        if not model:
            messagebox.showwarning("提示", "请输入模型名称")
            return
        
        self.result = {
            'provider': self.provider_var.get(),
            'base_url': self.base_url_var.get(),
            'api_key': self.api_key_var.get(),
            'model': model
        }
        self.destroy()
