import threading
import time
import tkinter as tk
from queue import Queue
import ctypes

ctypes.windll.shcore.SetProcessDpiAwareness(1)

class ToastWindow:
    def __init__(self, parent_root, text, font_size=14, bg='#075077', fg='white',
                 duration=3000, initial_width=400, initial_height=0, streaming=False):
        """创建浮动消息窗口

        Args:
            parent_root: 父窗口
            text: 初始文本
            font_size: 字体大小
            bg: 背景颜色
            fg: 字体颜色
            duration: 显示时长（毫秒）
            initial_width: 初始宽度
            initial_height: 初始高度（0 表示自动计算）
            streaming: 是否为流式模式（支持动态更新文本）
        """
        self.parent_root = parent_root
        self.window = tk.Toplevel(parent_root)
        self.window.hang_on = False
        self.streaming = streaming
        self.pause = False
        self.duration = duration
        self.initial_width = initial_width
        self.initial_height = initial_height
        self.timer_id = None

        # 设置窗口属性
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.configure(bg=bg)

        # 绑定可拖动
        self.window.bind('<ButtonPress-1>', self._on_drag_start)
        self.window.bind('<ButtonRelease-1>', self._on_drag_stop)
        self.window.bind('<B1-Motion>', self._on_drag_motion)
        self.window.bind('<Escape>', self._destroy_window)

        # 创建文字标签
        self.label = tk.Label(
            self.window,
            text=text,
            font=('Microsoft YaHei', font_size),
            fg=fg,
            bg=bg,
            justify=tk.LEFT,
            wraplength=self.initial_width - 40  # 预留 padding
        )
        self.label.pack(padx=20, pady=15)

        # 设置初始窗口位置（屏幕中央，单行高度）
        self._set_window_position(initial=True)

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

            # 加上 padding
            window_width = max(self.initial_width, label_width + 40)  # 左右各 20px padding

            # 如果设置了初始高度，使用初始高度；否则自动计算
            if self.initial_height > 0:
                window_height = max(self.initial_height, label_height + 30)
            else:
                window_height = label_height + 30  # 上下各 15px padding

            # 限制最大宽度和最小高度
            window_width = min(window_width, 800)
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
        """更新文本（流式模式）

        Args:
            new_text: 新的文本内容
        """
        if not self.streaming:
            return

        self.label.config(text=new_text)
        # 更新窗口高度
        self._set_window_position(initial=False)

    def finish(self):
        """完成流式输出，启动销毁计时器"""
        if self.streaming:
            self.streaming = False
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


class ToastMessageManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.initialized = False
            return cls._instance

    def __init__(self):
        if not self.initialized:
            self.message_queue = Queue()
            self.is_running = False
            self.initialized = True
            self.active_windows = []  # 跟踪活动窗口

            # 在子线程中启动 Tkinter
            self.manager_thread = threading.Thread(target=self._run_manager)
            self.manager_thread.daemon = True
            self.manager_thread.start()

    def _run_manager(self):
        """在子线程中运行 Tkinter 主循环"""
        # 创建隐藏的主窗口
        self.root = tk.Tk()
        self.root.withdraw()  # 隐藏主窗口
        self.root.tk.call('tk', 'scaling', 2)

        # 设置窗口关闭时的行为
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 开始处理队列
        self.is_running = True
        self._process_queue()

        # 启动 Tkinter 主循环
        self.root.mainloop()

    def _on_close(self):
        """关闭所有窗口并退出"""
        self.is_running = False
        for window in self.active_windows[:]:
            try:
                window.window.destroy()
            except:
                pass
        self.active_windows.clear()
        self.root.quit()

    def _process_queue(self):
        """处理队列中的消息"""
        try:
            # 检查是否有新消息
            if not self.message_queue.empty():
                data = self.message_queue.get_nowait()

                # 支持多种格式
                if len(data) == 4:
                    # 旧格式：text, font_size, bg, duration
                    text, font_size, bg, duration = data
                    fg = 'white'
                    initial_width = 400
                    initial_height = 0
                    streaming = False
                elif len(data) == 5:
                    # 格式：text, font_size, bg, duration, streaming
                    text, font_size, bg, duration, streaming = data
                    fg = 'white'
                    initial_width = 400
                    initial_height = 0
                elif len(data) == 8:
                    # 新格式：text, font_size, bg, fg, duration, initial_width, initial_height, streaming
                    text, font_size, bg, fg, duration, initial_width, initial_height, streaming = data
                else:
                    # 尝试解析其他格式
                    text = data[0]
                    font_size = data[1] if len(data) > 1 else 14
                    bg = data[2] if len(data) > 2 else '#075077'
                    fg = data[3] if len(data) > 3 else 'white'
                    duration = data[4] if len(data) > 4 else 3000
                    initial_width = data[5] if len(data) > 5 else 400
                    initial_height = data[6] if len(data) > 6 else 0
                    streaming = data[7] if len(data) > 7 else False

                # 创建新窗口
                toast_window = ToastWindow(self.root, text, font_size, bg, fg, duration,
                                         initial_width, initial_height, streaming=streaming)
                self.active_windows.append(toast_window)

                # 设置窗口销毁时的回调
                toast_window.window.bind('<Destroy>',
                    lambda e, w=toast_window: self._remove_window(w))

            # 清理已销毁的窗口
            self.active_windows = [w for w in self.active_windows
                                 if w.window.winfo_exists()]

        except Exception as e:
            # 忽略队列空异常等
            pass

        # 继续处理队列
        if self.is_running:
            self.root.after(100, self._process_queue)

    def _remove_window(self, window):
        """从活动窗口列表中移除窗口"""
        if window in self.active_windows:
            self.active_windows.remove(window)

    def add_message(self, text, font_size=14, bg='#075077', fg='white',
                   duration=3000, initial_width=400, initial_height=0, streaming=False):
        """添加消息到队列"""
        self.message_queue.put((text, font_size, bg, fg, duration, initial_width, initial_height, streaming))

    def update_last_toast(self, text):
        """更新最后一个 toast 的文本（用于流式输出）"""
        if self.active_windows:
            last_window = self.active_windows[-1]
            if last_window.streaming:
                last_window.update_text(text)

    def finish_last_toast(self):
        """完成最后一个 toast 的流式输出"""
        if self.active_windows:
            last_window = self.active_windows[-1]
            if last_window.streaming:
                last_window.finish()

    def close_last_toast(self):
        """关闭最后一个 toast（用于用户按 ESC）"""
        if self.active_windows:
            last_window = self.active_windows[-1]
            try:
                last_window.window.destroy()
                self.active_windows.remove(last_window)
            except:
                pass


def toast(text, font_size=14, bg="#C41529", fg='white', duration=2000,
         initial_width=400, initial_height=0, streaming=False):
    """显示浮动消息的便捷函数"""
    manager = ToastMessageManager()
    manager.add_message(text, font_size, bg, fg, duration, initial_width, initial_height, streaming)


# 使用示例
if __name__ == "__main__":
    message_text = """21:14:13 【国际航协：中国四大航空公司加入航班数据交互项目】 财联社11月14日电，从国际航协获悉，中国东方航空公司宣布加入国际航协航班计划数据交互项目（SDEP）。至此，该计划已涵盖中国四大航空公司——中国国际航空公司、中国东方航空公司、中国南方航空公司和海南航空公司，标志着该计划在中国市场的推进迈出了重要一步。随着中国四大航空公司加入航班计划数据交互项目，该项目目前涵盖了中国民航75%以上的运力。 (证券时报)"""
    
    # 测试多个消息
    toast(message_text, bg="#075077", duration=3000)
    time.sleep(4)
    toast(message_text, bg="#C41529", duration=2000)
    time.sleep(4)
    toast(message_text, bg="#008000", duration=1000)
    
    # 保持主线程运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("程序退出")