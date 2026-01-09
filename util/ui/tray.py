import os
import sys
import time
import threading
import ctypes
from ctypes import wintypes
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

# --- Windows API 常量与定义 ---
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_HIDE = 0
SW_RESTORE = 9  # 关键：用于从最小化还原
SW_SHOW = 5

SC_CLOSE = 0xF060
MF_BYCOMMAND = 0x00000000

# 全局变量，防止重复启动
_tray_instance = None
_lock = threading.Lock()

# --- 辅助函数 ---
def _get_console_hwnd():
    return kernel32.GetConsoleWindow()

def _disable_close_button(hwnd):
    """禁用窗口的关闭按钮 (X)"""
    h_menu = user32.GetSystemMenu(hwnd, False)
    if h_menu:
        user32.DeleteMenu(h_menu, SC_CLOSE, MF_BYCOMMAND)

def _enable_close_button(hwnd):
    """恢复窗口的关闭按钮"""
    user32.GetSystemMenu(hwnd, True)

def _is_window_minimized(hwnd):
    return user32.IsIconic(hwnd) != 0

def _is_window_visible(hwnd):
    return user32.IsWindowVisible(hwnd) != 0

def _create_icon(icon_path=None):
    """
    优先从指定路径加载图标文件，如果不存在则动态生成
    风格：Python 蓝黄 (Modern Flat)
    描述：圆角矩形，蓝底黄芯

    Args:
        icon_path: 图标文件路径
    """
    # 如果图标文件存在，直接加载
    if os.path.exists(icon_path):
        try:
            image = Image.open(icon_path)
            # 确保是 RGBA 模式
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            # 调整到标准尺寸
            return image.resize((64, 64), Image.Resampling.LANCZOS)
        except Exception as e:
            # 如果加载失败，继续使用动态生成
            print(f"警告: 无法加载图标文件 {icon_path}: {e}")

    # 动态生成图标（原有逻辑）
    size = 64
    scale = 4
    real_size = size * scale

    image = Image.new('RGBA', (real_size, real_size), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)

    blue = (55, 118, 171)
    yellow = (255, 211, 67)
    white = (255, 255, 255)

    # 绘制蓝色圆角背景（模拟圆角矩形，用画圆+填色实现）
    m = 2 * scale
    dc.rounded_rectangle(
        [m, m, real_size-m, real_size-m],
        radius=real_size//4,
        fill=blue
    )

    # 绘制中间的黄色圆圈
    center = real_size // 2
    r = real_size // 3.5
    dc.ellipse([center-r, center-r, center+r, center+r], fill=yellow)

    # 绘制中间的小白点（像眼睛瞳孔，表示 monitoring）
    r2 = r // 2
    dc.ellipse([center-r2, center-r2, center+r2, center+r2], fill=white)

    return image.resize((size, size), Image.Resampling.LANCZOS)

# --- 核心逻辑类 ---
class _TraySystem:
    def __init__(self, name=None, icon_path=None):
        self.hwnd = _get_console_hwnd()
        self.should_exit = False

        # 使用传入的名字，或者从 sys.argv 获取
        self.title = name if name else (os.path.basename(sys.argv[0]) or "Console App")

        # 禁用关闭按钮
        if self.hwnd:
            _disable_close_button(self.hwnd)

        # 定义菜单
        menu = (
            item(f"{self.title}", lambda: None, enabled=False),
            item(f'显示/隐藏', self.toggle_window, default=True),
            item(f'退出程序', self.on_exit),
        )

        self.icon = pystray.Icon(
            "console_tray",
            _create_icon(icon_path),
            title=f"{self.title}",
            menu=menu
        )

    def toggle_window(self):
        """切换显示状态，核心修复了还原逻辑"""
        if not self.hwnd: return

        if _is_window_visible(self.hwnd):
            user32.ShowWindow(self.hwnd, SW_HIDE)
        else:
            # 必须使用 SW_RESTORE 才能正确从最小化状态恢复
            user32.ShowWindow(self.hwnd, SW_RESTORE)
            user32.SetForegroundWindow(self.hwnd)

    def monitor_loop(self):
        """监控线程：检测最小化操作"""
        while not self.should_exit:
            if self.hwnd:
                # 如果窗口可见 且 处于最小化状态 -> 隐藏它
                if _is_window_visible(self.hwnd) and _is_window_minimized(self.hwnd):
                    user32.ShowWindow(self.hwnd, SW_HIDE)
                    # 可选：发个通知
                    # self.icon.notify("程序已隐藏到托盘运行", "提示")
            time.sleep(0.2)

    def on_exit(self, icon, item):
        """托盘退出处理"""
        self.should_exit = True
        self.icon.visible = False
        self.icon.stop()
        
        if self.hwnd:
            _enable_close_button(self.hwnd)
            user32.ShowWindow(self.hwnd, SW_RESTORE)
        
        # 强制结束整个进程
        os._exit(0)

    def start(self):
        """启动所有线程"""
        # 1. 托盘图标线程（非守护线程，确保正常退出）
        t_tray = threading.Thread(target=self.icon.run, daemon=False)
        t_tray.start()

        # 2. 状态监控线程（守护线程）
        t_monitor = threading.Thread(target=self.monitor_loop, daemon=True)
        t_monitor.start()

        self.toggle_window()
        # print(f"[{self.title}] 托盘保护已启动：关闭按钮已禁用，最小化将自动隐藏。")

# --- 对外暴露的启动函数 ---
def enable_min_to_tray(name=None, icon_path=None):
    """
    启用最小化到托盘功能。
    如果检测不到控制台窗口（如 .pyw 运行），则不执行任何操作。

    Args:
        name: 托盘图标显示的名称，如果为 None 则使用程序名称
        icon_path: 可选的图标文件路径，如果为 None 则使用默认路径
    """
    global _tray_instance

    # 简单的 DPI 感知设置，防止图标模糊
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except:
        pass

    with _lock:
        if _tray_instance is not None:
            return  # 已经启动过，直接返回

        if not _get_console_hwnd():
            # 没有控制台窗口（可能是 IDE 内部运行或 .pyw），跳过
            return

        _tray_instance = _TraySystem(name, icon_path)
        _tray_instance.start()


if __name__ == "__main__":
    print("程序运行中... 你可以双击托盘图标隐藏我。")
    while True:
        time.sleep(1)
