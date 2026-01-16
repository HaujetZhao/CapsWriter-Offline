"""
Toast 窗口基础模块

提供 Toast 窗口的抽象基类和通用工具函数。
"""
import logging
import tkinter as tk
from tkinter import font
from typing import Optional, Callable, Union
from abc import ABC, abstractmethod
import ctypes

import markdown
from tkhtmlview import HTMLLabel

from .toast_constants import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_PADDING_X,
    DEFAULT_PADDING_Y,
    MIN_WINDOW_HEIGHT,
    MARKDOWN_MIN_HEIGHT,
    SCROLL_STEP,
    DESTROY_DELAY_MS,
)
from .toast_logger import get_toast_logger

# 配置日志（智能检测主程序配置）
logger = get_toast_logger(__name__)

# DPI 感知设置（只调用一次，避免重复调用）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except (OSError, AttributeError):
    # Windows 7 或不支持 DPI 感知的系统
    pass


# ============================================================
# 工具函数
# ============================================================

def add_zero_width_for_chinese(text: str) -> str:
    """在中文字符后添加零宽空格，强制 Label 按字符换行。
    
    这样可以避免中英混合时，Label 的单词边界换行导致不均匀。
    
    Args:
        text: 原始文本
        
    Returns:
        处理后的文本，每个中文字符后都添加了零宽空格
    """
    result = []
    for char in text:
        result.append(char)
        # 在中文字符（及全角字符）后插入零宽空格
        if ord(char) > 127:
            result.append('\u200B')  # 零宽空格
    return ''.join(result)


# ============================================================
# Toast 窗口抽象基类
# ============================================================

class ToastWindowBase(ABC):
    """Toast 窗口抽象基类
    
    提供窗口创建、拖动、鼠标事件处理、定时销毁等通用功能。
    子类需要实现 update_text 和 _destroy_content_widget 方法。
    
    Attributes:
        window: tkinter Toplevel 窗口对象
        streaming: 是否为流式输出模式
        markdown: 是否启用 Markdown 渲染
        full_text: 完整的文本内容
    """

    def __init__(
        self,
        parent_root: tk.Tk,
        text: str,
        font_size: int,
        font_family: str,
        bg: str,
        fg: str,
        duration: int,
        initial_width: Union[float, int],
        initial_height: int,
        streaming: bool,
        stop_callback: Optional[Callable[[], None]],
        markdown_enabled: bool,
        editable: bool = False
    ) -> None:
        """初始化 Toast 窗口基类
        
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
            markdown_enabled: 是否启用 Markdown 渲染
            editable: Markdown 渲染后是否允许编辑
        """
        # 保存基本属性
        self.parent_root = parent_root
        self.stop_callback = stop_callback
        self.streaming = streaming
        self.markdown = markdown_enabled
        self.editable = editable
        self.duration = duration
        self.initial_width = initial_width
        self.initial_height = initial_height
        
        # 状态标志
        self.pause = False
        self.mouse_inside = False
        self.timer_id: Optional[str] = None
        
        # 拖动位置
        self.x = 0
        self.y = 0
        
        # 保存完整文本和样式配置（用于 Markdown 渲染）
        self.full_text = text
        self.font_size = font_size
        self.font_family = font_family if font_family else DEFAULT_FONT_FAMILY
        self.bg = bg
        self.fg = fg
        
        # 创建窗口
        self.window = tk.Toplevel(parent_root)
        self.window.hang_on = False
        
        # 设置窗口属性
        self.window.overrideredirect(True)  # 无边框模式
        self.window.attributes('-topmost', True)  # 保持置顶
        self.window.configure(bg=bg)
        self.window.resizable(True, True)
        self.window.pack_propagate(False)
        
        # 绑定通用事件
        self._bind_common_events()
        
        # 显示窗口
        self.window.deiconify()
        
        # 如果不是流式模式，设置定时销毁
        if not self.streaming:
            self._start_destroy_timer()

    def _bind_common_events(self) -> None:
        """绑定通用事件（拖动、鼠标进入/离开、滚轮、ESC、复制）"""
        self.window.bind('<ButtonPress-1>', self._on_drag_start)
        self.window.bind('<ButtonRelease-1>', self._on_drag_stop)
        self.window.bind('<B1-Motion>', self._on_drag_motion)
        self.window.bind('<Escape>', self._destroy_window)
        self.window.bind('<Enter>', self._on_mouse_enter)
        self.window.bind('<Leave>', self._on_mouse_leave)
        self.window.bind('<MouseWheel>', self._on_mouse_wheel)
        self.window.bind('<Button-4>', self._on_mouse_wheel)  # Linux 向上滚动
        self.window.bind('<Button-5>', self._on_mouse_wheel)  # Linux 向下滚动
        self.window.bind('<Control-c>', self._on_copy)        # Ctrl+C 复制

    def _calculate_actual_width(self) -> int:
        """计算实际窗口宽度
        
        Returns:
            窗口宽度（像素）
        """
        screen_width = self.window.winfo_screenwidth()
        if 0 < self.initial_width < 1:
            # 0-1 之间的小数，使用屏幕宽度的比例
            return int(screen_width * self.initial_width)
        else:
            # 绝对值（像素）
            return int(self.initial_width)

    @staticmethod
    def _invert_color(hex_color: str) -> str:
        """计算十六进制颜色的反色
        
        Args:
            hex_color: 十六进制颜色值（如 '#075077'）
            
        Returns:
            反色的十六进制颜色值
        """
        # 去掉 # 前缀
        hex_color = hex_color.lstrip('#')
        # 解析 RGB 值
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        # 计算反色
        inv_r = 255 - r
        inv_g = 255 - g
        inv_b = 255 - b
        return f"#{inv_r:02x}{inv_g:02x}{inv_b:02x}"

    # --------------------------------------------------------
    # 鼠标事件处理
    # --------------------------------------------------------

    def _on_mouse_enter(self, event: tk.Event) -> None:
        """鼠标进入窗口，暂停自动关闭计时器"""
        self.mouse_inside = True
        if self.timer_id:
            self.window.after_cancel(self.timer_id)
            self.timer_id = None

    def _on_mouse_leave(self, event: tk.Event) -> None:
        """鼠标离开窗口，恢复自动关闭计时器"""
        self.mouse_inside = False
        if not self.streaming:
            self._start_destroy_timer()

    def _on_drag_start(self, event: tk.Event) -> None:
        """拖动开始"""
        self.pause = True
        self.x = event.x
        self.y = event.y

    def _on_drag_stop(self, event: tk.Event) -> None:
        """拖动结束"""
        self.pause = False

    def _on_drag_motion(self, event: tk.Event) -> None:
        """拖动中，更新窗口位置"""
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.window.winfo_x() + deltax
        y = self.window.winfo_y() + deltay
        self.window.geometry(f"+{x}+{y}")

    def _on_mouse_wheel(self, event: tk.Event) -> str:
        """滚轮调整窗口垂直位置

        允许在屏幕中线到屏幕底边之间滚动：
        - 窗口底部超出屏幕时，可以向上滚动（减小 y）
        - 窗口顶部超过屏幕中线时，可以向下滚动（增加 y）

        Returns:
            "break" 阻止事件继续传播
        """
        try:
            self.window.update_idletasks()
            current_y = self.window.winfo_y()
            window_height = self.window.winfo_height()
            screen_height = self.window.winfo_screenheight()
            screen_middle = screen_height // 2

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
            # top_limit: 窗口在最低位置时的 y 坐标（底部刚好在屏幕底边）
            # bottom_limit: 窗口在最高位置时的 y 坐标（顶部在屏幕中线）
            top_limit = screen_height - window_height
            bottom_limit = screen_middle

            # 检查是否允许滚动
            window_bottom = current_y + window_height
            can_scroll_up = window_bottom > screen_height  # 底部超出屏幕，可向上滚动
            can_scroll_down = current_y < screen_middle    # 顶部在中线之上，可向下滚动

            # 根据滚动方向和位置判断是否执行滚动
            if is_scroll_up and can_scroll_up:
                # 向上滚动（减小 y）
                target_y = max(current_y - SCROLL_STEP, top_limit)
                if target_y != current_y:
                    self.window.geometry(f"+{self.window.winfo_x()}+{int(target_y)}")
            elif not is_scroll_up and can_scroll_down:
                # 向下滚动（增加 y）
                target_y = min(current_y + SCROLL_STEP, bottom_limit)
                if target_y != current_y:
                    self.window.geometry(f"+{self.window.winfo_x()}+{int(target_y)}")

            return "break"
        except tk.TclError as e:
            logger.warning(f"滚动事件处理失败: {e}")
            return "break"

    def _on_copy(self, _event: tk.Event) -> str:
        """复制文本到剪贴板
        
        优先复制选中的文本（如果有），否则复制全部内容。

        Args:
            _event: 事件对象（未使用）

        Returns:
            "break" 阻止事件继续传播
        """
        try:
            text_to_copy = None
            
            # 如果有 md_label，检查是否有选中文本
            if hasattr(self, 'md_label') and self.md_label:
                try:
                    # Text 组件使用 tag_ranges("sel") 检查选区
                    sel_ranges = self.md_label.tag_ranges("sel")
                    if sel_ranges:
                        # 有选中文本，获取选中内容
                        text_to_copy = self.md_label.get(sel_ranges[0], sel_ranges[1])
                        logger.info("已复制选中的文本到剪贴板")
                except tk.TclError:
                    pass  # 没有选区或其他错误
            
            # 如果没有选中文本，复制全部内容
            if text_to_copy is None:
                text_to_copy = self.full_text
                logger.info("已复制 Toast 全部内容到剪贴板")
            
            self.window.clipboard_clear()
            self.window.clipboard_append(text_to_copy)
        except Exception as e:
            logger.error(f"复制到剪贴板失败: {e}")
        return "break"

    # --------------------------------------------------------
    # 窗口销毁
    # --------------------------------------------------------

    def _start_destroy_timer(self) -> None:
        """启动自动销毁计时器"""
        if self.timer_id:
            self.window.after_cancel(self.timer_id)
        self.timer_id = self.window.after(self.duration, self._destroy_window)

    def _destroy_window(self, event: Optional[tk.Event] = None) -> None:
        """销毁窗口
        
        Args:
            event: 事件对象（ESC 键触发时传入）
        """
        try:
            # 调用停止回调（用于停止 LLM 输出）
            if self.stop_callback:
                try:
                    self.stop_callback()
                except Exception as e:
                    logger.warning(f"停止回调执行失败: {e}")

            if self.pause:
                # 如果窗口被暂停（拖动），延迟销毁
                if self.timer_id:
                    self.window.after_cancel(self.timer_id)
                self.timer_id = self.window.after(DESTROY_DELAY_MS, self._destroy_window)
            else:
                if self.timer_id:
                    self.window.after_cancel(self.timer_id)
                    self.timer_id = None
                self.window.destroy()
        except tk.TclError:
            # 窗口可能已被销毁
            pass

    # --------------------------------------------------------
    # Markdown 渲染
    # --------------------------------------------------------

    def _calculate_height_coefficient(self, content_height: int) -> float:
        """根据内容高度计算边距系数

        使用指数衰减曲线：f(x) = 0.5 * e^(-0.003x) + 1.1
        当内容高度较小时，需要更大的边距系数以确保内容完全显示。
        当内容高度较大时，系数逐渐接近极限值 1.1。

        Args:
            content_height: 内容高度（像素）

        Returns:
            边距系数，范围 (1.1, 1.6]
            - x=50: f(50) ≈ 1.6
            - x=300: f(300) ≈ 1.3
            - x=1500: f(1500) ≈ 1.15
            - x→∞: f(x) → 1.1
        """
        import math

        if content_height <= 50:
            return 1.6

        # 指数衰减曲线：f(x) = 0.5 * e^(-0.003x) + 1.1
        coefficient = 0.5 * math.exp(-0.003 * content_height) + 1.1

        # 确保系数在合理范围内
        return max(coefficient, 1.1)

    def _switch_to_markdown(self) -> None:
        """将内容组件切换为 Markdown 渲染"""
        try:
            # 保存当前位置
            cx, cy = self.window.winfo_x(), self.window.winfo_y()

            # 转换 Markdown 为 HTML
            raw_html = markdown.markdown(
                self.full_text,
                extensions=['extra', 'nl2br']
            )

            # 包装为完整的 HTML（不设置 padding，让 HTMLLabel 组件处理）
            full_html = f"""
            <div style="background-color:{self.bg}; color:{self.fg};
                        font-family:{self.font_family}; font-size:{self.font_size}px;">
                {raw_html}
            </div>
            """

            # 先创建 HTMLLabel 组件，覆盖在原有组件上面
            self.md_label = HTMLLabel(
                self.window,
                html=full_html,
                wrap="char",
                background=self.bg,
                padx=DEFAULT_PADDING_X,
                pady=DEFAULT_PADDING_Y
            )
            self.md_label.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            
            # 根据 editable 参数设置是否可编辑
            # DISABLED 状态下仍可选择文字，但无法编辑
            # NORMAL 状态下可以选择和编辑文字
            if self.editable:
                self.md_label.config(state=tk.NORMAL)
                
                # 设置光标颜色为背景色的反色
                cursor_color = self._invert_color(self.bg)
                self.md_label.config(insertbackground=cursor_color, insertwidth=2)
            # 否则保持 HTMLLabel 默认的 DISABLED 状态
            
            # 设置选中文字的高亮样式（DISABLED 状态下默认选中样式不可见）
            select_bg = "#3399ff"
            select_fg = "white"
            self.md_label.config(selectbackground=select_bg, selectforeground=select_fg)
            
            # HTMLLabel 使用 tag 设置文字样式，需要为所有 tag 也设置选中样式
            for tag in self.md_label.tag_names():
                self.md_label.tag_config(tag, selectbackground=select_bg, selectforeground=select_fg)

            # 现在 Markdown 组件已经显示，再销毁原有组件
            self._destroy_content_widget()

            # 多次更新以确保布局完全计算
            self.window.update()
            self.window.update_idletasks()

            # 使用 fit_height() 方法获取真实的内容高度
            # 这会自动调整标签高度以适应所有内容
            self.md_label.fit_height()
            self.window.update()
            self.window.update_idletasks()

            # 测量 fit_height() 后的高度
            height_after = self.md_label.winfo_height()
            reqheight_after = self.md_label.winfo_reqheight()

            # 使用较大的高度值（reqheight 可能更准确）
            content_height = max(height_after, reqheight_after)

            # 计算新的窗口高度和宽度
            # 使用动态系数确保内容完全显示
            margin_coefficient = self._calculate_height_coefficient(content_height)
            final_h = max(int(content_height * margin_coefficient), MARKDOWN_MIN_HEIGHT)
            final_w = self._calculate_actual_width()

            self.window.geometry(f"{final_w}x{int(final_h)}+{cx}+{cy}")

            # 更新布局后再次测量
            self.window.update()
            self.window.update_idletasks()

            logger.info(f"Markdown 窗口: {final_w}x{final_h} (内容: {content_height}px, 系数: {margin_coefficient:.2f})")

        except Exception as e:
            logger.error(f"Markdown 转换失败: {e}")
            self._destroy_window()

    # --------------------------------------------------------
    # 抽象方法（子类必须实现）
    # --------------------------------------------------------

    @abstractmethod
    def update_text(self, new_text: str) -> None:
        """更新文本内容（由子类实现）
        
        Args:
            new_text: 新的完整文本内容
        """
        pass

    @abstractmethod
    def _destroy_content_widget(self) -> None:
        """销毁内容组件（由子类实现）"""
        pass

    # --------------------------------------------------------
    # 流式输出完成
    # --------------------------------------------------------

    def finish(self) -> None:
        """完成流式输出

        标记流式输出结束，如果启用了 Markdown 则转换渲染，
        然后启动自动销毁计时器。
        """
        if self.streaming:
            self.streaming = False

            # 如果启用了 Markdown，转换渲染
            if self.markdown:
                self._switch_to_markdown()

            # 只有当鼠标不在窗口内时才启动计时器
            if not self.mouse_inside:
                self._start_destroy_timer()
