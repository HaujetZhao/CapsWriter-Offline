# coding: utf-8
"""
通用设置面板 - 开机启动、自动服务、托盘最小化
"""

import tkinter as tk
from tkinter import ttk
import sys
import os
from typing import Callable, Dict, Any, Optional

# Windows 注册表支持
if sys.platform == 'win32':
    import winreg


class GeneralPanel(ttk.Frame):
    """通用设置面板"""
    
    # Windows 启动项注册表键
    STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "CapsWriter-Offline"
    
    def __init__(
        self,
        parent,
        config: Dict[str, Any],
        on_change: Callable[[], None]
    ):
        """
        初始化通用设置面板
        
        Args:
            parent: 父容器
            config: 配置字典 (general 部分)
            on_change: 配置变更回调
        """
        super().__init__(parent, padding=12)
        
        self.config = config
        self.on_change = on_change
        
        # 变量
        self.auto_start_var = tk.BooleanVar(value=self._is_auto_start_enabled())
        self.auto_start_service_var = tk.BooleanVar(value=config.get('auto_start_service', False))
        self.minimize_to_tray_var = tk.BooleanVar(value=config.get('minimize_to_tray', True))
        
        self._create_ui()
    
    def _create_ui(self):
        """构建 UI"""
        # ===== 开机启动 =====
        auto_start_frame = ttk.Frame(self)
        auto_start_frame.pack(fill=tk.X, pady=(0, 8))
        
        auto_start_check = ttk.Checkbutton(
            auto_start_frame,
            text="🚀 开机自动启动",
            variable=self.auto_start_var,
            command=self._on_auto_start_change
        )
        auto_start_check.pack(side=tk.LEFT)
        
        auto_start_tip = ttk.Label(
            auto_start_frame,
            text="(添加到 Windows 启动项)",
            foreground="gray"
        )
        auto_start_tip.pack(side=tk.LEFT, padx=(8, 0))
        
        # ===== 自动开始服务 =====
        auto_service_frame = ttk.Frame(self)
        auto_service_frame.pack(fill=tk.X, pady=(0, 8))
        
        auto_service_check = ttk.Checkbutton(
            auto_service_frame,
            text="⚡ 启动后自动开始服务",
            variable=self.auto_start_service_var,
            command=self._on_config_change
        )
        auto_service_check.pack(side=tk.LEFT)
        
        auto_service_tip = ttk.Label(
            auto_service_frame,
            text="(打开程序时自动启动语音服务)",
            foreground="gray"
        )
        auto_service_tip.pack(side=tk.LEFT, padx=(8, 0))
        
        # ===== 关闭时最小化到托盘 =====
        tray_frame = ttk.Frame(self)
        tray_frame.pack(fill=tk.X, pady=(0, 0))
        
        tray_check = ttk.Checkbutton(
            tray_frame,
            text="🔽 关闭时最小化到系统托盘",
            variable=self.minimize_to_tray_var,
            command=self._on_config_change
        )
        tray_check.pack(side=tk.LEFT)
        
        tray_tip = ttk.Label(
            tray_frame,
            text="(点击关闭按钮隐藏窗口，不退出程序)",
            foreground="gray"
        )
        tray_tip.pack(side=tk.LEFT, padx=(8, 0))
    
    def _is_auto_start_enabled(self) -> bool:
        """检查是否已添加到开机启动"""
        if sys.platform != 'win32':
            return False
        
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.STARTUP_KEY, 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, self.APP_NAME)
                return True
        except FileNotFoundError:
            return False
        except Exception:
            return False
    
    def _set_auto_start(self, enable: bool) -> bool:
        """设置开机启动"""
        if sys.platform != 'win32':
            return False
        
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.STARTUP_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    # 获取当前程序路径
                    # 优先使用 pythonw.exe 以隐藏控制台窗口
                    python_exe = sys.executable
                    if python_exe.endswith('python.exe'):
                        pythonw_exe = python_exe.replace('python.exe', 'pythonw.exe')
                        if os.path.exists(pythonw_exe):
                            python_exe = pythonw_exe
                    
                    # 获取项目根目录
                    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    
                    # 构建启动命令 - 直接使用 pythonw 运行 .pyw 文件（无命令行窗口）
                    # 使用 Start-Process 的 -WorkingDirectory 或者直接指定完整路径
                    pyw_file = os.path.join(base_dir, "CapsWriter-GUI.pyw")
                    if os.path.exists(pyw_file):
                        # 使用 .pyw 文件启动（完全无窗口）
                        startup_cmd = f'"{python_exe}" "{pyw_file}"'
                    else:
                        # 回退：使用 wscript 隐藏 cmd 窗口
                        startup_cmd = f'wscript //B //E:vbscript /c:"CreateObject(\\"Wscript.Shell\\").Run \\"\\"\\"{python_exe}\\"\\\" -m gui.main_window\\", 0"'
                    
                    # 注意：需要在注册表中设置工作目录，使用 VBS 启动
                    # 创建一个隐藏窗口的 VBS 启动脚本
                    vbs_path = os.path.join(base_dir, "startup_hidden.vbs")
                    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{base_dir}"
WshShell.Run """{python_exe}"" -m gui.main_window", 0, False
'''
                    with open(vbs_path, 'w', encoding='utf-8') as f:
                        f.write(vbs_content)
                    
                    startup_cmd = f'wscript.exe "{vbs_path}"'
                    
                    winreg.SetValueEx(key, self.APP_NAME, 0, winreg.REG_SZ, startup_cmd)
                else:
                    try:
                        winreg.DeleteValue(key, self.APP_NAME)
                    except FileNotFoundError:
                        pass  # 本来就不存在
            return True
        except Exception as e:
            print(f"设置开机启动失败: {e}")
            return False
    
    def _on_auto_start_change(self):
        """开机启动选项变更"""
        enable = self.auto_start_var.get()
        success = self._set_auto_start(enable)
        
        if not success:
            # 回滚 UI 状态
            self.auto_start_var.set(not enable)
        
        self.on_change()
    
    def _on_config_change(self):
        """配置变更处理"""
        self.config['auto_start_service'] = self.auto_start_service_var.get()
        self.config['minimize_to_tray'] = self.minimize_to_tray_var.get()
        self.on_change()
    
    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            'auto_start_service': self.auto_start_service_var.get(),
            'minimize_to_tray': self.minimize_to_tray_var.get()
        }
