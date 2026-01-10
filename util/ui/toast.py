import threading
import time
import tkinter as tk
from queue import Queue
from dataclasses import dataclass
from typing import Literal
import sys
import os

# 直接运行时，切换工作目录到项目根目录，并添加到搜索路径
if __name__ == "__main__":
    # 获取文件所在目录的父目录（项目根目录）
    file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(file_dir))
    os.chdir(project_root)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # 现在可以使用绝对导入了
    from util.ui.toast_text import ToastWindowText
    from util.ui.toast_label import ToastWindowLabel
else:
    # 作为模块导入时，使用相对导入
    from .toast_text import ToastWindowText
    from .toast_label import ToastWindowLabel


@dataclass
class ToastMessage:
    """Toast 消息数据类"""
    text: str
    font_size: int = 14
    font_family: str = ''     # 字体（空字符串表示使用系统默认）
    bg: str = '#075077'
    fg: str = 'white'
    duration: int = 3000
    initial_width: int = 400
    initial_height: int = 0
    streaming: bool = False
    window_type: Literal['text', 'label'] = 'text'
    stop_callback: any = None  # 窗口关闭时的回调函数（用于停止 LLM 输出）
    markdown: bool = False     # 是否在完成后转换为 Markdown 渲染


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
                        msg.font_family,
                        msg.bg,
                        msg.fg,
                        msg.duration,
                        msg.initial_width,
                        msg.initial_height,
                        streaming=msg.streaming,
                        stop_callback=msg.stop_callback,
                        markdown=msg.markdown
                    )
                else:  # 默认使用 text 版本
                    toast_window = ToastWindowText(
                        self.root,
                        msg.text,
                        msg.font_size,
                        msg.font_family,
                        msg.bg,
                        msg.fg,
                        msg.duration,
                        msg.initial_width,
                        msg.initial_height,
                        streaming=msg.streaming,
                        stop_callback=msg.stop_callback,
                        markdown=msg.markdown
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
         initial_width=0.5, initial_height=0, streaming=False, window_type='text', markdown=False):
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
        markdown: 是否在完成后转换为 Markdown 渲染（仅当 streaming=True 时有效）
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
        window_type=window_type,
        markdown=markdown
    )
    manager.add_message(msg)


def toast_stream(text, font_size=14, bg="#C41529", fg='white', duration=2000,
                initial_width=0.5, initial_height=0, window_type='text', markdown=False):
    """模拟流式输入的 Toast（用于测试流式输出效果）

    Args:
        text: 消息文本
        font_size: 字体大小
        bg: 背景颜色
        fg: 字体颜色
        duration: 显示时长（毫秒）
        initial_width: 初始宽度
        initial_height: 初始高度（0 表示自动计算）
        window_type: 窗口类型 ('text' 或 'label')
        markdown: 是否在完成后转换为 Markdown 渲染
    """
    manager = ToastMessageManager()

    # 创建流式 toast
    msg = ToastMessage(
        text="",
        font_size=font_size,
        bg=bg,
        fg=fg,
        duration=duration,
        initial_width=initial_width,
        initial_height=initial_height,
        streaming=True,
        window_type=window_type,
        markdown=markdown
    )
    manager.add_message(msg)

    # 模拟流式输出（逐字显示）
    def simulate_streaming():
        for i in range(len(text) + 1):
            if i > 0:
                manager.update_last_toast(text[:i])
            time.sleep(0.001)  # 每 5ms 显示一个字符

        # 流式输出完成
        manager.finish_last_toast()

    # 在新线程中模拟流式输出
    import threading
    stream_thread = threading.Thread(target=simulate_streaming, daemon=True)
    stream_thread.start()


# 使用示例
if __name__ == "__main__":
    print("=" * 60)
    print("全面 Toast 测试程序")
    print("=" * 60)
    print("\n将执行 8 个测试用例:")
    print("1. Text 版本 - 普通文本 - 非流式")
    print("2. Text 版本 - 普通文本 - 流式")
    print("3. Text 版本 - Markdown - 非流式")
    print("4. Text 版本 - Markdown - 流式")
    print("5. Label 版本 - 普通文本 - 非流式")
    print("6. Label 版本 - 普通文本 - 流式")
    print("7. Label 版本 - Markdown - 非流式")
    print("8. Label 版本 - Markdown - 流式")
    print("=" * 60)

    # 测试文本
    plain_text = """在这个快节奏、信息爆炸的时代，我们似乎总是被一种无形的压力所裹挟，焦虑、烦恼、疲惫，像潮水般涌入我们的内心。我们争分夺秒地奔波于工作、学习、社交之间，却往往忽略了内心深处那片安静的土地。在这样的背景下，寻找静心，成为了我们重新审视自我、找回平衡的重要途径。"""
    markdown_text = """# Markdown 测试

## 功能特性

这是一段**粗体文字**和*斜体文字*的示例。

### 代码示例
```python
def hello():
    print("Hello, World!")
```

### 列表
- 第一项
- 第二项
- 第三项

> 这是一段引用文字"""

    # ========== Text 版本测试 ==========
    
    # 测试 1: Text 版本 - 普通文本 - 非流式
    print("\n[测试 1] Text 版本 - 普通文本 - 非流式 (3秒)")
    toast(plain_text, bg="#075077", fg='white', duration=3000, window_type='text', initial_width=800)
    time.sleep(4)

    # 测试 2: Text 版本 - 普通文本 - 流式
    print("[测试 2] Text 版本 - 普通文本 - 流式 (5秒)")
    toast_stream(plain_text, bg="#2E7D32", fg='white', duration=5000, window_type='text', initial_width=800, markdown=False)
    time.sleep(7)

    # 测试 3: Text 版本 - Markdown - 非流式
    print("[测试 3] Text 版本 - Markdown - 非流式 (3秒)")
    toast(markdown_text, bg="#1565C0", fg='white', duration=3000, window_type='text', initial_width=800, markdown=True)
    time.sleep(4)

    # 测试 4: Text 版本 - Markdown - 流式
    print("[测试 4] Text 版本 - Markdown - 流式 (5秒)")
    toast_stream(markdown_text, bg="#C62828", fg='white', duration=5000, window_type='text', initial_width=800, markdown=True)
    time.sleep(7)

    # ========== Label 版本测试 ==========
    
    # 测试 5: Label 版本 - 普通文本 - 非流式
    print("[测试 5] Label 版本 - 普通文本 - 非流式 (3秒)")
    toast(plain_text, bg="#F57C00", fg='white', duration=3000, window_type='label', initial_width=800)
    time.sleep(4)

    # 测试 6: Label 版本 - 普通文本 - 流式
    print("[测试 6] Label 版本 - 普通文本 - 流式 (5秒)")
    toast_stream(plain_text, bg="#7B1FA2", fg='white', duration=5000, window_type='label', initial_width=800, markdown=False)
    time.sleep(7)

    # 测试 7: Label 版本 - Markdown - 非流式
    print("[测试 7] Label 版本 - Markdown - 非流式 (3秒)")
    toast(markdown_text, bg="#00796B", fg='white', duration=3000, window_type='label', initial_width=800, markdown=True)
    time.sleep(4)

    # 测试 8: Label 版本 - Markdown - 流式
    print("[测试 8] Label 版本 - Markdown - 流式 (5秒)")
    toast_stream(markdown_text, bg="#5D4037", fg='white', duration=5000, window_type='label', initial_width=800, markdown=True)
    time.sleep(7)


    print("\n" + "=" * 60)
    print("所有测试完成！按 Ctrl+C 退出程序")
    print("=" * 60)

    # 保持主线程运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n程序退出")
