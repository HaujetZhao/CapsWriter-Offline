import tkinter as tk
from tkinter import font
import ctypes

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


class ToastWindowText:
    """基于 Text 组件的浮动消息窗口（适合流式输出）"""
    def __init__(self, parent_root, text, font_size=14, font_family='', bg='#075077', fg='white',
                 duration=3000, initial_width=400, initial_height=0, streaming=False, stop_callback=None):
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
        """
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

        # 计算实际宽度（支持比例）
        screen_width = self.window.winfo_screenwidth()
        if 0 < self.initial_width < 1:
            # 0-1 之间的小数，使用屏幕宽度的比例
            actual_width = int(screen_width * self.initial_width)
        else:
            # 绝对值（像素）
            actual_width = self.initial_width

        # 设置窗口属性
        self.window.overrideredirect(True)  # 无边框模式
        self.window.attributes('-topmost', True)  # 保持置顶
        self.window.configure(bg=bg)
        # self.window.title('')  # 无边框窗口不需要标题栏
        self.window.resizable(True, True)  # 允许调整大小


        # 💡 关键改动 1: 禁用自动传播，完全由代码控制窗口尺寸
        self.window.pack_propagate(False)

        # 创建字体对象用于计算行高
        # 如果未指定字体，使用默认字体
        font_name = font_family if font_family else 'Microsoft YaHei'
        self.my_font = font.Font(family=font_name, size=font_size)
        self.line_height = self.my_font.metrics('linespace')
        self.last_char_count = 0

        # 创建文本框
        self.text_area = tk.Text(
            self.window,
            font=self.my_font,
            fg=fg,
            bg=bg,
            padx=20,
            pady=15,
            borderwidth=0,
            highlightthickness=0,
            wrap=tk.CHAR,  # 使用 CHAR 自动换行
            insertofftime=0,
            state=tk.DISABLED,
            cursor="arrow",
            # 预设一个较大的高度（行数），防止它因为内容多而自动滚动
            height=50
        )

        # 锚定在左上角 (nw)
        # 不使用 expand=True，防止它试图填满变大的窗口而导致重心偏移
        self.text_area.pack(side=tk.TOP, anchor='nw')

        # 设置初始窗口位置（屏幕中央，单行高度）
        self._set_window_position(initial=True)

        # 初始化时插入初始文本
        if text:
            self.text_area.config(state=tk.NORMAL)
            self.text_area.insert(tk.END, text)
            self.text_area.config(state=tk.DISABLED)
            self.last_char_count = len(text)

        # 绑定可拖动
        self.window.bind('<ButtonPress-1>', self._on_drag_start)
        self.window.bind('<ButtonRelease-1>', self._on_drag_stop)
        self.window.bind('<B1-Motion>', self._on_drag_motion)
        self.window.bind('<Escape>', self._destroy_window)

        # 绑定鼠标进入/离开事件
        self.window.bind('<Enter>', self._on_mouse_enter)
        self.window.bind('<Leave>', self._on_mouse_leave)

        # 绑定滚轮事件（Windows 和 Linux 使用 MouseWheel，macOS 使用 MouseWheel/Button-4/5）
        self.window.bind('<MouseWheel>', self._on_mouse_wheel)
        self.window.bind('<Button-4>', self._on_mouse_wheel)  # Linux 向上滚动
        self.window.bind('<Button-5>', self._on_mouse_wheel)  # Linux 向下滚动
        # 显示窗口
        self.window.deiconify()

        # 如果不是流式模式，设置定时销毁
        if not self.streaming:
            self._start_destroy_timer()

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
                # 初始位置：屏幕中央
                x = (screen_width - window_width) // 2
                y = (screen_height - window_height) // 2
            else:
                # 保持当前位置，只更新大小
                x = self.window.winfo_x()
                y = self.window.winfo_y()

            self.window.geometry(f'{window_width}x{int(window_height)}+{x}+{y}')
        except:
            pass

    def _on_mouse_wheel(self, event):
        """滚轮调整窗口垂直位置，限制在屏幕中线到底边之间"""
        try:
            self.window.update_idletasks()
            current_y = self.window.winfo_y()
            window_height = self.window.winfo_height()
            screen_height = self.window.winfo_screenheight()
            screen_middle = screen_height // 2

            # --- 关键修正：检查窗口高度是否足以进行滚动 ---
            # 如果窗口高度太短，不足以同时覆盖中线和底边，则直接返回，不处理滚动
            if window_height <= (screen_height - screen_middle):
                return "break"

            # 判定滚动方向（delta: Windows/macOS, num: Linux）
            delta = getattr(event, 'delta', 0)
            num = getattr(event, 'num', 0)

            if delta:
                is_scroll_up = (delta < 0)  # 向上滚动，窗口上移
            elif num:
                is_scroll_up = (num != 4)
            else:
                return "break"

            # 计算边界
            # top_limit: 窗口向上移动的极限（下边缘贴底边）
            top_limit = screen_height - window_height
            # bottom_limit: 窗口向下移动的极限（上边缘贴中线）
            bottom_limit = screen_middle

            # 计算目标位置
            step = 60
            if is_scroll_up:
                # 向上滚动，y 减小，但不能小于 top_limit
                target_y = max(current_y - step, top_limit)
            else:
                # 向下滚动，y 增大，但不能大于 bottom_limit
                target_y = min(current_y + step, bottom_limit)

            # 更新位置
            if target_y != current_y:
                self.window.geometry(f"+{self.window.winfo_x()}+{int(target_y)}")

            return "break"
        except Exception as e:
            print(f"滚动异常: {e}")

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
            # 获取新增部分
            new_chars = new_text[self.last_char_count:]

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

    def finish(self):
        """完成流式输出，启动销毁计时器"""
        if self.streaming:
            self.streaming = False
            # 只有当鼠标不在窗口内时才启动计时器
            if not self.mouse_inside:
                self._start_destroy_timer()

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


    def _start_destroy_timer(self):
        """启动销毁计时器"""
        if self.timer_id:
            self.window.after_cancel(self.timer_id)
        self.timer_id = self.window.after(self.duration, self._destroy_window)

    def _on_drag_start(self, event):
        self.pause = True
        self.x = event.x
        self.y = event.y

    def _on_drag_stop(self, event):
        self.pause = False

    def _on_drag_motion(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.window.winfo_x() + deltax
        y = self.window.winfo_y() + deltay
        self.window.geometry(f"+{x}+{y}")

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
                self.window.destroy()  # 销毁窗口
        except:
            pass


class ToastWindowLabel:
    """基于 Label 组件的浮动消息窗口（适合普通提示消息）"""
    def __init__(self, parent_root, text, font_size=14, font_family='', bg='#075077', fg='white',
                 duration=3000, initial_width=400, initial_height=0, streaming=False, stop_callback=None):
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
        """
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
        self.last_char_count = 0  # 用于增量插入

        # 计算实际宽度（支持比例）
        screen_width = self.window.winfo_screenwidth()
        if 0 < self.initial_width < 1:
            # 0-1 之间的小数，使用屏幕宽度的比例
            actual_width = int(screen_width * self.initial_width)
        else:
            # 绝对值（像素）
            actual_width = self.initial_width

        # 设置窗口属性
        self.window.overrideredirect(True)  # 无边框模式
        self.window.attributes('-topmost', True)  # 保持置顶
        self.window.configure(bg=bg)
        # self.window.title('')  # 无边框窗口不需要标题栏
        self.window.resizable(True, True)  # 允许调整大小

        # 绑定可拖动
        self.window.bind('<ButtonPress-1>', self._on_drag_start)
        self.window.bind('<ButtonRelease-1>', self._on_drag_stop)
        self.window.bind('<B1-Motion>', self._on_drag_motion)
        self.window.bind('<Escape>', self._destroy_window)

        # 绑定鼠标进入/离开事件
        self.window.bind('<Enter>', self._on_mouse_enter)
        self.window.bind('<Leave>', self._on_mouse_leave)

        # 绑定滚轮事件（Windows 和 Linux 使用 MouseWheel，macOS 使用 MouseWheel/Button-4/5）
        self.window.bind('<MouseWheel>', self._on_mouse_wheel)
        self.window.bind('<Button-4>', self._on_mouse_wheel)  # Linux 向上滚动
        self.window.bind('<Button-5>', self._on_mouse_wheel)  # Linux 向下滚动

        # 💡 关键改动 1: 禁用自动传播，完全由代码控制窗口尺寸
        self.window.pack_propagate(False)

        # 处理文本：在中文字符后添加零宽空格，强制按字符换行
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
            wraplength=actual_width - 40,  # 使用 wraplength 控制换行
            anchor='nw'
        )
        # 💡 关键改动 3: 使用 side=tk.TOP 和 fill=tk.BOTH, expand=True
        # 配合 pack_propagate(False) 和 anchor='nw'，这样文字换行时，只会向下长，顶部永远钉在窗口 (20, 15) 的位置
        self.label.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=15)

        # 设置初始窗口位置（屏幕中央，单行高度）
        self._set_window_position(initial=True)

        # 初始化字符计数
        if text:
            self.last_char_count = len(text)

        # 显示窗口
        self.window.deiconify()

        # 如果不是流式模式，设置定时销毁
        if not self.streaming:
            self._start_destroy_timer()

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

            # 获取标签的实际大小
            label_width = self.label.winfo_reqwidth()
            label_height = self.label.winfo_reqheight()

            # 计算初始宽度（支持比例或绝对值）
            if 0 < self.initial_width < 1:
                # 0-1 之间的小数，使用屏幕宽度的比例
                calculated_width = int(screen_width * self.initial_width)
            else:
                # 绝对值（像素）
                calculated_width = self.initial_width

            # 加上 padding
            window_width = max(calculated_width, label_width + 40)  # 左右各 20px padding

            # 如果设置了初始高度，使用初始高度；否则自动计算
            if self.initial_height > 0:
                window_height = max(self.initial_height, label_height + 30)
            else:
                window_height = label_height + 30  # 上下各 15px padding

            # 限制最小高度
            window_height = max(window_height, 60)  # 最小高度 60px

            if initial:
                # 初始位置：屏幕中央
                x = (screen_width - window_width) // 2
                y = (screen_height - window_height) // 2
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
            # 处理文本：在中文字符后添加零宽空格
            processed_text = add_zero_width_for_chinese(new_text)

            # Label 不支持增量插入，只能替换全部文本
            # 但通过记录字符数，可以确保只在文本增长时才更新
            self.label.config(text=processed_text)

            # 2. 强制同步布局计算，获取 Label 的「理想高度」
            self.window.update_idletasks()

            # 3. 计算窗口需要的新高度 (Label 高度 + 上下 padding)
            needed_h = self.label.winfo_reqheight() + 30
            current_h = self.window.winfo_height()
            current_w = self.window.winfo_width()

            # 4. 如果需要增长高度
            if needed_h > current_h:
                # 获取当前位置坐标，确保只向下长，不动 (x, y)
                curr_x = self.window.winfo_x()
                curr_y = self.window.winfo_y()

                # 直接更新几何尺寸。由于设置了 anchor='nw'，
                # 窗口变大时，上方的文字会保持不动，只有下方空白区域变多
                self.window.geometry(f"{current_w}x{int(needed_h)}+{curr_x}+{curr_y}")

            self.last_char_count = current_char_count

    def finish(self):
        """完成流式输出，启动销毁计时器"""
        if self.streaming:
            self.streaming = False
            # 只有当鼠标不在窗口内时才启动计时器
            if not self.mouse_inside:
                self._start_destroy_timer()

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

    def _on_mouse_wheel(self, event):
        """滚轮调整窗口垂直位置，限制在屏幕中线到底边之间"""
        try:
            self.window.update_idletasks()
            current_y = self.window.winfo_y()
            window_height = self.window.winfo_height()
            screen_height = self.window.winfo_screenheight()
            screen_middle = screen_height // 2

            # --- 关键修正：检查窗口高度是否足以进行滚动 ---
            # 如果窗口高度太短，不足以同时覆盖中线和底边，则直接返回，不处理滚动
            if window_height <= (screen_height - screen_middle):
                return "break"

            # 判定滚动方向（delta: Windows/macOS, num: Linux）
            delta = getattr(event, 'delta', 0)
            num = getattr(event, 'num', 0)

            if delta:
                is_scroll_up = (delta < 0)  # 向上滚动，窗口上移
            elif num:
                is_scroll_up = (num != 4)
            else:
                return "break"

            # 计算边界
            # top_limit: 窗口向上移动的极限（下边缘贴底边）
            top_limit = screen_height - window_height
            # bottom_limit: 窗口向下移动的极限（上边缘贴中线）
            bottom_limit = screen_middle

            # 计算目标位置
            step = 60
            if is_scroll_up:
                # 向上滚动，y 减小，但不能小于 top_limit
                target_y = max(current_y - step, top_limit)
            else:
                # 向下滚动，y 增大，但不能大于 bottom_limit
                target_y = min(current_y + step, bottom_limit)

            # 更新位置
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

    def _on_drag_start(self, event):
        self.pause = True
        self.x = event.x
        self.y = event.y

    def _on_drag_stop(self, event):
        self.pause = False

    def _on_drag_motion(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.window.winfo_x() + deltax
        y = self.window.winfo_y() + deltay
        self.window.geometry(f"+{x}+{y}")

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
                self.window.destroy()  # 销毁窗口
        except:
            pass
