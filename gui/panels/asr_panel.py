"""
ASR 模型配置面板
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Any


class ASRPanel(ttk.Frame):
    """ASR 模型配置面板"""
    
    # 模型选项
    MODELS = {
        "fun_asr_nano": {
            "name": "Fun-ASR-Nano",
            "description": "推荐，速度与精度平衡"
        },
        "sense_voice": {
            "name": "SenseVoice",
            "description": "快速，适合实时转写"
        },
        "paraformer": {
            "name": "Paraformer",
            "description": "高精度，适合离线转写"
        }
    }
    
    def __init__(self, parent, config: Dict[str, Any], on_change: Callable = None):
        """
        初始化 ASR 配置面板
        
        Args:
            parent: 父容器
            config: ASR 配置字典
            on_change: 配置变更回调
        """
        super().__init__(parent, padding=12)
        self.config = config
        self.on_change = on_change
        
        # 变量
        self.model_var = tk.StringVar(value=config.get('model_type', 'fun_asr_nano'))
        self.vulkan_var = tk.BooleanVar(value=config.get('vulkan_enable', False))
        self.fp32_var = tk.BooleanVar(value=config.get('vulkan_force_fp32', False))
        
        self._create_ui()
    
    def _create_ui(self):
        """创建界面"""
        # 模型选择区域
        model_frame = ttk.Frame(self)
        model_frame.pack(fill='x', pady=(0, 12))
        
        # 模型单选按钮
        for model_id, model_info in self.MODELS.items():
            radio_frame = ttk.Frame(model_frame)
            radio_frame.pack(fill='x', pady=2)
            
            radio = ttk.Radiobutton(
                radio_frame,
                text=model_info['name'],
                variable=self.model_var,
                value=model_id,
                command=self._on_model_change
            )
            radio.pack(side='left')
            
            desc_label = ttk.Label(
                radio_frame,
                text=f"({model_info['description']})",
                foreground='gray'
            )
            desc_label.pack(side='left', padx=(8, 0))
        
        # 分隔线
        separator = ttk.Separator(self, orient='horizontal')
        separator.pack(fill='x', pady=12)
        
        # 加速选项区域
        accel_frame = ttk.Frame(self)
        accel_frame.pack(fill='x')
        
        # Vulkan 加速复选框
        self.vulkan_check = ttk.Checkbutton(
            accel_frame,
            text="启用 Vulkan 加速",
            variable=self.vulkan_var,
            command=self._on_vulkan_change
        )
        self.vulkan_check.pack(side='left')
        
        # 强制 FP32 复选框
        self.fp32_check = ttk.Checkbutton(
            accel_frame,
            text="强制 FP32 精度",
            variable=self.fp32_var,
            command=self._on_fp32_change
        )
        self.fp32_check.pack(side='left', padx=(16, 0))
        
        # 根据 Vulkan 状态更新 FP32 可用性
        self._update_fp32_state()
    
    def _on_model_change(self):
        """模型选择变更"""
        self.config['model_type'] = self.model_var.get()
        if self.on_change:
            self.on_change()
    
    def _on_vulkan_change(self):
        """Vulkan 加速选项变更"""
        self.config['vulkan_enable'] = self.vulkan_var.get()
        self._update_fp32_state()
        if self.on_change:
            self.on_change()
    
    def _on_fp32_change(self):
        """FP32 精度选项变更"""
        self.config['vulkan_force_fp32'] = self.fp32_var.get()
        if self.on_change:
            self.on_change()
    
    def _update_fp32_state(self):
        """更新 FP32 复选框状态（仅在 Vulkan 启用时可用）"""
        if self.vulkan_var.get():
            self.fp32_check.configure(state='normal')
        else:
            self.fp32_var.set(False)
            self.config['vulkan_force_fp32'] = False
            self.fp32_check.configure(state='disabled')
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            'model_type': self.model_var.get(),
            'vulkan_enable': self.vulkan_var.get(),
            'vulkan_force_fp32': self.fp32_var.get()
        }
