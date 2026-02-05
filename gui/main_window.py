"""
CapsWriter-Offline 配置工具 - 主窗口
"""

import tkinter as tk
from tkinter import ttk, messagebox
import ctypes
import sys
import os
import subprocess
import signal
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *

from gui.config_manager import ConfigManager
from gui.panels.asr_panel import ASRPanel
from gui.panels.shortcut_panel import ShortcutPanel
from gui.panels.llm_panel import LLMPanel
from gui.panels.overlay_panel import OverlayPanel
from gui.panels.general_panel import GeneralPanel


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
        
        # 服务进程句柄
        self.server_process = None
        self.client_process = None
        self.is_running = False
        
        # 托盘相关
        self._tray_icon = None
        self._tray_thread = None
        
        # 初始化窗口
        theme_name = self.THEMES.get(self.current_theme, 'litera')
        super().__init__(themename=theme_name)
        
        # 窗口设置
        self.title("CapsWriter-Offline 配置工具")
        self.minsize(640, 600)  # 最小尺寸，内容自适应
        
        # 设置窗口图标（同时使用 iconbitmap 和 wm_iconphoto 确保任务栏图标正确显示）
        self._set_window_icon()
        
        # 创建 UI
        self._create_ui()
        
        # 应用标题栏主题（Windows 暮色模式 API）
        self.after(100, self._apply_titlebar_theme)
        
        # 窗口关闭时处理
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # 自动启动服务
        general_config = self.config.get('general', {})
        if general_config.get('auto_start_service', False):
            self.after(500, self._start_services)  # 延迟500ms启动，确保UI完成渲染
        
        # 启动时立即创建托盘图标（延迟执行以确保窗口渲染完成）
        self.after(200, self._ensure_tray_icon)
    
    def _create_ui(self):
        """创建主界面布局 - 双列布局"""
        # 主容器
        main_container = ttk.Frame(self, padding=16)
        main_container.pack(fill=BOTH, expand=True)
        
        # 标题栏区域（包含主题切换按钮）
        self._create_title_bar(main_container)
        
        # 双列容器
        columns_frame = ttk.Frame(main_container)
        columns_frame.pack(fill=BOTH, expand=True, pady=8)
        
        # 左侧列：ASR + LLM 设置
        left_column = ttk.Frame(columns_frame)
        left_column.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 8))
        
        # ASR 模型设置区域
        self.asr_frame = ttk.LabelFrame(left_column, text="🎙 ASR 模型设置", padding=0)
        self.asr_frame.pack(fill=X, pady=(0, 8))
        self.asr_panel = ASRPanel(
            self.asr_frame,
            self.config.get('asr', {}),
            on_change=self._on_config_change
        )
        self.asr_panel.pack(fill=X)
        
        # LLM 设置区域
        self.llm_frame = ttk.LabelFrame(left_column, text="🤖 LLM 设置", padding=0)
        self.llm_frame.pack(fill=BOTH, expand=True, pady=(0, 8))
        self.llm_panel = LLMPanel(
            self.llm_frame,
            self.config.get('llm', {}),
            on_change=self._on_config_change
        )
        self.llm_panel.pack(fill=BOTH, expand=True)
        
        # 右侧列：场景 + 悬浮窗 + 通用设置
        right_column = ttk.Frame(columns_frame)
        right_column.pack(side=RIGHT, fill=BOTH, expand=True, padx=(8, 0))
        
        # 语音输入场景设置区域
        self.shortcut_frame = ttk.LabelFrame(right_column, text="⌨ 语音输入场景", padding=0)
        self.shortcut_frame.pack(fill=X, pady=(0, 8))
        self.shortcut_panel = ShortcutPanel(
            self.shortcut_frame,
            self.config.get('scenes', []),
            on_change=self._on_config_change
        )
        self.shortcut_panel.pack(fill=X)
        
        # 状态悬浮窗设置区域
        self.overlay_frame = ttk.LabelFrame(right_column, text="📊 状态悬浮窗", padding=0)
        self.overlay_frame.pack(fill=X, pady=(0, 8))
        self.overlay_panel = OverlayPanel(
            self.overlay_frame,
            self.config.get('overlay', {}),
            on_change=self._on_config_change
        )
        self.overlay_panel.pack(fill=X)
        
        # 通用设置区域
        self.general_frame = ttk.LabelFrame(right_column, text="⚙ 通用设置", padding=0)
        self.general_frame.pack(fill=X, pady=(0, 8))
        self.general_panel = GeneralPanel(
            self.general_frame,
            self.config.get('general', {}),
            on_change=self._on_config_change
        )
        self.general_panel.pack(fill=X)
        
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
        
        # 主题切换开关（胶囊样式）
        toggle_frame = ttk.Frame(title_frame)
        toggle_frame.pack(side=RIGHT)
        
        # 创建胶囊形状的 Canvas（双椭圆选择器）
        self.toggle_canvas = tk.Canvas(
            toggle_frame, 
            width=88, height=40, 
            highlightthickness=0,
            cursor="hand2"
        )
        self.toggle_canvas.pack()
        
        # 绑定点击事件
        self.toggle_canvas.bind("<Button-1>", lambda e: self._toggle_theme())
        
        # 绘制初始状态
        self._draw_toggle()
    
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
        self.start_btn.pack(side=LEFT, padx=(0, 8))
        
        # 退出按钮
        self.exit_btn = ttk.Button(
            action_frame,
            text="🚪 退出",
            command=self._on_exit,
            bootstyle="secondary-outline",
            width=10
        )
        self.exit_btn.pack(side=LEFT)
        
        # 状态栏容器（右侧）
        status_frame = ttk.Frame(action_frame)
        status_frame.pack(side=RIGHT)
        
        # 服务器状态标签
        self.service_status = ttk.Label(
            status_frame,
            text="⏹ 服务未启动",
            foreground="gray"
        )
        self.service_status.pack(side=RIGHT, padx=(8, 0))
        
        # 配置状态标签
        self.config_status = ttk.Label(
            status_frame,
            text="",
            foreground="gray"
        )
        self.config_status.pack(side=RIGHT)
    
    def _apply_titlebar_theme(self):
        """应用 Windows 标题栏暗色/亮色模式"""
        if sys.platform != 'win32':
            return
        
        try:
            # 获取窗口句柄
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            
            # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 10 20H1+)
            # 值为 1 表示暗色，0 表示亮色
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            dark_mode = ctypes.c_int(1 if self.current_theme == "dark" else 0)
            
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(dark_mode),
                ctypes.sizeof(dark_mode)
            )
        except Exception:
            # 在不支持的 Windows 版本上静默失败
            pass
    
    def _draw_toggle(self):
        """绘制双椭圆主题开关：激活侧蓝色背景+白色图标，未激活侧无背景+黑色图标"""
        canvas = self.toggle_canvas
        canvas.delete("all")
        
        w, h = 88, 40
        pad = 4
        oval_w, oval_h = 38, 32
        r = h // 2  # 圆角半径
        
        # 绘制完整的胶囊背景（用两个半圆+矩形）
        canvas.create_arc(0, 0, h, h, start=90, extent=180, fill="#E8E8E8", outline="")
        canvas.create_arc(w - h, 0, w, h, start=-90, extent=180, fill="#E8E8E8", outline="")
        canvas.create_rectangle(r, 0, w - r, h, fill="#E8E8E8", outline="")
        
        # 左侧椭圆位置
        left_x1, left_y1 = pad, pad
        left_x2, left_y2 = pad + oval_w, pad + oval_h
        left_cx = (left_x1 + left_x2) // 2
        left_cy = (left_y1 + left_y2) // 2
        
        # 右侧椭圆位置
        right_x1, right_y1 = w - pad - oval_w, pad
        right_x2, right_y2 = w - pad, pad + oval_h
        right_cx = (right_x1 + right_x2) // 2
        right_cy = (right_y1 + right_y2) // 2
        
        # 使用纯色 Unicode 符号，较小字体
        light_icon = "☀"  # 纯色太阳
        icon_font = ("Segoe UI Symbol", 10)
        
        def draw_crescent(cx, cy, color):
            """绘制实心月牙"""
            r = 6  # 月牙半径
            # 外圆
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="")
            # 内圆（偏移形成月牙效果）- 使用背景色覆盖
            bg = "#2196F3" if (self.current_theme == "dark") else "#E8E8E8"
            canvas.create_oval(cx - r + 4, cy - r - 1, cx + r + 4, cy + r - 1, fill=bg, outline="")
        
        if self.current_theme == "light":
            # 亮色模式：左侧激活（蓝色+白色图标），右侧未激活（黑色图标）
            canvas.create_oval(left_x1, left_y1, left_x2, left_y2, fill="#2196F3", outline="")
            canvas.create_text(left_cx, left_cy, text=light_icon, font=icon_font, fill="white")
            draw_crescent(right_cx, right_cy, "#555555")
        else:
            # 暗色模式：左侧未激活（黑色图标），右侧激活（蓝色+白色图标）
            canvas.create_text(left_cx, left_cy, text=light_icon, font=icon_font, fill="#555555")
            canvas.create_oval(right_x1, right_y1, right_x2, right_y2, fill="#2196F3", outline="")
            draw_crescent(right_cx, right_cy, "white")
    
    def _toggle_theme(self):
        """切换主题"""
        # 切换主题状态
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        new_theme = self.THEMES.get(self.current_theme, 'litera')
        
        # 应用主题
        self.style.theme_use(new_theme)
        
        # 重绘开关
        self._draw_toggle()
        
        # 应用标题栏主题
        self._apply_titlebar_theme()
        
        # 保存主题偏好
        self.config['theme'] = self.current_theme
        ConfigManager.save(self.config)
    
    def _on_config_change(self):
        """配置变更回调"""
        # 更新所有面板配置
        self.config['asr'] = self.asr_panel.get_config()
        self.config['scenes'] = self.shortcut_panel.get_config()
        self.config['llm'] = self.llm_panel.get_config()
        self.config['overlay'] = self.overlay_panel.get_config()
        self.config['general'] = self.general_panel.get_config()
        self.config_status.configure(text="⚠ 配置已修改", foreground="orange")
    
    def _on_save(self):
        """保存配置按钮点击事件"""
        try:
            # 收集所有面板配置
            self.config['asr'] = self.asr_panel.get_config()
            self.config['scenes'] = self.shortcut_panel.get_config()
            self.config['llm'] = self.llm_panel.get_config()
            self.config['overlay'] = self.overlay_panel.get_config()
            self.config['general'] = self.general_panel.get_config()
            ConfigManager.save(self.config)
            self.config_status.configure(text="✅ 配置已保存", foreground="green")
        except Exception as e:
            self.config_status.configure(text=f"❌ 保存失败: {e}", foreground="red")
    
    def _on_start(self):
        """启动/停止服务按钮点击事件"""
        if self.is_running:
            self._stop_services()
        else:
            self._start_services()
    
    def _find_system_python(self) -> str:
        """查找系统 Python 解释器（用于 EXE 模式下启动子进程）"""
        import shutil
        
        # 1. 首先尝试 shutil.which
        python_exe = shutil.which('pythonw') or shutil.which('python')
        if python_exe:
            # 确保不是 EXE 自己
            exe_path = os.path.abspath(sys.executable).lower()
            if os.path.abspath(python_exe).lower() != exe_path:
                return python_exe
        
        # 2. 检查常见安装路径
        common_paths = [
            # 用户安装
            os.path.expandvars(r'%LOCALAPPDATA%\Programs\Python'),
            # 系统安装
            r'C:\Python313', r'C:\Python312', r'C:\Python311', r'C:\Python310',
            r'C:\Program Files\Python313', r'C:\Program Files\Python312',
        ]
        
        for base_path in common_paths:
            if os.path.isdir(base_path):
                # 检查目录下是否有 pythonw.exe
                for item in os.listdir(base_path):
                    item_path = os.path.join(base_path, item)
                    if os.path.isdir(item_path):
                        pythonw = os.path.join(item_path, 'pythonw.exe')
                        if os.path.exists(pythonw):
                            return pythonw
                # 直接在目录下检查
                pythonw = os.path.join(base_path, 'pythonw.exe')
                if os.path.exists(pythonw):
                    return pythonw
        
        # 3. 尝试从注册表读取
        if sys.platform == 'win32':
            try:
                import winreg
                # 检查 Python 安装路径
                for version in ['3.13', '3.12', '3.11', '3.10']:
                    try:
                        key = winreg.OpenKey(
                            winreg.HKEY_CURRENT_USER,
                            rf'Software\Python\PythonCore\{version}\InstallPath'
                        )
                        install_path, _ = winreg.QueryValueEx(key, '')
                        winreg.CloseKey(key)
                        pythonw = os.path.join(install_path, 'pythonw.exe')
                        if os.path.exists(pythonw):
                            return pythonw
                    except FileNotFoundError:
                        continue
            except Exception:
                pass
        
        return None
    
    def _start_services(self):
        """启动服务端和客户端进程"""
        try:
            print("[DEBUG] _start_services called")
            
            # 先保存配置
            self._on_save()
            print("[DEBUG] Config saved")
            
            # 获取项目根目录
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 检测是否从 EXE 运行（frozen 模式）
            if getattr(sys, 'frozen', False):
                # 从 EXE 启动时，使用系统 Python（避免循环启动 EXE 自己）
                python_exe = self._find_system_python()
                if not python_exe:
                    raise RuntimeError("无法找到系统 Python 解释器，请确保 Python 已安装")
            else:
                python_exe = sys.executable
            
            print(f"[DEBUG] base_dir={base_dir}, python_exe={python_exe}")
            
            # 启动服务端（隐藏控制台窗口）
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            # 设置环境变量禁用子进程托盘图标
            env = os.environ.copy()
            env['CAPSWRITER_NO_TRAY'] = '1'
            
            print("[DEBUG] Starting server process...")
            self.server_process = subprocess.Popen(
                [python_exe, "core_server.py"],
                cwd=base_dir,
                startupinfo=startupinfo,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
            )
            print(f"[DEBUG] Server started with PID: {self.server_process.pid}")
            
            # 等待服务端启动
            self.after(2000, self._start_client)
            
            self.service_status.configure(text="🚀 正在启动...", foreground="blue")
            print("[DEBUG] UI updated, waiting for client start...")
            
        except Exception as e:
            print(f"[DEBUG] Error in _start_services: {e}")
            import traceback
            traceback.print_exc()
            self.service_status.configure(text=f"❌ 启动失败", foreground="red")
            messagebox.showerror("启动失败", f"无法启动服务：\n{e}")
    
    def _start_client(self):
        """启动客户端进程"""
        print("[DEBUG] _start_client called")
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 检测是否从 EXE 运行（frozen 模式）
            if getattr(sys, 'frozen', False):
                python_exe = self._find_system_python()
                if not python_exe:
                    raise RuntimeError("无法找到系统 Python 解释器")
            else:
                python_exe = sys.executable
            
            # 启动客户端（隐藏控制台窗口）
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            # 设置环境变量禁用子进程托盘图标
            env = os.environ.copy()
            env['CAPSWRITER_NO_TRAY'] = '1'
            
            print("[DEBUG] Starting client process...")
            self.client_process = subprocess.Popen(
                [python_exe, "core_client.py"],
                cwd=base_dir,
                startupinfo=startupinfo,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
            )
            print(f"[DEBUG] Client started with PID: {self.client_process.pid}")
            
            # 更新 UI 状态
            self.is_running = True
            self.start_btn.configure(text="⏹ 停止服务", bootstyle="danger")
            self.service_status.configure(text="✅ 服务已启动", foreground="green")
            print("[DEBUG] Services started successfully")
            
        except Exception as e:
            print(f"[DEBUG] Error in _start_client: {e}")
            import traceback
            traceback.print_exc()
            self.service_status.configure(text="❌ 客户端启动失败", foreground="red")
    
    def _stop_services(self):
        """停止服务端和客户端进程"""
        import threading
        
        # 更新 UI 状态为正在停止
        self.service_status.configure(text="⏳ 正在停止...", foreground="orange")
        self.start_btn.configure(state="disabled")
        
        def stop_in_background():
            try:
                # Windows 上隐藏控制台窗口
                startupinfo = None
                if sys.platform == 'win32':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                
                # 停止客户端
                if self.client_process and self.client_process.poll() is None:
                    if sys.platform == 'win32':
                        # Windows: 使用 taskkill 强制终止进程树
                        subprocess.run(
                            ['taskkill', '/F', '/T', '/PID', str(self.client_process.pid)],
                            capture_output=True,
                            timeout=10,
                            startupinfo=startupinfo
                        )
                    else:
                        self.client_process.terminate()
                        self.client_process.wait(timeout=5)
                
                # 停止服务端
                if self.server_process and self.server_process.poll() is None:
                    if sys.platform == 'win32':
                        subprocess.run(
                            ['taskkill', '/F', '/T', '/PID', str(self.server_process.pid)],
                            capture_output=True,
                            timeout=10,
                            startupinfo=startupinfo
                        )
                    else:
                        self.server_process.terminate()
                        self.server_process.wait(timeout=5)
                
                # 清理进程引用
                self.server_process = None
                self.client_process = None
                
                # 在主线程更新 UI
                self.after(0, self._on_stop_complete, True)
                
            except Exception as e:
                self.after(0, self._on_stop_complete, False, str(e))
        
        # 在后台线程执行停止操作
        threading.Thread(target=stop_in_background, daemon=True).start()
    
    def _on_stop_complete(self, success: bool, error_msg: str = ""):
        """停止服务完成后的 UI 更新"""
        self.start_btn.configure(state="normal")
        if success:
            self.is_running = False
            self.start_btn.configure(text="🚀 启动服务", bootstyle="success")
            self.service_status.configure(text="⏹ 服务已停止", foreground="gray")
        else:
            self.service_status.configure(text=f"❌ 停止失败: {error_msg}", foreground="red")
    
    def _on_close(self):
        """窗口关闭事件"""
        general_config = self.config.get('general', {})
        minimize_to_tray = general_config.get('minimize_to_tray', True)
        
        if minimize_to_tray:
            # 最小化到托盘
            self._minimize_to_tray()
        else:
            # 直接关闭
            self._exit_app()
    
    def _ensure_tray_icon(self):
        """确保托盘图标已创建（程序启动时调用）"""
        if self._tray_icon is None:
            self._create_tray_icon()
    
    def _minimize_to_tray(self):
        """最小化到系统托盘"""
        # 隐藏窗口
        self.withdraw()
        
        # 创建托盘图标（如果还没创建）
        if self._tray_icon is None:
            self._create_tray_icon()
    
    def _create_tray_icon(self):
        """创建系统托盘图标"""
        try:
            import pystray
            from PIL import Image, ImageDraw
            import threading
            
            # 创建图标
            icon_image = self._create_icon_image()
            
            # 定义菜单
            menu = pystray.Menu(
                pystray.MenuItem("CapsWriter-Offline", lambda: None, enabled=False),
                pystray.MenuItem("👁 显示窗口", self._show_window, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("❌ 退出", self._exit_from_tray)
            )
            
            self._tray_icon = pystray.Icon(
                "CapsWriter-Offline",
                icon_image,
                "CapsWriter-Offline",
                menu
            )
            
            # 在后台线程运行托盘
            self._tray_thread = threading.Thread(target=self._tray_icon.run, daemon=True)
            self._tray_thread.start()
            
        except ImportError:
            # pystray 不可用，直接关闭
            self._exit_app()
    
    def _set_window_icon(self):
        """设置窗口图标（解决 Windows 任务栏图标首次启动显示异常的问题）"""
        from PIL import Image, ImageTk
        
        # 尝试多个可能的图标路径
        possible_paths = [
            "assets/icon.ico",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'icon.ico'),
        ]
        
        # 如果是 PyInstaller 打包的 EXE，添加 _internal 路径
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            possible_paths.insert(0, os.path.join(exe_dir, '_internal', 'assets', 'icon.ico'))
            possible_paths.insert(0, os.path.join(exe_dir, 'assets', 'icon.ico'))
        
        icon_path = None
        for path in possible_paths:
            if os.path.exists(path):
                icon_path = path
                break
        
        if icon_path:
            try:
                # 1. 使用 iconbitmap 设置窗口左上角图标
                self.iconbitmap(icon_path)
                
                # 2. 使用 wm_iconphoto 设置任务栏图标（解决首次启动显示异常）
                # 需要将 ICO 转换为 PhotoImage 格式
                icon_image = Image.open(icon_path)
                # ICO 文件可能包含多个尺寸，选择合适的尺寸
                if hasattr(icon_image, 'n_frames') and icon_image.n_frames > 1:
                    # 尝试获取最大尺寸的图像
                    best_size = 0
                    best_frame = 0
                    for i in range(icon_image.n_frames):
                        icon_image.seek(i)
                        size = icon_image.size[0] * icon_image.size[1]
                        if size > best_size:
                            best_size = size
                            best_frame = i
                    icon_image.seek(best_frame)
                
                # 转换为 RGBA 格式
                if icon_image.mode != 'RGBA':
                    icon_image = icon_image.convert('RGBA')
                
                # 创建多个尺寸的图标（Windows 任务栏需要）
                icon_sizes = [16, 32, 48, 64, 128, 256]
                photo_images = []
                for size in icon_sizes:
                    resized = icon_image.resize((size, size), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(resized)
                    photo_images.append(photo)
                
                # 保存引用防止垃圾回收
                self._icon_photos = photo_images
                
                # 设置任务栏图标
                self.wm_iconphoto(True, *photo_images)
                
            except Exception as e:
                # 图标加载失败时静默忽略
                pass
    
    def _create_icon_image(self):
        """创建托盘图标图像"""
        from PIL import Image, ImageDraw
        
        # 尝试加载现有图标
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'icon.ico')
        if os.path.exists(icon_path):
            try:
                image = Image.open(icon_path)
                if image.mode != 'RGBA':
                    image = image.convert('RGBA')
                return image.resize((64, 64), Image.Resampling.LANCZOS)
            except Exception:
                pass
        
        # 动态生成图标
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        dc = ImageDraw.Draw(image)
        
        blue = (55, 118, 171)
        yellow = (255, 211, 67)
        white = (255, 255, 255)
        
        # 蓝色圆角背景
        dc.rounded_rectangle([2, 2, size-2, size-2], radius=size//4, fill=blue)
        
        # 黄色圆圈
        center = size // 2
        r = size // 3
        dc.ellipse([center-r, center-r, center+r, center+r], fill=yellow)
        
        # 白色圆点
        r2 = r // 2
        dc.ellipse([center-r2, center-r2, center+r2, center+r2], fill=white)
        
        return image
    
    def _show_window(self, icon=None, item=None):
        """显示主窗口"""
        self.deiconify()
        self.lift()
        self.focus_force()
    
    def _exit_from_tray(self, icon=None, item=None):
        """从托盘退出"""
        # 停止托盘图标
        if self._tray_icon:
            self._tray_icon.stop()
            self._tray_icon = None
        
        # 退出应用
        self._exit_app()
    
    def _on_exit(self):
        """退出按钮回调 - 直接退出不询问"""
        self._force_exit()
    
    def _exit_app(self):
        """退出应用程序（可能询问确认）"""
        if self.is_running:
            if messagebox.askyesno("确认退出", "服务正在运行中，是否停止服务并退出？"):
                self._force_exit()
        else:
            self._force_exit()
    
    def _force_exit(self):
        """强制退出 - 彻底关闭所有服务和进程"""
        # 停止托盘图标
        if self._tray_icon:
            try:
                self._tray_icon.stop()
                self._tray_icon = None
            except Exception:
                pass
        
        # 强制终止服务器进程
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=2)
            except Exception:
                pass
            try:
                self.server_process.kill()
            except Exception:
                pass
            self.server_process = None
        
        # 强制终止客户端进程
        if self.client_process:
            try:
                self.client_process.terminate()
                self.client_process.wait(timeout=2)
            except Exception:
                pass
            try:
                self.client_process.kill()
            except Exception:
                pass
            self.client_process = None
        
        self.is_running = False
        self.destroy()


def main():
    """主函数"""
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()

