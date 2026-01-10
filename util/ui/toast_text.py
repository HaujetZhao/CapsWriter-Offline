"""
Toast Text 窗口模块

基于 Text 组件的浮动消息窗口（适合流式输出）
"""
import tkinter as tk
from tkinter import font
from util.ui.toast_base import ToastWindowBase


class ToastWindowText(ToastWindowBase):
    """基于 Text 组件的浮动消息窗口（适合流式输出）"""

    def __init__(self, parent_root, text, font_size=14, font_family='', bg='#075077', fg='white',
                 duration=3000, initial_width=400, initial_height=0, streaming=False, stop_callback=None, markdown=False):
        """创建浮动消息窗口

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

        # 创建字体对象用于计算行高
        font_name = self.font_family if self.font_family else 'Microsoft YaHei'
        self.my_font = font.Font(family=font_name, size=self.font_size)
        self.line_height = self.my_font.metrics('linespace')
        self.last_char_count = 0

        # 创建文本框
        # 流式模式：预设较大高度(50行)，防止内容多时自动滚动
        # 非流式模式：设置较小高度(1行)，通过 geometry 控制实际大小
        text_height = 50 if streaming else 1
        
        self.text_area = tk.Text(
            self.window,
            font=self.my_font,
            fg=self.fg,
            bg=self.bg,
            padx=20,
            pady=15,
            borderwidth=0,
            highlightthickness=0,
            wrap=tk.CHAR,  # 使用 CHAR 自动换行
            insertofftime=0,
            state=tk.DISABLED,
            cursor="arrow",
            height=text_height
        )

        # 锚定在左上角 (nw)，使用 fill=X 水平填充窗口
        # 不使用 expand=True，防止它试图填满变大的窗口而导致重心偏移
        self.text_area.pack(side=tk.TOP, anchor='nw', fill=tk.X)

        # 初始化时插入初始文本
        if text:
            self.text_area.config(state=tk.NORMAL)
            self.text_area.insert(tk.END, text)
            self.text_area.config(state=tk.DISABLED)
            self.last_char_count = len(text)
            
            # 如果是非流式模式，需要先设置窗口宽度，再计算实际行数
            if not streaming:
                # 先计算并设置窗口宽度
                screen_width = self.window.winfo_screenwidth()
                if 0 < self.initial_width < 1:
                    calculated_width = int(screen_width * self.initial_width)
                else:
                    calculated_width = self.initial_width
                
                # 设置临时窗口大小（只设置宽度，高度暂时设为100）
                screen_height = self.window.winfo_screenheight()
                x = (screen_width - calculated_width) // 2
                y = (screen_height - 100) // 2
                self.window.geometry(f'{calculated_width}x100+{x}+{y}')
                
                # 强制更新，让 Text 组件按照新宽度重新计算换行
                self.window.update_idletasks()
                
                # 现在计算实际行数
                result = self.text_area.count('1.0', 'end', 'displaylines')
                actual_lines = result[0] if result else 1
                self.text_area.config(height=actual_lines)

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

            # 更新窗口以确保获取正确的尺寸
            self.window.update_idletasks()

            # 计算初始宽度（支持比例或绝对值）
            if 0 < self.initial_width < 1:
                # 0-1 之间的小数，使用屏幕宽度的比例
                calculated_width = int(screen_width * self.initial_width)
            else:
                # 绝对值（像素）
                calculated_width = self.initial_width

            # 获取实际渲染的行数
            result = self.text_area.count('1.0', 'end', 'displaylines')
            current_lines = result[0] if result else 1

            # 精确计算：行数 * 行高 + 上下 Padding 补偿
            needed_h = (current_lines * self.line_height) + 40

            # 如果设置了初始高度，使用初始高度；否则自动计算
            if self.initial_height > 0:
                window_height = max(self.initial_height, needed_h)
            else:
                window_height = needed_h

            # 限制最小高度
            window_height = max(window_height, 60)  # 最小高度 60px

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

            self.window.geometry(f'{window_width}x{int(window_height)}+{x}+{y}')
        except:
            pass

    def update_text(self, new_text):
        """更新文本内容（增量插入模式）"""
        if not self.streaming:
            return

        # 检查窗口是否还存在（防止窗口已关闭时继续更新）
        try:
            if not self.window.winfo_exists():
                self.streaming = False
                return
        except:
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
                needed_h = (current_lines * self.line_height) + 40
                current_h = self.window.winfo_height()
                current_w = self.window.winfo_width()

                # 如果需要增长高度
                if needed_h > current_h:
                    curr_x = self.window.winfo_x()
                    curr_y = self.window.winfo_y()
                    self.window.geometry(f"{current_w}x{int(needed_h)}+{curr_x}+{curr_y}")

                self.last_char_count = current_char_count
            except tk.TclError:
                # 窗口已被销毁，停止流式输出
                self.streaming = False
            except Exception:
                # 其他错误，也停止流式输出
                self.streaming = False

    def _destroy_content_widget(self):
        """销毁 Text 组件"""
        if hasattr(self, 'text_area'):
            self.text_area.destroy()
