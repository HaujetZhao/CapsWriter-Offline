# coding: utf-8
"""
纠错记录对话框模块

提供 RectifyDialog 类用于显示"添加纠错记录"对话框。
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
from util.logger import get_logger

logger = get_logger('client')


class RectifyDialog:
    """
    纠错记录对话框

    显示一个模态对话框，基于上一次的识别结果，让用户编辑：
    - 原始文本（ASR 识别的错误文本）
    - 纠错文本（正确的文本）

    用户可以编辑后点击确定，将记录保存到 hot-rectify.txt。

    Features:
        - 单行输入框，根据内容自动扩展高度（1-10 行）
        - 禁用滚动，高度自适应
        - 窗口高度动态调整，确保按钮始终可见
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
        recognition_text: str,
        title: str = "添加纠错记录",
        width: int = 600
    ) -> DialogResult:
        """
        显示对话框

        Args:
            recognition_text: 上一次识别的文本（预填充到两个文本框）
            title: 对话框标题
            width: 对话框宽度（像素），默认 600

        Returns:
            DialogResult 对象：
            - result.confirmed: 用户是否点击了确定
            - result.data: {'original': str, 'corrected': str}
        """
        # 创建对话框窗口（初始高度 200，后续会动态调整）
        dialog = create_modal_dialog(
            title=title,
            width=width,
            height=200,
            resizable=True,
            withdraw=True  # 先隐藏窗口，避免闪烁
        )

        # 创建容器
        main_frame = ttk.Frame(dialog, padding=(20, 15, 20, 25))
        main_frame.pack(fill="both", expand=True)

        # 保存宽度参数，用于后续窗口高度调整
        dialog_width = width

        # 创建说明文本
        info_text = (
            "请基于上一次的识别结果，编辑纠错记录：\n"
            "• 原始文本：识别出来的错误文本\n"
            "• 纠错文本：正确的文本\n"
            "点击确定后将保存到 hot-rectify.txt，用于后续 LLM 纠错参考。"
        )
        info_label = ttk.Label(
            main_frame,
            text=info_text,
            font=(DEFAULT_FONT_FAMILY, 9),
            foreground="#666666"
        )
        # info_label.pack(anchor="w", pady=(0, 10))

        # 字体设置
        text_font = (DEFAULT_FONT_FAMILY, 10)

        # 动态高度调整函数
        def auto_resize_textbox(text_widget):
            """根据文本内容自动调整高度（禁用滚动）"""
            text_widget.update_idletasks()

            # 获取文本内容
            content = text_widget.get("1.0", "end-1c")

            if not content:
                line_count = 1
            else:
                # 使用 bbox 方法获取最后一行的位置来计算实际行数
                # 先尝试获取文本末尾的位置
                try:
                    last_line_index = int(text_widget.index('end-1c').split('.')[0])
                    line_count = max(1, last_line_index)
                except:
                    # 降级方案：使用字符数估算
                    # 假设每行约 50 个字符（考虑 600px 宽度和 10pt 字体）
                    estimated_lines = max(1, len(content) // 50 + 1)
                    line_count = min(10, estimated_lines)

            # 限制在 1-10 行之间
            new_height = max(1, min(10, line_count))
            current_height = text_widget.cget('height')

            if current_height != new_height:
                text_widget.configure(height=new_height)
                # 重要：改变高度后，强制刷新整个对话框的布局
                # 这样父容器（main_frame）才能重新计算需求高度
                dialog.update_idletasks()
                return True  # 高度已改变
            return False

        def update_dialog_height():
            """更新窗口高度以适应内容"""
            dialog.update_idletasks()
            new_height = main_frame.winfo_reqheight()
            dialog.geometry(f"{dialog_width}x{new_height}")

            return new_height  # 返回实际设置的高度

        def on_text_change(event=None):
            height_changed = False
            height_changed |= auto_resize_textbox(original_text_widget)
            height_changed |= auto_resize_textbox(corrected_text_widget)

            if height_changed:
                # 更新窗口高度
                new_height = update_dialog_height()
                dialog.geometry(f"{dialog_width}x{new_height}")

        def setup_text_widget(widget):
            widget.configure(yscrollcommand=lambda *args: None) # 彻底禁用内部滚动逻辑
            
            def _on_mod(event):
                if widget.edit_modified():
                    on_text_change()
                    widget.edit_modified(False) # 重置修改标记
                    
            widget.bind("<<Modified>>", _on_mod)
            
        # 创建原始文本输入框（初始高度 1）
        ttk.Label(main_frame, text="原始：", font=(DEFAULT_FONT_FAMILY, 10, "bold")).pack(anchor="w")

        original_text_widget = tk.Text(
            main_frame,
            height=1,  # 初始 1 行
            font=text_font,
            wrap="word",
            spacing1=2,
            spacing2=2,
            spacing3=2,
            borderwidth=1,
            relief="solid",
            padx=10,
            pady=10,
        )
        setup_text_widget(original_text_widget)

        # 锚定在左上角（与 Toast 一致，使用 TOP 避免内容跳动）
        original_text_widget.pack(fill="x", pady=(5, 10))


        # 创建纠错文本输入框（初始高度 1）
        ttk.Label(main_frame, text="纠错：", font=(DEFAULT_FONT_FAMILY, 10, "bold")).pack(anchor="w")

        corrected_text_widget = tk.Text(
            main_frame,
            height=1,  # 初始 1 行
            font=text_font,
            wrap="word",
            spacing1=2,
            spacing2=2,
            spacing3=2,
            borderwidth=1,
            relief="solid",
            padx=10,
            pady=10,
        )
        setup_text_widget(corrected_text_widget)

        # 锚定在左上角（与 Toast 一致，使用 TOP 避免内容跳动）
        corrected_text_widget.pack(fill="x", pady=(5, 10))

        # 预填充识别文本（两个文本框都预填充）
        original_text_widget.insert("1.0", recognition_text)
        corrected_text_widget.insert("1.0", recognition_text)

        # 立即调整文本框高度（在绑定事件前）
        dialog.update_idletasks()
        update_dialog_height()  # 调用但忽略返回值

        # 绑定内容变化事件
        for widget in [original_text_widget, corrected_text_widget]:
            widget.bind("<KeyRelease>", on_text_change)
            widget.bind("<ButtonRelease-1>", on_text_change)
            widget.bind("<KeyPress>", on_text_change)

        # 对话框完全显示后，再次调整高度
        # 使用 after_idle 确保在所有布局完成后执行
        def final_adjustment():
            """对话框完全显示后的最终高度调整"""
            dialog.update_idletasks()

            # 强制重新计算文本框高度
            for widget in [original_text_widget, corrected_text_widget]:
                widget.update_idletasks()
                auto_resize_textbox(widget)

            # 更新窗口高度并获取实际设置的高度
            actual_height = update_dialog_height()

            # 居中显示窗口
            screen_width = dialog.winfo_screenwidth()
            screen_height = dialog.winfo_screenheight()

            # 计算居中位置
            x = (screen_width - dialog_width) // 2
            y = (screen_height - actual_height) // 2
            dialog.geometry(f"{dialog_width}x{actual_height}+{x}+{y}")

            # 最后显示窗口（避免闪烁）
            dialog.deiconify()
            # 确保窗口在最前面
            dialog.lift()

        # 使用 after_idle 在事件循环空闲时执行
        dialog.after_idle(final_adjustment)

        # 创建按钮区域
        def on_confirm():
            """确定按钮回调"""
            original_value = original_text_widget.get("1.0", "end-1c").strip()
            corrected_value = corrected_text_widget.get("1.0", "end-1c").strip()

            # 验证输入
            if not original_value or not corrected_value:
                messagebox.showwarning("输入为空", "原始文本和纠错文本不能为空！")
                return

            if original_value == corrected_value:
                result = messagebox.askyesno(
                    "文本相同",
                    "原始文本和纠错文本完全相同，是否仍要保存？"
                )
                if not result:
                    return

            # 保存结果并关闭对话框
            self.result = DialogResult(
                confirmed=True,
                original=original_value,
                corrected=corrected_value
            )
            dialog.destroy()

        def on_cancel():
            """取消按钮回调"""
            self.result = DialogResult(confirmed=False)
            dialog.destroy()

        # 绑定键盘事件（Esc 取消，Ctrl+Enter 确定）
        dialog.bind("<Escape>", lambda e: on_cancel())
        dialog.bind("<Control-Return>", lambda e: on_confirm())

        # 创建按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0))

        # 使用 tk.Button 而不是 ttk.Button，可以更好地控制高度
        confirm_btn = tk.Button(
            button_frame,
            text="确定 (Ctrl+Enter)",
            command=on_confirm,
            width=15,
            height=1,
            font=(DEFAULT_FONT_FAMILY, 10),
            bg="#4CAF50",
            fg="white",
            activebackground="#45a049",
            relief="flat",
            cursor="hand2"
        )
        confirm_btn.pack(side="left", padx=5, ipady=0)  # ipady 增加垂直内部填充

        cancel_btn = tk.Button(
            button_frame,
            text="取消 (Esc)",
            command=on_cancel,
            width=15,
            height=1,
            font=(DEFAULT_FONT_FAMILY, 10),
            bg="#f44336",
            fg="white",
            activebackground="#da190b",
            relief="flat",
            cursor="hand2",
        )
        cancel_btn.pack(side="left", padx=5, ipady=0)  # ipady 增加垂直内部填充

        update_dialog_height()  # 调用但忽略返回值

        # 设置焦点到第一个文本框
        original_text_widget.focus_set()

        # 等待对话框关闭
        wait_window(dialog)

        logger.debug(
            f"对话框关闭: confirmed={self.result.confirmed if self.result else False}, "
            f"original={self.result.get('original', '')[:30] if self.result else ''}..."
        )

        return self.result if self.result else DialogResult(confirmed=False)


# ======================================================================
# 便捷函数
# ======================================================================

def show_rectify_dialog(
    recognition_text: str,
    parent: tk.Tk = None,
    title: str = "添加纠错记录",
    width: int = 600
) -> DialogResult:
    """
    显示纠错记录对话框（便捷函数）

    Args:
        recognition_text: 上一次识别的文本
        parent: 父窗口（可选）
        title: 对话框标题
        width: 对话框宽度（像素），默认 600

    Returns:
        DialogResult 对象
    """
    dialog = RectifyDialog(parent)
    return dialog.show(recognition_text, title, width)


if __name__ == "__main__":
    # 测试代码
    root = tk.Tk()
    root.withdraw()

    result = show_rectify_dialog(
        recognition_text="原锯子不对",
        parent=root, 
        width=800
    )

    if result:
        print(f"确认: {result.confirmed}")
        print(f"原始文本: {result.get('original')}")
        print(f"纠错文本: {result.get('corrected')}")
    else:
        print("用户取消")
