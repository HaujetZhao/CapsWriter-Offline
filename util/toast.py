import threading
import time
import tkinter as tk
from queue import Queue
from dataclasses import dataclass
from typing import Literal

from util.toast_windows import ToastWindowText, ToastWindowLabel


@dataclass
class ToastMessage:
    """Toast 消息数据类"""
    text: str
    font_size: int = 14
    bg: str = '#075077'
    fg: str = 'white'
    duration: int = 3000
    initial_width: int = 400
    initial_height: int = 0
    streaming: bool = False
    window_type: Literal['text', 'label'] = 'text'


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
                msg = self.message_queue.get_nowait()

                # 根据 window_type 选择窗口类
                if msg.window_type == 'label':
                    toast_window = ToastWindowLabel(
                        self.root,
                        msg.text,
                        msg.font_size,
                        msg.bg,
                        msg.fg,
                        msg.duration,
                        msg.initial_width,
                        msg.initial_height,
                        streaming=msg.streaming
                    )
                else:  # 默认使用 text 版本
                    toast_window = ToastWindowText(
                        self.root,
                        msg.text,
                        msg.font_size,
                        msg.bg,
                        msg.fg,
                        msg.duration,
                        msg.initial_width,
                        msg.initial_height,
                        streaming=msg.streaming
                    )

                self.active_windows.append(toast_window)

                # 设置窗口销毁时的回调
                toast_window.window.bind('<Destroy>',
                    lambda _, w=toast_window: self._remove_window(w))

            # 清理已销毁的窗口
            self.active_windows = [w for w in self.active_windows
                                 if w.window.winfo_exists()]

        except Exception:
            # 忽略队列空异常等
            pass

        # 继续处理队列
        if self.is_running:
            self.root.after(100, self._process_queue)

    def _remove_window(self, window):
        """从活动窗口列表中移除窗口"""
        if window in self.active_windows:
            self.active_windows.remove(window)

    def add_message(self, msg: ToastMessage):
        """添加 ToastMessage 对象到队列"""
        self.message_queue.put(msg)

    def update_last_toast(self, new_text):
        """更新最后一个活动的 toast 文字"""
        if self.active_windows:
            last_window = self.active_windows[-1]
            last_window.update_text(new_text)

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
         initial_width=400, initial_height=0, streaming=False, window_type='text'):
    """显示浮动消息的便捷函数

    Args:
        text: 消息文本
        font_size: 字体大小
        bg: 背景颜色
        fg: 字体颜色
        duration: 显示时长（毫秒）
        initial_width: 初始宽度
        initial_height: 初始高度（0 表示自动计算）
        streaming: 是否为流式模式
        window_type: 窗口类型 ('text' 或 'label')
    """
    manager = ToastMessageManager()
    msg = ToastMessage(
        text=text,
        font_size=font_size,
        bg=bg,
        fg=fg,
        duration=duration,
        initial_width=initial_width,
        initial_height=initial_height,
        streaming=streaming,
        window_type=window_type
    )
    manager.add_message(msg)


# 使用示例
if __name__ == "__main__":
    message_text = """21:14:13 【国际航协：中国四大航空公司加入航班数据交互项目】 财联社11月14日电，从国际航协获悉，中国东方航空公司宣布加入国际航协航班计划数据交互项目（SDEP）。至此，该计划已涵盖中国四大航空公司——中国国际航空公司、中国东方航空公司、中国南方航空公司和海南航空公司，标志着该计划在中国市场的推进迈出了重要一步。随着中国四大航空公司加入航班计划数据交互项目，该项目目前涵盖了中国民航75%以上的运力。 (证券时报)"""

    # 测试多个消息（使用 Text 版本）
    toast(message_text, bg="#075077", duration=3000, window_type='text')
    time.sleep(4)
    toast(message_text, bg="#C41529", duration=2000, window_type='text')
    time.sleep(4)
    # 使用 Label 版本
    toast(message_text, bg="#008000", duration=1000, window_type='label')

    # 或者使用 ToastMessage 对象
    msg = ToastMessage(
        text="使用 Dataclass 的消息",
        bg="#FF5722",
        window_type='label'
    )
    manager = ToastMessageManager()
    manager.add_message_obj(msg)

    # 保持主线程运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("程序退出")
