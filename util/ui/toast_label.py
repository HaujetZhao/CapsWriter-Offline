"""
Toast Label 窗口模块

基于 Label 组件的浮动消息窗口，适合普通提示消息。
"""
import logging
import tkinter as tk
from tkinter import font
from typing import Optional, Callable, Union

from .toast_base import (
    ToastWindowBase,
    add_zero_width_for_chinese,
)
from .toast_constants import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_PADDING_X,
    DEFAULT_PADDING_Y,
    MIN_WINDOW_HEIGHT,
    LABEL_HEIGHT_PADDING,
)
from .toast_logger import get_toast_logger

# 配置日志（智能检测主程序配置）
logger = get_toast_logger(__name__)


class ToastWindowLabel(ToastWindowBase):
    """基于 Label 组件的浮动消息窗口
    
    适合普通提示消息，支持简单的文本更新。
    
    Features:
        - 简单高效的文本显示
        - 自动换行（使用 wraplength）
        - 支持 Markdown 渲染
    """

    def __init__(
        self,
        parent_root: tk.Tk,
        text: str,
        font_size: int = 14,
        font_family: str = '',
        bg: str = '#075077',
        fg: str = 'white',
        duration: int = 3000,
        initial_width: Union[float, int] = 400,
        initial_height: int = 0,
        streaming: bool = False,
        stop_callback: Optional[Callable[[], None]] = None,
        markdown: bool = False,
        editable: bool = False
    ) -> None:
        """创建基于 Label 组件的浮动消息窗口
        
        Args:
            parent_root: 父窗口（Tk 主窗口）
            text: 初始文本内容
            font_size: 字体大小（像素）
            font_family: 字体名称，空字符串使用默认字体
            bg: 背景颜色
            fg: 前景色（文字颜色）
            duration: 自动关闭时长（毫秒）
            initial_width: 初始宽度，0-1 为屏幕比例，>1 为像素值
            initial_height: 初始高度，0 表示自动计算
            streaming: 是否为流式输出模式
            stop_callback: 窗口关闭时的回调函数
            markdown: 是否启用 Markdown 渲染
            editable: Markdown 渲染后是否允许编辑
        """
        # 初始化基类
        super().__init__(
            parent_root, text, font_size, font_family, bg, fg,
            duration, initial_width, initial_height, streaming,
            stop_callback, markdown, editable
        )

        # 计算实际宽度
        actual_width = self._calculate_actual_width()

        # 用于增量插入
        self.last_char_count = 0

        # 处理文本：在中文字符后添加零宽空格
        processed_text = add_zero_width_for_chinese(text) if text else text

        # 如果未指定字体，使用默认字体
        font_name = font_family if font_family else DEFAULT_FONT_FAMILY

        # 创建文字标签
        self.label = tk.Label(
            self.window,
            text=processed_text,
            font=(font_name, font_size),
            fg=fg,
            bg=bg,
            justify=tk.LEFT,
            wraplength=actual_width - (DEFAULT_PADDING_X * 2),
            anchor='nw'
        )

        # 使用 fill=BOTH 和 expand=True 填充窗口
        self.label.pack(
            side=tk.TOP,
            fill=tk.BOTH,
            expand=True,
            padx=DEFAULT_PADDING_X,
            pady=DEFAULT_PADDING_Y
        )

        # 初始化字符计数
        if text:
            self.last_char_count = len(text)

        # 强制更新布局
        self.window.update_idletasks()

        # 设置初始窗口位置
        self._set_window_position(initial=True)
        
        # 如果是非流式模式且启用了 Markdown，立即转换
        if not streaming and markdown:
            self.window.update()
            self._switch_to_markdown()

    def _set_window_position(self, initial: bool = False) -> None:
        """设置窗口位置
        
        Args:
            initial: 是否为初始位置（屏幕中央，单行高度）
        """
        try:
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()

            # 计算初始宽度
            calculated_width = self._calculate_actual_width()

            # 获取 Label 的理想高度
            needed_h = self.label.winfo_reqheight() + LABEL_HEIGHT_PADDING

            # 如果设置了初始高度，使用较大值
            if self.initial_height > 0:
                window_height = max(self.initial_height, needed_h)
            else:
                window_height = needed_h

            # 限制最小高度
            window_height = max(window_height, MIN_WINDOW_HEIGHT)
            window_width = calculated_width

            if initial:
                # 初始位置：水平居中，顶部在屏幕中间
                x = (screen_width - window_width) // 2
                y = screen_height // 2
            else:
                # 保持当前位置，只更新大小
                x = self.window.winfo_x()
                y = self.window.winfo_y()

            self.window.geometry(f'{window_width}x{window_height}+{x}+{y}')
        except tk.TclError as e:
            logger.warning(f"设置窗口位置失败: {e}")

    def update_text(self, new_text: str) -> None:
        """更新文本内容
        
        Label 不支持增量插入，每次更新都会替换全部文本。
        
        Args:
            new_text: 新的完整文本内容
        """
        if not self.streaming:
            return

        # 计算新增的字符
        current_char_count = len(new_text)
        if current_char_count > self.last_char_count:
            # 保存完整文本
            self.full_text = new_text

            # 处理文本：在中文字符后添加零宽空格
            processed_text = add_zero_width_for_chinese(new_text)

            try:
                # Label 不支持增量插入，只能替换全部文本
                self.label.config(text=processed_text)

                # 强制同步布局计算
                self.window.update_idletasks()

                # 计算窗口需要的新高度
                needed_h = self.label.winfo_reqheight() + LABEL_HEIGHT_PADDING
                current_h = self.window.winfo_height()
                current_w = self.window.winfo_width()

                # 如果需要增长高度
                if needed_h > current_h:
                    curr_x = self.window.winfo_x()
                    curr_y = self.window.winfo_y()
                    self.window.geometry(f"{current_w}x{int(needed_h)}+{curr_x}+{curr_y}")

                self.last_char_count = current_char_count
            except tk.TclError:
                # 窗口已被销毁
                self.streaming = False

    def _destroy_content_widget(self) -> None:
        """销毁 Label 组件"""
        if hasattr(self, 'label'):
            try:
                self.label.destroy()
            except tk.TclError:
                pass
