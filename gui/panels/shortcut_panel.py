"""
语音输入场景配置面板 - 紧凑表格 + 编辑对话框
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Dict, Any, List, Optional
from pathlib import Path

# 导入 keyboard 库用于全局按键捕获
try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False


class KeyCaptureDialog(tk.Toplevel):
    """按键捕获对话框 - 使用 keyboard 库实现全局按键拦截"""
    
    # 修饰键名称映射
    MODIFIER_KEYS = {
        'ctrl', 'left ctrl', 'right ctrl',
        'alt', 'left alt', 'right alt',
        'shift', 'left shift', 'right shift',
        'windows', 'left windows', 'right windows',
    }
    
    # 按键名称标准化映射
    KEY_NORMALIZE_MAP = {
        'left ctrl': 'Ctrl', 'right ctrl': 'Ctrl', 'ctrl': 'Ctrl',
        'left alt': 'Alt', 'right alt': 'Alt', 'alt': 'Alt',
        'left shift': 'Shift', 'right shift': 'Shift', 'shift': 'Shift',
        'left windows': 'Win', 'right windows': 'Win', 'windows': 'Win',
        'caps lock': 'CapsLock',
        'space': 'Space',
        'enter': 'Enter',
        'backspace': 'Backspace',
        'tab': 'Tab',
        'escape': 'Esc',
        'insert': 'Insert',
        'delete': 'Delete',
        'home': 'Home',
        'end': 'End',
        'page up': 'PageUp',
        'page down': 'PageDown',
        'up': 'Up', 'down': 'Down', 'left': 'Left', 'right': 'Right',
        'print screen': 'PrintScreen',
        'scroll lock': 'ScrollLock',
        'pause': 'Pause',
        'num lock': 'NumLock',
    }
    
    def __init__(self, parent, current_key: str, current_type: str, on_confirm: Callable[[str, str], None]):
        super().__init__(parent)
        
        self.on_confirm = on_confirm
        self.current_key = current_key
        self.current_type = current_type
        self.captured_keys = set()  # 当前按下的键
        self.final_combo = ""  # 最终组合键
        self.has_changes = False  # 是否有修改
        self.is_capturing = False  # 是否正在捕获
        self._hook = None  # keyboard 钩子
        
        self._setup_window()
        self._create_ui()
    
    def _setup_window(self):
        """设置窗口"""
        self.title("设置快捷键")
        self.resizable(False, False)
        self.transient(self.master)
        self.grab_set()
        self.focus_force()
        
        # 居中
        self.update_idletasks()
        x = self.master.winfo_rootx() + (self.master.winfo_width() - 380) // 2
        y = self.master.winfo_rooty() + (self.master.winfo_height() - 420) // 2
        self.geometry(f"+{x}+{y}")
        
        # 绑定关闭事件
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_ui(self):
        """创建界面"""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # 说明
        ttk.Label(main_frame, text="请选择快捷键：").pack(anchor='w')
        
        # 常用快捷键列表（包含自定义选项）
        common_keys = [
            ("CapsLock", "caps_lock", "keyboard"),
            ("鼠标侧键 X2（前进键）", "x2", "mouse"),
            ("鼠标侧键 X1（后退键）", "x1", "mouse"),
            ("F12 功能键", "f12", "keyboard"),
            ("F11 功能键", "f11", "keyboard"),
            ("F10 功能键", "f10", "keyboard"),
            ("空格键", "space", "keyboard"),
            ("自定义按键...", "__custom__", "keyboard"),  # 自定义选项
        ]
        
        # 快捷键选择
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill='x', pady=12)
        
        # 默认选择值
        default_value = f"{self.current_key}|{self.current_type}"
        # 检查是否为预设之外的自定义键
        preset_keys = {f"{k}|{t}" for _, k, t in common_keys[:-1]}
        if default_value not in preset_keys:
            default_value = "__custom__|keyboard"
            self.final_combo = self.current_key
        
        self.key_var = tk.StringVar(value=default_value)
        
        for display, key, ktype in common_keys:
            value = f"{key}|{ktype}"
            rb = ttk.Radiobutton(
                list_frame,
                text=display,
                variable=self.key_var,
                value=value,
                command=self._on_selection_change
            )
            rb.pack(anchor='w', pady=2)
        
        # 自定义输入区域
        self.custom_frame = ttk.Frame(main_frame)
        self.custom_frame.pack(fill='x', padx=(24, 0))
        
        ttk.Label(self.custom_frame, text="点击「开始录制」按钮，然后按下按键", 
                  foreground="gray").pack(anchor='w', pady=(2, 8))
        
        # 按键显示区域
        capture_frame = ttk.Frame(self.custom_frame)
        capture_frame.pack(fill='x')
        
        self.capture_entry = ttk.Entry(capture_frame, width=28, state='readonly')
        self.capture_entry.pack(side='left', fill='x', expand=True)
        
        # 如果当前是自定义键，显示它
        if self.final_combo:
            self._set_entry_text(self.final_combo)
        
        # 录制按钮
        self.record_btn = ttk.Button(capture_frame, text="开始录制", 
                                      command=self._toggle_capture, width=10)
        self.record_btn.pack(side='left', padx=(8, 0))
        
        # 清除按钮
        clear_btn = ttk.Button(capture_frame, text="清除", command=self._clear_capture, width=6)
        clear_btn.pack(side='left', padx=(4, 0))
        
        # 状态提示
        self.status_label = ttk.Label(self.custom_frame, text="", foreground="blue")
        self.status_label.pack(anchor='w', pady=(8, 0))
        
        # 初始状态
        self._update_custom_visibility()
        
        # 按钮区域
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(24, 0))
        
        ttk.Button(btn_frame, text="保存", command=self._on_save, 
                   bootstyle="primary", width=10).pack(side='left')
        ttk.Button(btn_frame, text="取消", command=self._on_cancel, width=10).pack(side='left', padx=(8, 0))
    
    def _set_entry_text(self, text: str):
        """设置输入框文本"""
        self.capture_entry.configure(state='normal')
        self.capture_entry.delete(0, tk.END)
        self.capture_entry.insert(0, text)
        self.capture_entry.configure(state='readonly')
    
    def _toggle_capture(self):
        """切换捕获状态"""
        if self.is_capturing:
            self._stop_capture()
        else:
            self._start_capture()
    
    def _start_capture(self):
        """开始捕获按键"""
        if not HAS_KEYBOARD:
            messagebox.showerror("错误", "keyboard 库未安装，无法捕获按键", parent=self)
            return
        
        # 自动选择自定义选项
        self.key_var.set("__custom__|keyboard")
        self.has_changes = True
        
        self.is_capturing = True
        self.captured_keys.clear()
        self.record_btn.configure(text="停止录制", bootstyle="danger")
        self.status_label.configure(text="🎯 正在监听...按下按键组合", foreground="red")
        self._set_entry_text("等待按键...")
        
        # 注册全局按键钩子（suppress=True 阻止按键传递到其他程序）
        self._hook = keyboard.hook(self._on_keyboard_event, suppress=True)
    
    def _stop_capture(self):
        """停止捕获按键"""
        self.is_capturing = False
        self.record_btn.configure(text="开始录制", bootstyle="default")
        
        # 移除钩子
        if self._hook:
            keyboard.unhook(self._hook)
            self._hook = None
        
        # 生成最终组合键
        if self.captured_keys:
            self._finalize_combo()
        
        if self.final_combo:
            self.status_label.configure(text=f"✓ 已设置: {self.final_combo}", foreground="green")
        else:
            self.status_label.configure(text="")
            self._set_entry_text("")
    
    def _on_keyboard_event(self, event):
        """处理键盘事件"""
        if not self.is_capturing:
            return
        
        key_name = self._normalize_key(event.name)
        if not key_name:
            return
        
        if event.event_type == 'down':
            self.captured_keys.add(key_name)
            self._update_display()
        elif event.event_type == 'up':
            # 检查是否有非修饰键被释放，如果有则确定组合
            if key_name.lower() not in ('ctrl', 'alt', 'shift', 'win'):
                # 非修饰键释放，确定最终组合
                self._finalize_combo()
                # 使用 after 在主线程中停止捕获
                self.after(10, self._stop_capture)
    
    def _normalize_key(self, key_name: str) -> Optional[str]:
        """标准化按键名称"""
        if not key_name:
            return None
        
        key_lower = key_name.lower()
        
        # 使用映射表
        if key_lower in self.KEY_NORMALIZE_MAP:
            return self.KEY_NORMALIZE_MAP[key_lower]
        
        # F1-F24
        if key_lower.startswith('f') and key_lower[1:].isdigit():
            return key_name.upper()
        
        # 单字符
        if len(key_name) == 1:
            return key_name.upper()
        
        # 其他按键保留原样但首字母大写
        return key_name.title()
    
    def _update_display(self):
        """更新按键显示"""
        if self.captured_keys:
            modifiers = []
            regular_keys = []
            
            for k in self.captured_keys:
                if k.lower() in ('ctrl', 'alt', 'shift', 'win'):
                    modifiers.append(k)
                else:
                    regular_keys.append(k)
            
            mod_order = {'ctrl': 0, 'alt': 1, 'shift': 2, 'win': 3}
            modifiers.sort(key=lambda x: mod_order.get(x.lower(), 99))
            
            all_keys = modifiers + regular_keys
            display = '+'.join(all_keys) + '...'
            self._set_entry_text(display)
    
    def _finalize_combo(self):
        """确定最终组合键"""
        if not self.captured_keys:
            return
        
        modifiers = []
        regular_keys = []
        
        for k in self.captured_keys:
            if k.lower() in ('ctrl', 'alt', 'shift', 'win'):
                modifiers.append(k)
            else:
                regular_keys.append(k)
        
        # 必须有非修饰键
        if not regular_keys:
            return
        
        mod_order = {'ctrl': 0, 'alt': 1, 'shift': 2, 'win': 3}
        modifiers.sort(key=lambda x: mod_order.get(x.lower(), 99))
        
        all_keys = modifiers + regular_keys
        self.final_combo = '+'.join(all_keys)
        self.has_changes = True
        self._set_entry_text(self.final_combo)
    
    def _on_selection_change(self):
        """选项变更"""
        self.has_changes = True
        self._update_custom_visibility()
    
    def _update_custom_visibility(self):
        """更新自定义区域可见性"""
        pass  # 始终显示自定义区域
    
    def _clear_capture(self):
        """清除捕获的按键"""
        # 如果正在捕获，先停止
        if self.is_capturing:
            self._stop_capture()
        
        self._set_entry_text("")
        self.final_combo = ""
        self.captured_keys.clear()
        self.status_label.configure(text="")
    
    def _on_save(self):
        """保存按钮点击"""
        # 停止捕获并清理钩子
        if self.is_capturing:
            self._stop_capture()
        
        selected = self.key_var.get()
        
        # 检查是否选择自定义
        if selected.startswith("__custom__"):
            custom = self.capture_entry.get().strip().rstrip('.')
            if custom and custom != "等待按键...":
                # 转换为 pynput 格式
                pynput_key = self._to_pynput_format(custom)
                self.on_confirm(pynput_key, "keyboard")
                self._cleanup_and_destroy()
                return
            else:
                messagebox.showwarning("警告", "请录入自定义按键", parent=self)
                return
        
        # 使用选择的预设
        if "|" in selected:
            key, ktype = selected.split("|", 1)
            self.on_confirm(key, ktype)
        self._cleanup_and_destroy()
    
    def _on_cancel(self):
        """取消按钮"""
        self._cleanup_and_destroy()
    
    def _on_close(self):
        """窗口关闭事件"""
        if self.has_changes:
            if messagebox.askyesno("确认", "是否保存更改？", parent=self):
                self._on_save()
            else:
                self._on_cancel()
        else:
            self._on_cancel()
    
    def _cleanup_and_destroy(self):
        """清理钩子并销毁窗口"""
        # 确保停止捕获
        if self.is_capturing:
            self.is_capturing = False
            if self._hook and HAS_KEYBOARD:
                try:
                    keyboard.unhook(self._hook)
                except:
                    pass
                self._hook = None
        self.destroy()
    
    def _to_pynput_format(self, key_combo: str) -> str:
        """转换为 pynput 格式"""
        # 简单转换：小写化，空格变下划线
        return key_combo.lower().replace(' ', '_')


class SceneEditDialog(tk.Toplevel):
    """场景编辑对话框"""
    
    # 触发模式选项
    MODES = [
        ("hold", "长按"),
        ("toggle", "切换"),
    ]
    
    # 处理方式选项 (value, display_text)
    # value 必须与 LLM/*.py 中的 name 字段匹配（角色名）
    # '直出' 表示直接输出（不走 LLM API）
    PROCESSORS = [
        ("直出", "直出"),              # 直接输出 ASR 结果，不调用 LLM
        ("润色", "润色"),              # LLM/润色.py
        ("翻译", "翻译"),              # LLM/翻译.py
    ]
    
    # 常用快捷键（用于显示）
    KEY_DISPLAY_MAP = {
        'caps_lock': 'CapsLock',
        'x1': '鼠标侧键 X1',
        'x2': '鼠标侧键 X2',
        'space': '空格键',
        'f10': 'F10',
        'f11': 'F11',
        'f12': 'F12',
    }
    
    def __init__(self, parent, scene: Dict[str, Any], available_roles: List[str], 
                 on_save: Callable[[Dict[str, Any]], None], is_new: bool = False):
        super().__init__(parent)
        
        self.scene = scene.copy()
        self.available_roles = available_roles
        self.on_save_callback = on_save
        self.is_new = is_new
        self.result = None
        
        # 构建完整的处理方式选项（不再添加自定义角色）
        self.all_processors = list(self.PROCESSORS)
        
        self._setup_window()
        self._create_ui()
        self._load_values()
        
        # 绑定关闭事件
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _setup_window(self):
        """设置窗口属性"""
        title = "新建场景" if self.is_new else f"编辑场景: {self.scene.get('name', '')}"
        self.title(title)
        self.resizable(False, False)
        self.transient(self.master)
        self.grab_set()
    
    def _create_ui(self):
        """创建界面"""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # ===== 标题行 =====
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(0, 12))
        
        # 场景名称
        ttk.Label(header_frame, text="场景").pack(side='left')
        
        # 序号标签
        scene_num = self.scene.get('_index', 1)
        ttk.Label(header_frame, text=f" {scene_num}:", foreground="gray").pack(side='left')
        
        # 名称输入框
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(header_frame, textvariable=self.name_var, width=20)
        name_entry.pack(side='left', padx=(4, 0))
        
        # 启用复选框
        self.enabled_var = tk.BooleanVar(value=True)
        enabled_frame = ttk.Frame(header_frame)
        enabled_frame.pack(side='right')
        ttk.Label(enabled_frame, text="启用").pack(side='left')
        enabled_check = ttk.Checkbutton(enabled_frame, variable=self.enabled_var)
        enabled_check.pack(side='left', padx=(4, 0))
        
        # ===== 分隔线 =====
        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=6)
        
        # ===== 设置区域 - 三列布局 =====
        settings_frame = ttk.Frame(main_frame)
        settings_frame.pack(fill='both', expand=True)
        
        # 使用 grid 布局确保对齐
        settings_frame.columnconfigure(0, weight=0, minsize=100)
        settings_frame.columnconfigure(1, weight=0, minsize=100)
        settings_frame.columnconfigure(2, weight=1, minsize=180)
        
        # --- 第一列: 快捷键 ---
        col1 = ttk.Frame(settings_frame)
        col1.grid(row=0, column=0, sticky='nw', padx=(0, 16))
        
        ttk.Label(col1, text="快捷键", foreground="#1E90FF").pack(anchor='w')
        
        # 显示当前快捷键
        self.key_display_var = tk.StringVar()
        key_label = ttk.Label(col1, textvariable=self.key_display_var)
        key_label.pack(anchor='w', pady=(8, 4))
        
        # 修改按钮
        self.modify_btn = ttk.Button(
            col1, text="[修改]", 
            command=self._show_key_picker, 
            bootstyle="link", 
            padding=0
        )
        self.modify_btn.pack(anchor='w')
        
        # --- 第二列: 触发模式 ---
        col2 = ttk.Frame(settings_frame)
        col2.grid(row=0, column=1, sticky='nw', padx=(0, 16))
        
        ttk.Label(col2, text="触发模式", foreground="#1E90FF").pack(anchor='w')
        
        self.mode_var = tk.StringVar(value="hold")
        mode_container = ttk.Frame(col2)
        mode_container.pack(anchor='w', pady=(8, 0))
        
        for value, text in self.MODES:
            rb = ttk.Radiobutton(mode_container, text=text, variable=self.mode_var, value=value)
            rb.pack(anchor='w', pady=2)
        
        # 启动延时控件（仅长按模式有效）
        threshold_frame = ttk.Frame(col2)
        threshold_frame.pack(anchor='w', pady=(12, 0))
        
        ttk.Label(threshold_frame, text="启动延时", foreground="#666").pack(anchor='w')
        
        # 滑块容器
        slider_container = ttk.Frame(threshold_frame)
        slider_container.pack(anchor='w', pady=(4, 0))
        
        self.threshold_var = tk.DoubleVar(value=0.3)
        self.threshold_scale = ttk.Scale(
            slider_container, 
            from_=0.1, to=1.0, 
            variable=self.threshold_var,
            command=self._on_threshold_change,
            length=100
        )
        self.threshold_scale.pack(side='left')
        
        self.threshold_label = ttk.Label(slider_container, text="0.3 秒", width=6)
        self.threshold_label.pack(side='left', padx=(4, 0))
        
        # --- 第三列: 处理方式 ---
        col3 = ttk.Frame(settings_frame)
        col3.grid(row=0, column=2, sticky='nw')
        
        ttk.Label(col3, text="处理方式", foreground="#1E90FF").pack(anchor='w')
        
        self.processor_var = tk.StringVar(value="none")
        processor_container = ttk.Frame(col3)
        processor_container.pack(anchor='w', pady=(8, 0))
        
        for value, text in self.all_processors:
            rb = ttk.Radiobutton(processor_container, text=text, variable=self.processor_var, value=value)
            rb.pack(anchor='w', pady=2)
        
        # ===== 底部按钮 =====
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', side='bottom', pady=(16, 0))
        
        # 保存按钮
        save_btn = ttk.Button(btn_frame, text="保存", command=self._on_save, 
                              bootstyle="primary", width=10)
        save_btn.pack(side='left')
        
        # 取消按钮
        cancel_btn = ttk.Button(btn_frame, text="取消", command=self._on_cancel, width=10)
        cancel_btn.pack(side='left', padx=(8, 0))
    
    def _load_values(self):
        """加载当前场景值"""
        self.name_var.set(self.scene.get('name', ''))
        self.enabled_var.set(self.scene.get('enabled', True))
        self.mode_var.set(self.scene.get('mode', 'hold'))
        
        # 兼容旧的 processor 值
        processor = self.scene.get('processor', '直出')
        # 旧值映射到新的中文值
        legacy_map = {
            'none': '直出', 'direct': '直出',
            'light': '润色', 'deep': '润色', 'polish': '润色',
            'translate': '翻译'
        }
        processor = legacy_map.get(processor, processor)
        self.processor_var.set(processor)
        
        # 设置快捷键显示
        self._update_key_display()
        
        # 加载 threshold
        threshold = self.scene.get('threshold', 0.3)
        if threshold is None:
            threshold = 0.3
        self.threshold_var.set(threshold)
        self._on_threshold_change(threshold)
    
    def _update_key_display(self):
        """更新快捷键显示"""
        key = self.scene.get('key', 'caps_lock')
        display = self.KEY_DISPLAY_MAP.get(key, key.upper() if len(key) <= 3 else key.title())
        self.key_display_var.set(display)
    
    def _on_threshold_change(self, value):
        """滑块值变化回调"""
        try:
            val = float(value)
            self.threshold_label.configure(text=f"{val:.1f} 秒")
        except (ValueError, AttributeError):
            pass
    
    def _show_key_picker(self):
        """显示快捷键选择对话框"""
        current_key = self.scene.get('key', 'caps_lock')
        current_type = self.scene.get('type', 'keyboard')
        
        def on_key_selected(key: str, key_type: str):
            self.scene['key'] = key
            self.scene['type'] = key_type
            self._update_key_display()
        
        KeyCaptureDialog(self, current_key, current_type, on_key_selected)
    
    def _on_save(self):
        """保存按钮点击"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("警告", "请输入场景名称", parent=self)
            return
        
        self.scene['name'] = name
        self.scene['enabled'] = self.enabled_var.get()
        self.scene['mode'] = self.mode_var.get()
        self.scene['processor'] = self.processor_var.get()
        self.scene['threshold'] = round(self.threshold_var.get(), 2)
        
        # 确保有 key 字段
        if 'key' not in self.scene:
            self.scene['key'] = 'caps_lock'
        if 'type' not in self.scene:
            self.scene['type'] = 'keyboard'
        
        # 移除临时字段
        self.scene.pop('_index', None)
        
        self.result = self.scene
        if self.on_save_callback:
            self.on_save_callback(self.scene)
        self.destroy()
    
    def _on_cancel(self):
        """取消按钮点击"""
        self.result = None
        self.destroy()
    
    def _on_close(self):
        """窗口关闭事件 - 询问是否保存"""
        if messagebox.askyesno("确认", "是否保存更改？", parent=self):
            self._on_save()
        else:
            self._on_cancel()


class ShortcutPanel(ttk.Frame):
    """语音输入场景配置面板"""
    
    # 预设场景模板
    PRESET_SCENES = [
        {
            "name": "直接打字",
            "key": "caps_lock",
            "type": "keyboard",
            "mode": "hold",
            "processor": "light",
            "enabled": True,
        },
        {
            "name": "润色打字",
            "key": "x2",
            "type": "mouse",
            "mode": "hold",
            "processor": "deep",
            "enabled": True,
        },
    ]
    
    # 模式显示映射
    MODES = {"hold": "长按", "toggle": "切换"}
    
    # 处理方式显示映射
    PROCESSORS = {
        "直出": "直出",
        "润色": "润色",
        "翻译": "翻译",
        # 兼容旧值
        "none": "直出",
        "direct": "直出",
        "light": "润色",
        "deep": "润色",
        "polish": "润色",
        "translate": "翻译",
    }
    
    # 快捷键显示映射
    KEY_DISPLAY_MAP = {
        'caps_lock': 'CapsLock',
        'x1': '鼠标 X1',
        'x2': '鼠标 X2',
        'space': 'Space',
        'f10': 'F10',
        'f11': 'F11',
        'f12': 'F12',
    }
    
    def __init__(self, parent, scenes: List[Dict[str, Any]], on_change: Callable = None):
        super().__init__(parent, padding=12)
        self.scenes = scenes if scenes else self._get_default_scenes()
        self.on_change = on_change
        
        # 加载可用角色列表
        self.available_roles = self._load_available_roles()
        
        self._create_ui()
        self._populate_table()
    
    def _get_default_scenes(self) -> List[Dict[str, Any]]:
        """获取默认场景配置"""
        return [scene.copy() for scene in self.PRESET_SCENES]
    
    def _load_available_roles(self) -> List[str]:
        """从 LLM/ 目录加载可用角色"""
        roles = []
        try:
            from config import BASE_DIR
            llm_dir = Path(BASE_DIR) / 'LLM'
            for file_path in sorted(llm_dir.glob('*.py')):
                if file_path.name == '__init__.py':
                    continue
                role_name = file_path.stem
                if role_name != 'default':
                    roles.append(role_name)
        except Exception:
            pass
        return roles
    
    def _get_processor_display(self, processor: str) -> str:
        """获取处理方式的显示文本"""
        if processor in self.PROCESSORS:
            return self.PROCESSORS[processor]
        if processor.startswith("role:"):
            return f"📜 {processor[5:]}"
        return processor
    
    def _format_key_display(self, scene: Dict) -> str:
        """格式化快捷键显示"""
        key = scene.get('key', '')
        display = self.KEY_DISPLAY_MAP.get(key, key.upper() if len(key) <= 3 else key.title())
        return display
    
    def _create_ui(self):
        """创建界面"""
        # 表格区域
        table_frame = ttk.Frame(self)
        table_frame.pack(fill='both', expand=True)
        
        columns = ("name", "key", "mode", "processor", "enabled")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=4,
            selectmode="browse"
        )
        
        # 定义列
        self.tree.heading("name", text="场景名称")
        self.tree.heading("key", text="快捷键")
        self.tree.heading("mode", text="模式")
        self.tree.heading("processor", text="处理方式")
        self.tree.heading("enabled", text="启用")
        
        # 列宽 - 全部居中
        self.tree.column("name", width=100, anchor="center")
        self.tree.column("key", width=80, anchor="center")
        self.tree.column("mode", width=60, anchor="center")
        self.tree.column("processor", width=100, anchor="center")
        self.tree.column("enabled", width=50, anchor="center")
        
        self.tree.pack(fill='both', expand=True)
        
        # 绑定双击编辑
        self.tree.bind("<Double-1>", lambda e: self._on_edit())
        
        # 按钮区域
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', pady=(12, 0))
        
        # 添加按钮
        add_btn = ttk.Button(
            btn_frame,
            text="+ 添加",
            command=self._on_add,
            bootstyle="success-outline",
            width=8
        )
        add_btn.pack(side='left', padx=(0, 8))
        
        # 编辑按钮
        edit_btn = ttk.Button(
            btn_frame,
            text="✏ 编辑",
            command=self._on_edit,
            bootstyle="info-outline",
            width=8
        )
        edit_btn.pack(side='left', padx=(0, 8))
        
        # 删除按钮
        del_btn = ttk.Button(
            btn_frame,
            text="- 删除",
            command=self._on_delete,
            bootstyle="danger-outline",
            width=8
        )
        del_btn.pack(side='left')
        
        # 提示标签
        hint_label = ttk.Label(
            btn_frame,
            text="双击行或点击编辑按钮修改场景",
            foreground="gray"
        )
        hint_label.pack(side='right')
    
    def _populate_table(self):
        """填充表格数据"""
        # 清空
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 添加数据
        for i, scene in enumerate(self.scenes):
            name = scene.get('name', '未命名')
            key_display = self._format_key_display(scene)
            mode = self.MODES.get(scene.get('mode', 'hold'), '长按')
            processor = self._get_processor_display(scene.get('processor', 'none'))
            enabled = "✓" if scene.get('enabled', True) else "○"
            
            self.tree.insert("", "end", iid=str(i), values=(name, key_display, mode, processor, enabled))
    
    def _on_add(self):
        """添加场景"""
        new_scene = {
            "name": f"场景 {len(self.scenes) + 1}",
            "key": "f12",
            "type": "keyboard",
            "mode": "hold",
            "processor": "none",
            "enabled": True,
            "_index": len(self.scenes) + 1,
        }
        
        # 打开编辑对话框
        dialog = SceneEditDialog(
            self.winfo_toplevel(),
            new_scene,
            self.available_roles,
            on_save=self._on_scene_saved,
            is_new=True
        )
        self.wait_window(dialog)
        
        if dialog.result:
            self.scenes.append(dialog.result)
            self._populate_table()
            
            # 选中新行
            new_idx = len(self.scenes) - 1
            self.tree.selection_set(str(new_idx))
            self.tree.see(str(new_idx))
            
            self._notify_change()
    
    def _on_edit(self):
        """编辑选中的场景"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一个场景")
            return
        
        idx = int(selection[0])
        scene = self.scenes[idx].copy()
        scene['_index'] = idx + 1
        
        # 打开编辑对话框
        dialog = SceneEditDialog(
            self.winfo_toplevel(),
            scene,
            self.available_roles,
            on_save=lambda s: self._on_scene_updated(idx, s),
            is_new=False
        )
        self.wait_window(dialog)
    
    def _on_scene_saved(self, scene: Dict[str, Any]):
        """新场景保存回调（由对话框调用 - 用于添加）"""
        pass  # 实际保存在 _on_add 中处理
    
    def _on_scene_updated(self, idx: int, scene: Dict[str, Any]):
        """场景更新回调"""
        self.scenes[idx] = scene
        self._populate_table()
        self.tree.selection_set(str(idx))
        self._notify_change()
    
    def _on_delete(self):
        """删除选中的场景"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一个场景")
            return
        
        idx = int(selection[0])
        if len(self.scenes) <= 1:
            messagebox.showwarning("警告", "至少需要保留一个场景")
            return
        
        scene_name = self.scenes[idx].get('name', '未命名')
        if messagebox.askyesno("确认删除", f"确定要删除场景 '{scene_name}' 吗？"):
            del self.scenes[idx]
            self._populate_table()
            self._notify_change()
    
    def _notify_change(self):
        """通知配置变更"""
        if self.on_change:
            self.on_change()
    
    def get_config(self) -> List[Dict[str, Any]]:
        """获取当前配置"""
        return self.scenes
