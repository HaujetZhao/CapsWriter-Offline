# coding: utf-8
"""
对话框基础模块

提供对话框的通用工具函数和基类。
"""

import ctypes
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable

from .toast_constants import DEFAULT_FONT_FAMILY
from .toast_logger import get_toast_logger

logger = get_toast_logger(__name__)

# DPI 感知设置（与 toast_base.py 保持一致）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except (OSError, AttributeError):
    pass


# ============================================================
# 工具函数
# ============================================================

def create_modal_dialog(
    title: str,
    width: int = 600,
    height: int = 400,
    resizable: bool = False,
    withdraw: bool = True
) -> tk.Toplevel:
    """
    创建模态对话框窗口

    Args:
        title: 窗口标题
        width: 窗口宽度（像素）
        height: 窗口高度（像素）
        resizable: 是否允许调整窗口大小
        withdraw: 是否先隐藏窗口（避免闪烁），默认 True

    Returns:
        tkinter Toplevel 窗口对象
    """
    # 创建 Toplevel 窗口
    dialog = tk.Toplevel()
    dialog.title(title)

    # 先隐藏窗口，避免闪烁
    if withdraw:
        dialog.withdraw()

    # 设置窗口大小
    dialog.geometry(f"{width}x{height}")
    dialog.resizable(resizable, resizable)

    # 设置为模态窗口
    dialog.transient()  # 属于主窗口
    dialog.grab_set()   # 捕获焦点，阻止用户操作其他窗口

    # 居中显示
    _center_window(dialog, width, height)

    logger.debug(f"创建模态对话框: {title} ({width}x{height})")

    return dialog


def _center_window(window: tk.Toplevel, width: int, height: int) -> None:
    """
    将窗口居中显示在屏幕上

    Args:
        window: 窗口对象
        width: 窗口宽度
        height: 窗口高度
    """
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    x = (screen_width - width) // 2
    y = (screen_height - height) // 2

    window.geometry(f"+{x}+{y}")


def create_label_button_frame(
    parent: tk.Widget,
    label_text: str,
    on_confirm: Callable[[], None],
    on_cancel: Callable[[], None],
    confirm_text: str = "确定",
    cancel_text: str = "取消"
) -> ttk.Frame:
    """
    创建标准按钮区域

    Args:
        parent: 父容器
        label_text: 说明文本
        on_confirm: 确定按钮回调
        on_cancel: 取消按钮回调
        confirm_text: 确定按钮文本
        cancel_text: 取消按钮文本

    Returns:
        按钮容器 Frame
    """
    frame = ttk.Frame(parent)
    frame.pack(pady=10)

    ttk.Button(frame, text=confirm_text, command=on_confirm, width=10).pack(side="left", padx=5)
    ttk.Button(frame, text=cancel_text, command=on_cancel, width=10).pack(side="left", padx=5)

    return frame


def create_scrolled_text(
    parent: tk.Widget,
    height: int = 5,
    font: tuple = (DEFAULT_FONT_FAMILY, 10)
) -> tk.Text:
    """
    创建带滚动条的文本框

    Args:
        parent: 父容器
        height: 文本框高度（行数）
        font: 字体设置

    Returns:
        Text 控件对象
    """
    # 创建 Text 控件
    text_widget = tk.Text(parent, height=height, font=font, wrap="word")

    # 添加滚动条
    scrollbar = ttk.Scrollbar(parent, command=text_widget.yview)
    text_widget.configure(yscrollcommand=scrollbar.set)

    return text_widget


def pack_scrolled_text(
    text_widget: tk.Text,
    scrollbar: ttk.Scrollbar,
    label_text: Optional[str] = None,
    parent: tk.Widget = None,
    padx: int = 10,
    pady_top: int = 10,
    pady_bottom: int = 5
) -> None:
    """
    布局带滚动条的文本框

    Args:
        text_widget: Text 控件
        scrollbar: 滚动条
        label_text: 可选的标签文本
        parent: 父容器（用于添加标签）
        padx: 水平边距
        pady_top: 顶部边距
        pady_bottom: 底部边距
    """
    # 添加标签（如果提供）
    if label_text and parent:
        ttk.Label(parent, text=label_text).pack(anchor="w", padx=padx, pady=(pady_top, 0))

    # 布局文本框和滚动条
    text_widget.pack(fill="both", expand=True, padx=padx, pady=(0 if label_text else pady_top, pady_bottom))
    scrollbar.pack(side="right", fill="y")


class DialogResult:
    """对话框结果封装"""

    def __init__(self, confirmed: bool, **data):
        self.confirmed = confirmed  # 用户是否点击了确定
        self.data = data             # 对话框返回的数据

    def __bool__(self) -> bool:
        """是否确认"""
        return self.confirmed

    def get(self, key: str, default=None):
        """获取数据"""
        return self.data.get(key, default)


def wait_window(dialog: tk.Toplevel) -> None:
    """
    等待窗口关闭（模态对话框标准用法）

    Args:
        dialog: 对话框窗口
    """
    dialog.wait_window()
