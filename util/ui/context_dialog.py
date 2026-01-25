
# coding: utf-8
"""
上下文编辑对话框模块

提供 ContextDialog 类用于显示"编辑上下文"对话框。
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from .dialogs import (
    create_modal_dialog,
    DialogResult,
    wait_window,
)
from .toast_constants import DEFAULT_FONT_FAMILY
from . import logger



class ContextDialog:
    """
    上下文编辑对话框

    显示一个模态对话框，让用户输入：
    - 提示词上下文（用于辅助 ASR 识别）

    用户可以编辑后点击确定，更新 Config.context。
    """

    def __init__(self, parent: tk.Tk = None):
        """
        初始化对话框

        Args:
            parent: 父窗口（Tk 主窗口），如果为 None 则创建一个隐藏的 Tk
        """
        if parent is None:
            parent = tk.Tk()
            parent.withdraw()  # 隐藏主窗口

        self.parent = parent
        self.result: Optional[DialogResult] = None

    def show(
        self,
        default_text: str = "",
        title: str = "编辑上下文",
        width: int = 600
    ) -> DialogResult:
        """
        显示对话框

        Args:
            default_text: 默认填充的文本
            title: 对话框标题
            width: 对话框宽度（像素），默认 600

        Returns:
            DialogResult 对象：
            - result.confirmed: 用户是否点击了确定
            - result.data: {'context': str}
        """
        # 创建对话框窗口
        dialog = create_modal_dialog(
            title=title,
            width=width,
            height=200,
            resizable=True,
            withdraw=True
        )

        # 创建容器
        main_frame = ttk.Frame(dialog, padding=(20, 15, 20, 20))
        main_frame.pack(fill="both", expand=True)

        # 字体设置
        label_font = (DEFAULT_FONT_FAMILY, 10, "bold")
        entry_font = (DEFAULT_FONT_FAMILY, 11)

        # 说明
        ttk.Label(
            main_frame,
            text="请输入提示词上下文（辅助 ASR 识别，如专有名词）：",
            font=(DEFAULT_FONT_FAMILY, 9),
            foreground="#666666"
        ).pack(anchor="w", pady=(0, 10))

        # 上下文输入框 (使用 Text 方便输入多行)
        text_widget = tk.Text(
            main_frame,
            height=5,
            font=entry_font,
            wrap="word",
            borderwidth=1,
            relief="solid",
            padx=5,
            pady=5
        )
        text_widget.pack(fill="both", expand=True, pady=(0, 15))
        
        if default_text:
            text_widget.insert("1.0", default_text)

        # 创建按钮区域
        def on_confirm():
            """确定按钮回调"""
            value = text_widget.get("1.0", "end-1c").strip()

            # 保存结果并关闭对话框
            self.result = DialogResult(
                confirmed=True,
                context=value
            )
            dialog.destroy()

        def on_cancel():
            """取消按钮回调"""
            self.result = DialogResult(confirmed=False)
            dialog.destroy()

        # 绑定键盘事件
        dialog.bind("<Escape>", lambda e: on_cancel())
        dialog.bind("<Control-Return>", lambda e: on_confirm())

        # 按钮容器
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0))

        # 确定按钮
        confirm_btn = tk.Button(
            button_frame,
            text="确定 (Ctrl+Enter)",
            command=on_confirm,
            font=(DEFAULT_FONT_FAMILY, 9),
            bg="#4CAF50",
            fg="white",
            activebackground="#45a049",
            relief="flat",
            cursor="hand2",
            padx=15,
            pady=5
        )
        confirm_btn.pack(side="left", padx=5, ipady=0)

        # 取消按钮
        cancel_btn = tk.Button(
            button_frame,
            text="取消 (Esc)",
            command=on_cancel,
            font=(DEFAULT_FONT_FAMILY, 9),
            bg="#f44336",
            fg="white",
            activebackground="#da190b",
            relief="flat",
            cursor="hand2",
            padx=15,
            pady=5
        )
        cancel_btn.pack(side="left", padx=5, ipady=0)

        # 居中并显示
        dialog.update_idletasks()
        _center_window(dialog, width, dialog.winfo_reqheight())
        dialog.deiconify()
        dialog.lift()
        text_widget.focus_set()

        # 等待对话框关闭
        wait_window(dialog)

        return self.result if self.result else DialogResult(confirmed=False)


def _center_window(window: tk.Toplevel, width: int, height: int) -> None:
    """居中显示窗口"""
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")


def show_context_dialog(
    default_text: str = "",
    parent: tk.Tk = None,
    title: str = "编辑上下文",
    width: int = 600
) -> DialogResult:
    """显示上下文编辑对话框（便捷函数）"""
    dialog = ContextDialog(parent)
    return dialog.show(default_text, title, width)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    res = show_context_dialog(default_text="默认上下文")
    print(f"Result: {res.confirmed}, Data: {res.data}")
