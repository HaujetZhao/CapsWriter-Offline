# coding: utf-8
"""
托盘图标模块

Windows: pystray + Win32 API（窗口管理）
Linux:   PySide6 QSystemTrayIcon（原生菜单）
"""

import os
import sys
import time
import threading
import platform
from typing import Optional
from . import logger, set_ui_logger

_IS_WINDOWS = platform.system() == 'Windows'
_IS_LINUX = platform.system() == 'Linux'

_exit_callback = None
_tray_available = None
_tray_instance = None
_lock = threading.Lock()


def _set_exit_callback(callback):
    global _exit_callback
    _exit_callback = callback


def _get_exit_callback():
    return _exit_callback


# ---------------------------------------------------------------------------
# 可用性检测
# ---------------------------------------------------------------------------

def _check_tray_available() -> bool:
    global _tray_available

    if _tray_available is not None:
        return _tray_available

    if _IS_LINUX:
        try:
            from PySide6.QtWidgets import QSystemTrayIcon
            _tray_available = True
        except ImportError as e:
            logger.warning(f"托盘功能不可用（Linux 需安装 PySide6）: {e}")
            _tray_available = False
        except Exception as e:
            logger.warning(f"托盘功能检测失败: {e}")
            _tray_available = False
    else:
        try:
            import pystray
            from PIL import Image
            _tray_available = True
        except ImportError as e:
            logger.warning(f"托盘功能不可用: {e}")
            _tray_available = False
        except Exception as e:
            logger.warning(f"托盘功能检测失败: {e}")
            _tray_available = False

    return _tray_available


# ---------------------------------------------------------------------------
# Windows API（延迟初始化，仅 Windows）
# ---------------------------------------------------------------------------

_win_api_initialized = False
user32 = None
kernel32 = None

SW_HIDE = 0
SW_RESTORE = 9
SC_CLOSE = 0xF060
MF_BYCOMMAND = 0x00000000


def _init_win_api():
    global _win_api_initialized, user32, kernel32
    if _win_api_initialized:
        return
    if not _IS_WINDOWS:
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        _win_api_initialized = True
    except Exception as e:
        logger.warning(f"Windows API 初始化失败: {e}")


def _get_console_hwnd() -> int:
    _init_win_api()
    if kernel32 is None:
        return 0
    return kernel32.GetConsoleWindow()


def _disable_close_button(hwnd: int) -> None:
    if user32 is None:
        return
    h_menu = user32.GetSystemMenu(hwnd, False)
    if h_menu:
        user32.DeleteMenu(h_menu, SC_CLOSE, MF_BYCOMMAND)


def _enable_close_button(hwnd: int) -> None:
    if user32 is None:
        return
    user32.GetSystemMenu(hwnd, True)


def _is_window_minimized(hwnd: int) -> bool:
    if user32 is None:
        return False
    return user32.IsIconic(hwnd) != 0


def _is_window_visible(hwnd: int) -> bool:
    if user32 is None:
        return False
    return user32.IsWindowVisible(hwnd) != 0


# ---------------------------------------------------------------------------
# 图标生成（PIL，Windows/Linux 共用）
# ---------------------------------------------------------------------------

def _create_pil_icon(icon_path: Optional[str] = None):
    from PIL import Image, ImageDraw

    if icon_path and os.path.exists(icon_path):
        try:
            image = Image.open(icon_path)
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            return image.resize((64, 64), Image.Resampling.LANCZOS)
        except Exception:
            pass

    size = 64
    scale = 4
    real_size = size * scale

    image = Image.new('RGBA', (real_size, real_size), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)

    blue = (55, 118, 171)
    yellow = (255, 211, 67)
    white = (255, 255, 255)

    m = 2 * scale
    dc.rounded_rectangle(
        [m, m, real_size - m, real_size - m],
        radius=real_size // 4,
        fill=blue
    )
    center = real_size // 2
    r = real_size // 3.5
    dc.ellipse([center - r, center - r, center + r, center + r], fill=yellow)
    r2 = r // 2
    dc.ellipse([center - r2, center - r2, center + r2, center + r2], fill=white)

    return image.resize((size, size), Image.Resampling.LANCZOS)


def _pil_to_qimage(pil_image):
    from PySide6.QtGui import QImage
    if pil_image.mode != 'RGBA':
        pil_image = pil_image.convert('RGBA')
    data = pil_image.tobytes()
    w, h = pil_image.size
    qimg = QImage(data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
    return qimg


# ---------------------------------------------------------------------------
# Windows 托盘（pystray）
# ---------------------------------------------------------------------------

class _WindowsTray:
    def __init__(self, name, icon_path, more_options):
        import pystray
        from pystray import MenuItem as item

        self.hwnd = _get_console_hwnd()
        self.should_exit = False
        self.title = name or os.path.basename(sys.argv[0]) or "CapsWriter"

        if self.hwnd:
            _disable_close_button(self.hwnd)

        menu_items = [
            item(f"{self.title}", lambda: None, enabled=False),
            item('显示/隐藏', self.toggle_window, default=True),
        ]
        if more_options:
            for opt_name, opt_func in more_options:
                menu_items.append(item(opt_name, opt_func))
        menu_items.append(item('退出', self.on_exit))

        self.icon = pystray.Icon(
            "console_tray",
            _create_pil_icon(icon_path),
            title=self.title,
            menu=tuple(menu_items)
        )

    def toggle_window(self):
        if not self.hwnd or user32 is None:
            return
        if _is_window_visible(self.hwnd):
            user32.ShowWindow(self.hwnd, SW_HIDE)
        else:
            user32.ShowWindow(self.hwnd, SW_RESTORE)
            user32.SetForegroundWindow(self.hwnd)

    def monitor_loop(self):
        while not self.should_exit:
            if self.hwnd and user32:
                if _is_window_visible(self.hwnd) and _is_window_minimized(self.hwnd):
                    user32.ShowWindow(self.hwnd, SW_HIDE)
            time.sleep(0.2)

    def on_exit(self, icon, item):
        logger.info("托盘退出: 用户点击退出菜单")
        self.should_exit = True
        if self.hwnd and user32:
            _enable_close_button(self.hwnd)
            user32.ShowWindow(self.hwnd, SW_RESTORE)
        cb = _get_exit_callback()
        if cb:
            try:
                cb()
            except Exception as e:
                logger.error(f"退出回调出错: {e}")
        try:
            self.icon.stop()
        except Exception:
            pass

    def start(self):
        threading.Thread(target=self.icon.run, daemon=False).start()
        threading.Thread(target=self.monitor_loop, daemon=True).start()
        self.toggle_window()

    def stop(self):
        try:
            self.icon.stop()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Linux 托盘（PySide6 QSystemTrayIcon）
# ---------------------------------------------------------------------------

class _LinuxTray:
    def __init__(self, name, icon_path, more_options):
        from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
        from PySide6.QtGui import QIcon, QPixmap, QFont, QFontDatabase

        self.title = name or os.path.basename(sys.argv[0]) or "CapsWriter"
        self._loop = None
        self._tick_handle = None
        self._running = False
        self._app = QApplication.instance()
        if self._app is None:
            self._app = QApplication([])
        self._app.setQuitOnLastWindowClosed(False)

        preferred = [
            "Noto Sans CJK SC", "Noto Sans SC",
            "WenQuanYi Micro Hei", "WenQuanYi Zen Hei",
            "Source Han Sans SC", "Droid Sans Fallback",
        ]
        families = QFontDatabase.families()
        for font_name in preferred:
            if any(font_name in f for f in families):
                QApplication.setFont(QFont(font_name, 10))
                break

        pil_img = _create_pil_icon(icon_path)
        qimg = _pil_to_qimage(pil_img)
        self._qt_icon = QIcon(QPixmap.fromImage(qimg))

        self._menu = QMenu()
        title_action = self._menu.addAction(self.title)
        title_action.setEnabled(False)
        self._menu.addSeparator()

        for opt_name, opt_func in (more_options or []):
            action = self._menu.addAction(opt_name)
            action.triggered.connect(lambda checked, f=opt_func: f())

        self._menu.addSeparator()
        exit_action = self._menu.addAction('退出')
        exit_action.triggered.connect(self._on_exit)

        self._tray_icon = QSystemTrayIcon(self._qt_icon)
        self._tray_icon.setToolTip(self.title)
        self._tray_icon.setContextMenu(self._menu)
        self._tray_icon.show()

    def _on_exit(self):
        logger.info("托盘退出: 用户点击退出菜单")
        cb = _get_exit_callback()
        if cb:
            try:
                cb()
            except Exception as e:
                logger.error(f"退出回调出错: {e}")
        if self._tray_icon:
            self._tray_icon.hide()

    def _tick(self):
        if not self._running:
            return
        if self._app:
            self._app.processEvents()
        if self._loop:
            self._tick_handle = self._loop.call_later(0.05, self._tick)

    def start(self):
        import asyncio
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("Linux Qt 托盘需要运行中的 asyncio 主循环，跳过事件泵")
            return
        self._running = True
        self._tick()

    def stop(self):
        self._running = False
        if self._tick_handle:
            self._tick_handle.cancel()
            self._tick_handle = None
        if self._tray_icon:
            self._tray_icon.hide()
        if self._app:
            self._app.quit()


# ---------------------------------------------------------------------------
# 公共接口
# ---------------------------------------------------------------------------

def enable_min_to_tray(name: Optional[str] = None, icon_path: Optional[str] = None, exit_callback=None, more_options: list = None) -> None:
    global _tray_instance

    if exit_callback is not None:
        _set_exit_callback(exit_callback)

    if not _check_tray_available():
        logger.info("托盘功能不可用，跳过启用")
        return

    if _IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass

    with _lock:
        if _tray_instance is not None:
            logger.debug(f"托盘已存在，跳过: {_tray_instance}")
            return

        try:
            if _IS_LINUX:
                _tray_instance = _LinuxTray(name, icon_path, more_options)
            else:
                _tray_instance = _WindowsTray(name, icon_path, more_options)
            _tray_instance.start()
            logger.info(f"托盘已创建并启动: {_tray_instance}")
        except Exception as e:
            logger.error(f"托盘创建失败: {e}", exc_info=True)
            _tray_instance = None


def stop_tray() -> None:
    global _tray_instance
    if _tray_instance:
        try:
            _tray_instance.stop()
        except Exception:
            pass
    _tray_instance = None


if __name__ == "__main__":
    enable_min_to_tray()
    print("程序运行中... 你可以右键托盘图标操作。")
    while True:
        time.sleep(1)
