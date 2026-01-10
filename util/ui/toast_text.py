"""
Toast Text 窗口模块

基于 Text 组件的浮动消息窗口，适合流式输出场景（如 LLM 实时显示）。
"""
import logging
import tkinter as tk
from tkinter import font
from typing import Optional, Callable, Union

from util.ui.toast_base import (
    ToastWindowBase,
    DEFAULT_FONT_FAMILY,
    DEFAULT_PADDING_X,
    DEFAULT_PADDING_Y,
    MIN_WINDOW_HEIGHT,
)

# 配置日志
logger = logging.getLogger(__name__)

# ============================================================
# 常量定义
# ============================================================

STREAMING_TEXT_HEIGHT = 50  # 流式模式预设行数，防止内容多时自动滚动
NON_STREAMING_TEXT_HEIGHT = 1  # 非流式模式初始行数
HEIGHT_PADDING = 40  # 窗口高度的额外边距


class ToastWindowText(ToastWindowBase):
    """基于 Text 组件的浮动消息窗口
    
    适合流式输出场景，支持增量插入文本，窗口高度自动增长。
    
    Features:
        - 支持流式文本输出（逐字显示）
        - 窗口高度根据内容自动调整
        - 支持 Markdown 渲染（流式完成后转换）
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
        markdown: bool = False
    ) -> None:
        """创建基于 Text 组件的浮动消息窗口
        
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
        """
        # 初始化基类
        super().__init__(
            parent_root, text, font_size, font_family, bg, fg,
            duration, initial_width, initial_height, streaming,
            stop_callback, markdown
        )

        # 创建字体对象用于计算行高
        font_name = self.font_family if self.font_family else 'Microsoft YaHei'
        self.my_font = font.Font(family=font_name, size=self.font_size)
        self.line_height = self.my_font.metrics('linespace')
        self.last_char_count = 0

        # 创建 Text 组件
        text_height = STREAMING_TEXT_HEIGHT if streaming else NON_STREAMING_TEXT_HEIGHT
        
        self.text_area = tk.Text(
            self.window,
            font=self.my_font,
            fg=self.fg,
            bg=self.bg,
            padx=DEFAULT_PADDING_X,
            pady=DEFAULT_PADDING_Y,
            borderwidth=0,
            highlightthickness=0,
            wrap=tk.CHAR,  # 按字符自动换行
            insertofftime=0,
            state=tk.DISABLED,
            cursor="arrow",
            height=text_height
        )

        # 锚定在左上角，使用 fill=X 水平填充窗口
        self.text_area.pack(side=tk.TOP, anchor='nw', fill=tk.X)

        # 初始化时插入初始文本
        if text:
            self.text_area.config(state=tk.NORMAL)
            self.text_area.insert(tk.END, text)
            self.text_area.config(state=tk.DISABLED)
            self.last_char_count = len(text)
            
            # 如果是非流式模式，需要先设置窗口宽度，再计算实际行数
            if not streaming:
                self._adjust_height_for_content()

        # 强制更新布局
        self.window.update_idletasks()

        # 设置初始窗口位置
        self._set_window_position(initial=True)
        
        # 如果是非流式模式且启用了 Markdown，立即转换
        if not streaming and markdown:
            self.window.update()
            self._switch_to_markdown()

    def _adjust_height_for_content(self) -> None:
        """根据内容调整窗口高度（非流式模式使用）"""
        # 先计算并设置窗口宽度
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        if 0 < self.initial_width < 1:
            calculated_width = int(screen_width * self.initial_width)
        else:
            calculated_width = int(self.initial_width)
        
        # 设置临时窗口大小（只设置宽度，高度暂时设为100）
        x = (screen_width - calculated_width) // 2
        y = (screen_height - 100) // 2
        self.window.geometry(f'{calculated_width}x100+{x}+{y}')
        
        # 强制更新，让 Text 组件按照新宽度重新计算换行
        self.window.update_idletasks()
        
        # 现在计算实际行数
        result = self.text_area.count('1.0', 'end', 'displaylines')
        actual_lines = result[0] if result else 1
        logger.debug(f"非流式模式 - 实际行数: {actual_lines}")
        self.text_area.config(height=actual_lines)

    def _set_window_position(self, initial: bool = False) -> None:
        """设置窗口位置
        
        Args:
            initial: 是否为初始位置（屏幕中央，单行高度）
        """
        try:
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()

            # 更新窗口以确保获取正确的尺寸
            self.window.update_idletasks()

            # 计算初始宽度
            if 0 < self.initial_width < 1:
                calculated_width = int(screen_width * self.initial_width)
            else:
                calculated_width = int(self.initial_width)

            # 获取实际渲染的行数
            result = self.text_area.count('1.0', 'end', 'displaylines')
            current_lines = result[0] if result else 1

            # 精确计算高度：行数 * 行高 + 上下 Padding
            needed_h = (current_lines * self.line_height) + HEIGHT_PADDING

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

            self.window.geometry(f'{window_width}x{int(window_height)}+{x}+{y}')
        except tk.TclError as e:
            logger.warning(f"设置窗口位置失败: {e}")

    def update_text(self, new_text: str) -> None:
        """更新文本内容（增量插入模式）
        
        仅在流式模式下有效。增量插入新字符到 Text 组件末尾，
        并根据内容自动调整窗口高度。
        
        Args:
            new_text: 完整的新文本内容
        """
        if not self.streaming:
            return

        # 检查窗口是否还存在
        try:
            if not self.window.winfo_exists():
                self.streaming = False
                return
        except tk.TclError:
            self.streaming = False
            return

        # 计算新增的字符
        current_char_count = len(new_text)
        if current_char_count > self.last_char_count:
            # 保存完整文本
            self.full_text = new_text
            
            # 获取新增部分
            new_chars = new_text[self.last_char_count:]

            try:
                # 更新 Text 组件
                self.text_area.config(state=tk.NORMAL)
                self.text_area.insert(tk.END, new_chars)
                self.text_area.config(state=tk.DISABLED)

                # 强制同步布局计算
                self.window.update_idletasks()

                # 计算需要的窗口高度
                result = self.text_area.count('1.0', 'end', 'displaylines')
                current_lines = result[0] if result else 1
                needed_h = (current_lines * self.line_height) + HEIGHT_PADDING
                current_h = self.window.winfo_height()
                current_w = self.window.winfo_width()

                # 如果需要增长高度
                if needed_h > current_h:
                    curr_x = self.window.winfo_x()
                    curr_y = self.window.winfo_y()
                    self.window.geometry(f"{current_w}x{int(needed_h)}+{curr_x}+{curr_y}")
                    logger.debug(f"窗口高度调整: {current_h} -> {needed_h}")

                self.last_char_count = current_char_count
            except tk.TclError:
                # 窗口已被销毁，停止流式输出
                self.streaming = False
                logger.debug("窗口已销毁，停止流式输出")

    def _destroy_content_widget(self) -> None:
        """销毁 Text 组件"""
        if hasattr(self, 'text_area'):
            try:
                self.text_area.destroy()
            except tk.TclError:
                pass
