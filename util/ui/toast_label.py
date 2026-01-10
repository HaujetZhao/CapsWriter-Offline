"""
Toast Label 窗口模块

基于 Label 组件的浮动消息窗口（适合普通提示消息）
"""
import tkinter as tk
from tkinter import font
from util.ui.toast_base import ToastWindowBase, add_zero_width_for_chinese


class ToastWindowLabel(ToastWindowBase):
    """基于 Label 组件的浮动消息窗口（适合普通提示消息）"""

    def __init__(self, parent_root, text, font_size=14, font_family='', bg='#075077', fg='white',
                 duration=3000, initial_width=400, initial_height=0, streaming=False, stop_callback=None, markdown=False):
        """创建浮动消息窗口 (基于 Label)

        Args:
            parent_root: 父窗口
            text: 初始文本
            font_size: 字体大小
            font_family: 字体（空字符串表示使用系统默认）
            bg: 背景颜色
            fg: 字体颜色
            duration: 显示时长（毫秒）
            initial_width: 初始宽度
            initial_height: 初始高度（0 表示自动计算）
            streaming: 是否为流式模式（支持动态更新文本）
            stop_callback: 窗口关闭时的回调函数（用于停止 LLM 输出）
            markdown: 是否在完成后转换为 Markdown 渲染
        """
        # 初始化基类
        super().__init__(parent_root, text, font_size, font_family, bg, fg,
                         duration, initial_width, initial_height, streaming, stop_callback, markdown)

        # 计算实际宽度
        actual_width = self._calculate_actual_width()

        # 用于增量插入
        self.last_char_count = 0

        # 处理文本：在中文字符后添加零宽空格
        processed_text = add_zero_width_for_chinese(text) if text else text

        # 如果未指定字体，使用默认字体
        font_name = font_family if font_family else 'Microsoft YaHei'

        # 创建文字标签
        self.label = tk.Label(
            self.window,
            text=processed_text,
            font=(font_name, font_size),
            fg=fg,
            bg=bg,
            justify=tk.LEFT,
            wraplength=actual_width - 40,
            anchor='nw'
        )

        # 使用 side=tk.TOP 和 fill=tk.BOTH, expand=True
        self.label.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=15)

        # 初始化字符计数
        if text:
            self.last_char_count = len(text)

        # 强制更新布局以计算正确的高度
        self.window.update_idletasks()

        # 设置初始窗口位置（屏幕中央，根据实际内容高度）
        self._set_window_position(initial=True)
        
        # 如果是非流式模式且启用了 Markdown，立即转换
        if not streaming and markdown:
            # 强制更新窗口，确保位置已应用
            self.window.update()
            self._switch_to_markdown()

    def _set_window_position(self, initial=False):
        """设置窗口位置

        Args:
            initial: 是否为初始位置（屏幕中央，单行高度）
        """
        try:
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()

            # 计算初始宽度
            if 0 < self.initial_width < 1:
                calculated_width = int(screen_width * self.initial_width)
            else:
                calculated_width = self.initial_width

            # 获取 Label 的理想高度
            needed_h = self.label.winfo_reqheight() + 30

            # 如果设置了初始高度，使用初始高度；否则自动计算
            if self.initial_height > 0:
                window_height = max(self.initial_height, needed_h)
            else:
                window_height = needed_h

            # 限制最小高度
            window_height = max(window_height, 60)

            # 窗口宽度
            window_width = calculated_width

            if initial:
                # 初始位置：水平居中，顶部在屏幕中间
                x = (screen_width - window_width) // 2
                y = screen_height // 2  # 顶部在屏幕中间
            else:
                # 保持当前位置，只更新大小
                x = self.window.winfo_x()
                y = self.window.winfo_y()

            self.window.geometry(f'{window_width}x{window_height}+{x}+{y}')
        except:
            pass

    def update_text(self, new_text):
        """更新文本并丝滑向下扩展（增量插入模式）"""
        if not self.streaming:
            return

        # 计算新增的字符
        current_char_count = len(new_text)
        if current_char_count > self.last_char_count:
            # 保存完整文本
            self.full_text = new_text

            # 处理文本：在中文字符后添加零宽空格
            processed_text = add_zero_width_for_chinese(new_text)

            # Label 不支持增量插入，只能替换全部文本
            self.label.config(text=processed_text)

            # 强制同步布局计算，获取 Label 的理想高度
            self.window.update_idletasks()

            # 计算窗口需要的新高度
            needed_h = self.label.winfo_reqheight() + 30
            current_h = self.window.winfo_height()
            current_w = self.window.winfo_width()

            # 如果需要增长高度
            if needed_h > current_h:
                curr_x = self.window.winfo_x()
                curr_y = self.window.winfo_y()
                self.window.geometry(f"{current_w}x{int(needed_h)}+{curr_x}+{curr_y}")

            self.last_char_count = current_char_count

    def _destroy_content_widget(self):
        """销毁 Label 组件"""
        if hasattr(self, 'label'):
            self.label.destroy()
