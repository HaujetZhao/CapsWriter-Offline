"""
Toast 窗口基础模块

提供基础功能函数和抽象基类
"""
import tkinter as tk
from tkinter import font
import ctypes
import markdown
from tkhtmlview import HTMLLabel
from abc import ABC, abstractmethod

# DPI 感知设置
ctypes.windll.shcore.SetProcessDpiAwareness(1)


def add_zero_width_for_chinese(text: str) -> str:
    """
    在中文字符后添加零宽空格，强制 Label 按字符换行
    这样可以避免中英混合时，Label 的单词边界换行导致不均匀

    Args:
        text: 原始文本

    Returns:
        处理后的文本
    """
    result = []
    for char in text:
        result.append(char)
        # 在中文字符（及全角字符）后插入零宽空格
        if ord(char) > 127:
            result.append('\u200B')  # 零宽空格
    return ''.join(result)


class ToastWindowBase(ABC):
    """Toast 窗口抽象基类"""

    def __init__(self, parent_root, text, font_size, font_family, bg, fg,
                 duration, initial_width, initial_height, streaming, stop_callback, markdown):
        """初始化基础属性"""
        self.parent_root = parent_root
        self.stop_callback = stop_callback
        self.window = tk.Toplevel(parent_root)
        self.window.hang_on = False
        self.streaming = streaming
        self.pause = False
        self.duration = duration
        self.initial_width = initial_width
        self.initial_height = initial_height
        self.timer_id = None
        self.mouse_inside = False  # 鼠标是否在窗口内
        self.markdown = markdown  # 是否转换为 Markdown 渲染

        # 保存完整文本和样式配置（用于 Markdown 渲染）
        self.full_text = text
        self.font_size = font_size
        self.font_family = font_family if font_family else 'Microsoft YaHei UI'
        self.bg = bg
        self.fg = fg

        # 设置窗口属性
        self.window.overrideredirect(True)  # 无边框模式
        self.window.attributes('-topmost', True)  # 保持置顶
        self.window.configure(bg=bg)
        self.window.resizable(True, True)  # 允许调整大小
        self.window.pack_propagate(False)

        # 绑定通用事件
        self._bind_common_events()

        # 显示窗口
        self.window.deiconify()

        # 如果不是流式模式，设置定时销毁
        if not self.streaming:
            self._start_destroy_timer()

    def _bind_common_events(self):
        """绑定通用事件（拖动、鼠标进入/离开、滚轮、ESC）"""
        self.window.bind('<ButtonPress-1>', self._on_drag_start)
        self.window.bind('<ButtonRelease-1>', self._on_drag_stop)
        self.window.bind('<B1-Motion>', self._on_drag_motion)
        self.window.bind('<Escape>', self._destroy_window)
        self.window.bind('<Enter>', self._on_mouse_enter)
        self.window.bind('<Leave>', self._on_mouse_leave)
        self.window.bind('<MouseWheel>', self._on_mouse_wheel)
        self.window.bind('<Button-4>', self._on_mouse_wheel)  # Linux 向上滚动
        self.window.bind('<Button-5>', self._on_mouse_wheel)  # Linux 向下滚动

    def _calculate_actual_width(self):
        """计算实际宽度（支持比例）"""
        screen_width = self.window.winfo_screenwidth()
        if 0 < self.initial_width < 1:
            # 0-1 之间的小数，使用屏幕宽度的比例
            return int(screen_width * self.initial_width)
        else:
            # 绝对值（像素）
            return self.initial_width

    def _on_mouse_enter(self, event):
        """鼠标进入窗口"""
        self.mouse_inside = True
        # 取消销毁计时器
        if self.timer_id:
            self.window.after_cancel(self.timer_id)
            self.timer_id = None

    def _on_mouse_leave(self, event):
        """鼠标离开窗口"""
        self.mouse_inside = False
        # 如果流式输出已完成，启动销毁计时器
        if not self.streaming:
            self._start_destroy_timer()

    def _on_drag_start(self, event):
        """拖动开始"""
        self.pause = True
        self.x = event.x
        self.y = event.y

    def _on_drag_stop(self, event):
        """拖动结束"""
        self.pause = False

    def _on_drag_motion(self, event):
        """拖动中"""
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.window.winfo_x() + deltax
        y = self.window.winfo_y() + deltay
        self.window.geometry(f"+{x}+{y}")

    def _on_mouse_wheel(self, event):
        """滚轮调整窗口垂直位置，限制在屏幕中线到底边之间"""
        try:
            self.window.update_idletasks()
            current_y = self.window.winfo_y()
            window_height = self.window.winfo_height()
            screen_height = self.window.winfo_screenheight()
            screen_middle = screen_height // 2

            # 检查窗口高度是否足以进行滚动
            if window_height <= (screen_height - screen_middle):
                return "break"

            # 判定滚动方向
            delta = getattr(event, 'delta', 0)
            num = getattr(event, 'num', 0)

            if delta:
                is_scroll_up = (delta < 0)
            elif num:
                is_scroll_up = (num != 4)
            else:
                return "break"

            # 计算边界
            top_limit = screen_height - window_height
            bottom_limit = screen_middle

            step = 60
            if is_scroll_up:
                target_y = max(current_y - step, top_limit)
            else:
                target_y = min(current_y + step, bottom_limit)

            if target_y != current_y:
                self.window.geometry(f"+{self.window.winfo_x()}+{int(target_y)}")

            return "break"
        except Exception as e:
            print(f"滚动异常: {e}")

    def _start_destroy_timer(self):
        """启动销毁计时器"""
        if self.timer_id:
            self.window.after_cancel(self.timer_id)
        self.timer_id = self.window.after(self.duration, self._destroy_window)

    def _destroy_window(self, event=None):
        """销毁窗口"""
        try:
            # 调用停止回调（用于停止 LLM 输出）
            if hasattr(self, 'stop_callback') and self.stop_callback:
                self.stop_callback()

            if self.pause:
                # 如果窗口被暂停（拖动），延迟销毁
                if self.timer_id:
                    self.window.after_cancel(self.timer_id)
                self.timer_id = self.window.after(100, self._destroy_window)
            else:
                if self.timer_id:
                    self.window.after_cancel(self.timer_id)
                self.window.destroy()
        except:
            pass

    def _switch_to_markdown(self):
        """将组件切换为 Markdown 渲染"""
        try:
            # 保存当前位置
            cx, cy = self.window.winfo_x(), self.window.winfo_y()

            # 销毁原有组件（由子类实现）
            self._destroy_content_widget()

            # 转换 Markdown 为 HTML
            raw_html = markdown.markdown(self.full_text, extensions=['extra', 'nl2br'])

            # 包装为完整的 HTML，使用用户配置的字体和颜色
            full_html = f"""
            <div style="background-color:{self.bg}; color:{self.fg}; font-family:{self.font_family}; font-size:{self.font_size}px; padding: 15px 20px;">
                {raw_html}
            </div>
            """

            # 创建 HTMLLabel 组件
            self.md_label = HTMLLabel(
                self.window,
                html=full_html,
                background=self.bg,
                padx=20,
                pady=15,
                state=tk.DISABLED  # 禁用编辑和滚动
            )
            self.md_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            # 多次更新以确保布局完全计算
            self.window.update()
            self.window.update_idletasks()

            # 获取内部渲染内容的实际高度
            try:
                # 尝试获取内部文本组件的高度
                internal_widget = self.md_label.winfo_children()[0] if self.md_label.winfo_children() else None
                if internal_widget:
                    content_height = internal_widget.winfo_reqheight()
                else:
                    content_height = self.md_label.winfo_reqheight()
            except:
                content_height = self.md_label.winfo_reqheight()

            # 计算新的窗口高度和宽度（增加足够的边距）
            final_h = content_height + 120  # 增加更多边距
            final_w = self._calculate_actual_width()

            # 确保最小高度
            final_h = max(final_h, 120)

            self.window.geometry(f"{final_w}x{int(final_h)}+{cx}+{cy}")

        except Exception as e:
            print(f"Markdown 转换错误: {e}")
            # 如果转换失败，销毁窗口
            self._destroy_window()

    @abstractmethod
    def update_text(self, new_text):
        """更新文本内容（由子类实现）"""
        pass

    @abstractmethod
    def _destroy_content_widget(self):
        """销毁内容组件（由子类实现）"""
        pass

    def finish(self):
        """完成流式输出，转为 Markdown 渲染并启动销毁计时器"""
        if self.streaming:
            self.streaming = False

            # 如果启用了 Markdown，转换渲染
            if self.markdown:
                self._switch_to_markdown()

            # 只有当鼠标不在窗口内时才启动计时器
            if not self.mouse_inside:
                self._start_destroy_timer()
