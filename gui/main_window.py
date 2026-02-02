"""
CapsWriter-Offline 配置工具 - 主窗口
"""

import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *

from gui.config_manager import ConfigManager
from gui.panels.asr_panel import ASRPanel


class MainWindow(ttkb.Window):
    """主窗口类"""
    
    # 主题映射
    THEMES = {
        "light": "litera",
        "dark": "darkly"
    }
    
    def __init__(self):
        # 加载配置
        self.config = ConfigManager.load()
        self.current_theme = self.config.get('theme', 'light')
        
        # 初始化窗口
        theme_name = self.THEMES.get(self.current_theme, 'litera')
        super().__init__(themename=theme_name)
        
        # 窗口设置
        self.title("CapsWriter-Offline 配置工具")
        self.geometry("720x860")
        self.minsize(640, 700)
        
        # 尝试设置图标
        try:
            self.iconbitmap("assets/icon.ico")
        except:
            pass  # 图标不存在时忽略
        
        # 创建 UI
        self._create_ui()
    
    def _create_ui(self):
        """创建主界面布局"""
        # 主容器
        main_container = ttk.Frame(self, padding=16)
        main_container.pack(fill=BOTH, expand=True)
        
        # 标题栏区域（包含主题切换按钮）
        self._create_title_bar(main_container)
        
        # ASR 模型设置区域
        self.asr_frame = ttk.LabelFrame(main_container, text="🎙 ASR 模型设置", padding=0)
        self.asr_frame.pack(fill=X, pady=8)
        self.asr_panel = ASRPanel(
            self.asr_frame,
            self.config.get('asr', {}),
            on_change=self._on_config_change
        )
        self.asr_panel.pack(fill=X)
        
        # 快捷键设置区域
        self.shortcut_frame = self._create_section(
            main_container, "⌨ 快捷键设置", "快捷键配置面板占位"
        )
        
        # LLM 设置区域
        self.llm_frame = self._create_section(
            main_container, "🤖 LLM 设置", "LLM 配置面板占位"
        )
        
        # 状态悬浮窗设置区域
        self.overlay_frame = self._create_section(
            main_container, "📊 状态悬浮窗", "悬浮窗配置面板占位"
        )
        
        # 底部操作区
        self._create_bottom_actions(main_container)
    
    def _create_title_bar(self, parent):
        """创建标题栏区域（包含主题切换按钮）"""
        title_frame = ttk.Frame(parent)
        title_frame.pack(fill=X, pady=(0, 16))
        
        # 标题
        title_label = ttk.Label(
            title_frame,
            text="CapsWriter-Offline 配置工具",
            font=("Microsoft YaHei UI", 16, "bold")
        )
        title_label.pack(side=LEFT)
        
        # 主题切换按钮
        self.theme_btn = ttk.Button(
            title_frame,
            text="☀️" if self.current_theme == "light" else "🌙",
            width=3,
            command=self._toggle_theme,
            bootstyle="secondary-outline"
        )
        self.theme_btn.pack(side=RIGHT)
    
    def _create_section(self, parent, title: str, placeholder: str) -> ttk.LabelFrame:
        """创建配置区域框架"""
        frame = ttk.LabelFrame(parent, text=title, padding=12)
        frame.pack(fill=X, pady=8)
        
        # 占位标签
        placeholder_label = ttk.Label(frame, text=placeholder, foreground="gray")
        placeholder_label.pack(pady=20)
        
        return frame
    
    def _create_bottom_actions(self, parent):
        """创建底部操作按钮区"""
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=X, pady=(16, 0))
        
        # 保存按钮
        self.save_btn = ttk.Button(
            action_frame,
            text="💾 保存配置",
            command=self._on_save,
            bootstyle="primary",
            width=15
        )
        self.save_btn.pack(side=LEFT, padx=(0, 8))
        
        # 启动服务按钮
        self.start_btn = ttk.Button(
            action_frame,
            text="🚀 启动服务",
            command=self._on_start,
            bootstyle="success",
            width=15
        )
        self.start_btn.pack(side=LEFT)
        
        # 状态标签
        self.status_label = ttk.Label(
            action_frame,
            text="就绪",
            foreground="gray"
        )
        self.status_label.pack(side=RIGHT)
    
    def _toggle_theme(self):
        """切换主题"""
        # 切换主题
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        new_theme = self.THEMES.get(self.current_theme, 'litera')
        
        # 应用主题
        self.style.theme_use(new_theme)
        
        # 更新按钮图标
        self.theme_btn.configure(text="☀️" if self.current_theme == "light" else "🌙")
        
        # 保存主题偏好
        self.config['theme'] = self.current_theme
        ConfigManager.save(self.config)
    
    def _on_config_change(self):
        """配置变更回调"""
        # 更新 ASR 配置
        self.config['asr'] = self.asr_panel.get_config()
        self.status_label.configure(text="配置已修改（未保存）", foreground="orange")
    
    def _on_save(self):
        """保存配置按钮点击事件"""
        try:
            # 收集所有面板配置
            self.config['asr'] = self.asr_panel.get_config()
            ConfigManager.save(self.config)
            self.status_label.configure(text="✅ 配置已保存", foreground="green")
        except Exception as e:
            self.status_label.configure(text=f"❌ 保存失败: {e}", foreground="red")
    
    def _on_start(self):
        """启动服务按钮点击事件（占位）"""
        self.status_label.configure(text="🚀 启动功能待实现", foreground="orange")


def main():
    """主函数"""
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
