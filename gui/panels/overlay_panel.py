"""
悬浮窗配置面板
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Any


class OverlayPanel(ttk.Frame):
    """悬浮窗配置面板"""
    
    # 位置选项：只保留底部三个
    POSITIONS = [
        ("bottom_left", "左下角"),
        ("bottom_center", "屏幕中下"),
        ("bottom_right", "右下角")
    ]
    
    def __init__(self, parent, config: Dict[str, Any], on_change: Callable = None):
        """
        初始化悬浮窗配置面板
        
        Args:
            parent: 父容器
            config: 悬浮窗配置字典
            on_change: 配置变更回调
        """
        super().__init__(parent, padding=12)
        self.config = config
        self.on_change = on_change
        
        # 变量
        self.enabled_var = tk.BooleanVar(value=config.get('enabled', True))
        self.position_var = tk.StringVar(value=config.get('position', 'bottom_center'))
        self.opacity_var = tk.DoubleVar(value=config.get('opacity', 0.85))
        self.auto_hide_var = tk.DoubleVar(value=config.get('auto_hide_delay', 1.5))
        
        self._create_ui()
        self._update_enabled_state()
    
    def _create_ui(self):
        """创建界面"""
        # 启用开关
        enable_frame = ttk.Frame(self)
        enable_frame.pack(fill='x', pady=(0, 12))
        
        self.enable_check = ttk.Checkbutton(
            enable_frame,
            text="启用状态悬浮窗",
            variable=self.enabled_var,
            command=self._on_enable_change,
            bootstyle="round-toggle"
        )
        self.enable_check.pack(side='left')
        
        ttk.Label(
            enable_frame,
            text="(录音/识别时显示实时状态)",
            foreground="gray"
        ).pack(side='left', padx=(8, 0))
        
        # 配置区域容器
        self.config_frame = ttk.Frame(self)
        self.config_frame.pack(fill='x')
        
        # 显示位置
        pos_frame = ttk.Frame(self.config_frame)
        pos_frame.pack(fill='x', pady=(0, 8))
        
        ttk.Label(pos_frame, text="显示位置：", width=10).pack(side='left')
        
        position_combo = ttk.Combobox(
            pos_frame,
            values=[p[1] for p in self.POSITIONS],
            state="readonly",
            width=15
        )
        position_combo.pack(side='left', padx=(8, 0))
        
        # 设置显示值
        current_key = self.config.get('position', 'bottom_center')
        for key, label in self.POSITIONS:
            if key == current_key:
                position_combo.set(label)
                break
        
        position_combo.bind("<<ComboboxSelected>>", self._on_position_change)
        self.position_combo = position_combo
        
        # 透明度
        opacity_frame = ttk.Frame(self.config_frame)
        opacity_frame.pack(fill='x', pady=(0, 8))
        
        ttk.Label(opacity_frame, text="透明度：", width=10).pack(side='left')
        
        opacity_scale = ttk.Scale(
            opacity_frame,
            from_=0.3,
            to=1.0,
            variable=self.opacity_var,
            command=self._on_opacity_change,
            length=150
        )
        opacity_scale.pack(side='left', padx=(8, 0))
        
        self.opacity_label = ttk.Label(
            opacity_frame,
            text=f"{int(self.opacity_var.get() * 100)}%",
            width=5
        )
        self.opacity_label.pack(side='left', padx=(8, 0))
        
        # 自动隐藏延迟
        hide_frame = ttk.Frame(self.config_frame)
        hide_frame.pack(fill='x')
        
        ttk.Label(hide_frame, text="自动隐藏：", width=10).pack(side='left')
        
        hide_spin = ttk.Spinbox(
            hide_frame,
            from_=0.5,
            to=10.0,
            increment=0.5,
            textvariable=self.auto_hide_var,
            width=6,
            command=self._on_config_change
        )
        hide_spin.pack(side='left', padx=(8, 0))
        hide_spin.bind("<KeyRelease>", lambda e: self._on_config_change())
        
        ttk.Label(
            hide_frame,
            text="秒 (识别完成后自动隐藏)",
            foreground="gray"
        ).pack(side='left', padx=(8, 0))
        

    
    def _on_enable_change(self):
        """启用开关变更"""
        self._update_enabled_state()
        self._on_config_change()
    
    def _update_enabled_state(self):
        """更新启用状态"""
        enabled = self.enabled_var.get()
        state = 'normal' if enabled else 'disabled'
        
        for child in self.config_frame.winfo_children():
            self._set_widget_state(child, state)
    
    def _set_widget_state(self, widget, state):
        """递归设置组件状态"""
        try:
            widget.configure(state=state)
        except:
            pass
        
        for child in widget.winfo_children():
            self._set_widget_state(child, state)
    
    def _on_position_change(self, event=None):
        """位置变更"""
        # 转换显示值为键值
        selected_label = self.position_combo.get()
        for key, label in self.POSITIONS:
            if label == selected_label:
                self.position_var.set(key)
                break
        
        self._on_config_change()
    
    def _on_opacity_change(self, value=None):
        """透明度变更"""
        opacity = self.opacity_var.get()
        self.opacity_label.configure(text=f"{int(opacity * 100)}%")
        self._on_config_change()
    
    def _on_config_change(self):
        """配置变更"""
        self.config['enabled'] = self.enabled_var.get()
        self.config['position'] = self.position_var.get()
        self.config['opacity'] = round(self.opacity_var.get(), 2)
        self.config['auto_hide_delay'] = self.auto_hide_var.get()
        
        if self.on_change:
            self.on_change()
    
    def _preview_overlay(self):
        """预览悬浮窗效果"""
        try:
            from gui.status_overlay import StatusOverlay
            
            # 创建预览窗口
            preview = StatusOverlay(
                position=self.position_var.get(),
                opacity=self.opacity_var.get(),
                auto_hide_delay=self.auto_hide_var.get()
            )
            
            # 依次显示各状态
            def show_recording():
                preview.show('recording', '预览模式')
            
            def show_processing():
                preview.show('processing')
            
            def show_done():
                preview.show('done')
            
            # 时序展示
            self.after(0, show_recording)
            self.after(2000, show_processing)
            self.after(3500, show_done)
            
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("预览失败", str(e))
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            'enabled': self.enabled_var.get(),
            'position': self.position_var.get(),
            'opacity': round(self.opacity_var.get(), 2),
            'auto_hide_delay': self.auto_hide_var.get()
        }
