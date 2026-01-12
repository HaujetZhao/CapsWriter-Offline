# coding: utf-8
"""
托盘图标模块

提供最小化到系统托盘的功能。
仅在 Windows 平台有效。

功能：
- 禁用控制台窗口的关闭按钮（防止误关）
- 最小化时自动隐藏到托盘
- 双击托盘图标显示/隐藏窗口
- 托盘菜单退出程序
"""

import os
import sys
import time
import threading
import ctypes
from ctypes import wintypes
from typing import Optional

from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

# 日志记录器（由主程序传入）
_logger = None

# 退出回调函数（由主程序传入）
_exit_callback = None

def _set_logger(logger):
    """设置日志记录器"""
    global _logger
    _logger = logger

def _get_logger():
    return _logger

def _set_exit_callback(callback):
    """设置退出回调函数"""
    global _exit_callback
    _exit_callback = callback

def _get_exit_callback():
    return _exit_callback

# Windows API 常量
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_HIDE = 0
SW_RESTORE = 9
SW_SHOW = 5
SC_CLOSE = 0xF060
MF_BYCOMMAND = 0x00000000

# 全局变量
_tray_instance: Optional['_TraySystem'] = None
_lock = threading.Lock()


def _get_console_hwnd() -> int:
    """获取控制台窗口句柄"""
    return kernel32.GetConsoleWindow()


def _disable_close_button(hwnd: int) -> None:
    """禁用窗口的关闭按钮"""
    h_menu = user32.GetSystemMenu(hwnd, False)
    if h_menu:
        user32.DeleteMenu(h_menu, SC_CLOSE, MF_BYCOMMAND)


def _enable_close_button(hwnd: int) -> None:
    """恢复窗口的关闭按钮"""
    user32.GetSystemMenu(hwnd, True)


def _is_window_minimized(hwnd: int) -> bool:
    """检查窗口是否最小化"""
    return user32.IsIconic(hwnd) != 0


def _is_window_visible(hwnd: int) -> bool:
    """检查窗口是否可见"""
    return user32.IsWindowVisible(hwnd) != 0


def _create_icon(icon_path: Optional[str] = None) -> Image.Image:
    """
    创建托盘图标
    
    优先从指定路径加载图标文件，如果不存在则动态生成。
    
    Args:
        icon_path: 图标文件路径
        
    Returns:
        PIL Image 对象
    """
    # 如果图标文件存在，直接加载
    if icon_path and os.path.exists(icon_path):
        try:
            image = Image.open(icon_path)
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            return image.resize((64, 64), Image.Resampling.LANCZOS)
        except Exception:
            pass  # 加载失败则使用动态生成

    # 动态生成图标
    size = 64
    scale = 4
    real_size = size * scale

    image = Image.new('RGBA', (real_size, real_size), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)

    blue = (55, 118, 171)
    yellow = (255, 211, 67)
    white = (255, 255, 255)

    # 蓝色圆角背景
    m = 2 * scale
    dc.rounded_rectangle(
        [m, m, real_size - m, real_size - m],
        radius=real_size // 4,
        fill=blue
    )

    # 黄色圆圈
    center = real_size // 2
    r = real_size // 3.5
    dc.ellipse([center - r, center - r, center + r, center + r], fill=yellow)

    # 白色圆点
    r2 = r // 2
    dc.ellipse([center - r2, center - r2, center + r2, center + r2], fill=white)

    return image.resize((size, size), Image.Resampling.LANCZOS)


class _TraySystem:
    """托盘系统内部类"""
    
    def __init__(self, name: Optional[str] = None, icon_path: Optional[str] = None, more_options: list = None):
        self.hwnd = _get_console_hwnd()
        self.should_exit = False
        self.title = name if name else (os.path.basename(sys.argv[0]) or "Console App")

        # 禁用关闭按钮
        if self.hwnd:
            _disable_close_button(self.hwnd)

        # 定义菜单
        menu_items = [
            item(f"{self.title}", lambda: None, enabled=False),
            item('👁️ 显示/隐藏', self.toggle_window, default=True),
        ]

        # 添加额外选项
        if more_options:
            for opt_name, opt_func in more_options:
                menu_items.append(item(opt_name, opt_func))

        menu_items.append(item('❌ 退出', self.on_exit))

        self.icon = pystray.Icon(
            "console_tray",
            _create_icon(icon_path),
            title=f"{self.title}",
            menu=tuple(menu_items)
        )

    def toggle_window(self) -> None:
        """切换窗口显示状态"""
        if not self.hwnd:
            return

        if _is_window_visible(self.hwnd):
            user32.ShowWindow(self.hwnd, SW_HIDE)
        else:
            user32.ShowWindow(self.hwnd, SW_RESTORE)
            user32.SetForegroundWindow(self.hwnd)

    def monitor_loop(self) -> None:
        """监控线程：检测最小化操作"""
        while not self.should_exit:
            if self.hwnd:
                # 窗口可见且最小化 -> 隐藏到托盘
                if _is_window_visible(self.hwnd) and _is_window_minimized(self.hwnd):
                    user32.ShowWindow(self.hwnd, SW_HIDE)
            time.sleep(0.2)

    def on_exit(self, icon, item) -> None:
        """托盘退出处理"""
        log = _get_logger()
        exit_callback = _get_exit_callback()

        if log:
            log.info("托盘退出: 用户点击退出菜单，准备清理资源并退出")

        # 1. 设置退出标志，停止监控循环
        self.should_exit = True
        if log:
            log.debug("已设置托盘退出标志")

        # 2. 恢复窗口关闭按钮并显示窗口
        if self.hwnd:
            _enable_close_button(self.hwnd)
            user32.ShowWindow(self.hwnd, SW_RESTORE)
            if log:
                log.debug("已恢复窗口显示")

        # 3. 调用退出回调函数，请求主程序退出
        if exit_callback:
            try:
                if log:
                    log.debug("正在调用退出回调函数...")
                exit_callback()
                if log:
                    log.info("退出回调函数已调用")
            except Exception as e:
                if log:
                    log.error(f"调用退出回调函数时发生错误: {e}")



        # 5. 停止托盘图标
        try:
            if log:
                log.debug("正在停止托盘图标线程...")
            self.icon.stop()
            if log:
                log.debug("托盘图标线程已停止")
        except Exception as e:
            if log:
                log.warning(f"停止托盘图标时发生错误: {e}")

    def start(self) -> None:
        """启动托盘系统"""
        # 托盘图标线程
        t_tray = threading.Thread(target=self.icon.run, daemon=False)
        t_tray.start()

        # 状态监控线程
        t_monitor = threading.Thread(target=self.monitor_loop, daemon=True)
        t_monitor.start()

        # 启动时隐藏窗口
        self.toggle_window()


def enable_min_to_tray(name: Optional[str] = None, icon_path: Optional[str] = None, logger=None, exit_callback=None, more_options: list = None) -> None:
    """
    启用最小化到托盘功能

    如果检测不到控制台窗口（如 .pyw 运行），则不执行任何操作。

    Args:
        name: 托盘图标显示的名称，默认使用程序名称
        icon_path: 图标文件路径，默认动态生成
        logger: 日志记录器，如果传入则使用主程序的统一日志记录器
        exit_callback: 退出回调函数，当用户点击托盘退出菜单时调用
        more_options: 额外菜单项列表，格式为 [(名称, 回调函数), ...]
    """
    global _tray_instance

    # 设置日志记录器
    if logger is not None:
        _set_logger(logger)

    # 设置退出回调函数
    if exit_callback is not None:
        _set_exit_callback(exit_callback)

    # DPI 感知设置
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    with _lock:
        if _tray_instance is not None:
            return  # 已启动

        if not _get_console_hwnd():
            return  # 没有控制台窗口

        _tray_instance = _TraySystem(name, icon_path, more_options)
        _tray_instance.start()



def stop_tray() -> None:
    """停止托盘图标"""
    global _tray_instance
    if _tray_instance and _tray_instance.icon:
        try:
            _tray_instance.icon.stop()
        except Exception:
            pass
    _tray_instance = None


if __name__ == "__main__":
    enable_min_to_tray()
    print("程序运行中... 你可以双击托盘图标隐藏我。")
    while True:
        time.sleep(1)
