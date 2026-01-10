"""
Toast 消息管理模块

提供浮动消息通知功能，支持普通和流式输出两种模式。

Usage:
    # 普通 Toast
    toast("消息内容", duration=3000)

    # 流式 Toast（用于测试）
    toast_stream("消息内容", markdown=False)
"""
import logging
import threading
import time
import tkinter as tk
from queue import Queue
from dataclasses import dataclass, field
from typing import Literal, Optional, Callable, Union, List, TYPE_CHECKING
import sys
import os

# 直接运行时，将项目根目录添加到 sys.path
if __name__ == "__main__":
    file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(file_dir))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from util.ui.toast_text import ToastWindowText
    from util.ui.toast_label import ToastWindowLabel
    from util.ui.toast_constants import (
        QUEUE_POLL_INTERVAL_MS,
        DEFAULT_DURATION_MS,
        DEFAULT_INITIAL_WIDTH,
        STREAM_CHAR_DELAY_S,
        TK_SCALING_FACTOR,
    )
else:
    from .toast_text import ToastWindowText
    from .toast_label import ToastWindowLabel
    from .toast_constants import (
        QUEUE_POLL_INTERVAL_MS,
        DEFAULT_DURATION_MS,
        DEFAULT_INITIAL_WIDTH,
        STREAM_CHAR_DELAY_S,
        TK_SCALING_FACTOR,
    )

# 用于类型注解的前向引用
if TYPE_CHECKING:
    from .toast_text import ToastWindowText
    from .toast_label import ToastWindowLabel


# 配置日志（默认不输出，在测试时配置）
logger = logging.getLogger(__name__)


# ============================================================
# 数据类
# ============================================================

@dataclass
class ToastMessage:
    """Toast 消息配置数据类
    
    Attributes:
        text: 消息文本内容
        font_size: 字体大小（像素）
        font_family: 字体名称，空字符串使用系统默认
        bg: 背景颜色（十六进制或颜色名）
        fg: 前景色（文字颜色）
        duration: 显示时长（毫秒）
        initial_width: 初始宽度，0-1 为屏幕比例，>1 为像素值
        initial_height: 初始高度，0 表示自动计算
        streaming: 是否为流式模式
        window_type: 窗口类型 ('text' 或 'label')
        stop_callback: 窗口关闭时的回调函数
        markdown: 是否启用 Markdown 渲染
    """
    text: str
    font_size: int = 14
    font_family: str = ''
    bg: str = '#075077'
    fg: str = 'white'
    duration: int = DEFAULT_DURATION_MS
    initial_width: Union[float, int] = DEFAULT_INITIAL_WIDTH
    initial_height: int = 0
    streaming: bool = False
    window_type: Literal['text', 'label'] = 'text'
    stop_callback: Optional[Callable[[], None]] = None
    markdown: bool = False


# ============================================================
# Toast 消息管理器
# ============================================================

class ToastMessageManager:
    """Toast 消息管理器（单例模式）
    
    在独立的线程中运行 Tkinter 主循环，管理所有 Toast 窗口的生命周期。
    
    Features:
        - 单例模式，确保只有一个 Tkinter 主循环
        - 消息队列，支持并发添加消息
        - 活动窗口跟踪，支持流式输出更新
    """
    
    _instance: Optional['ToastMessageManager'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'ToastMessageManager':
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
            
        logger.debug("初始化 Toast 消息管理器")
        self._initialized = True
        self.message_queue: 'Queue[ToastMessage]' = Queue()
        self.is_running = False
        self.active_windows: List = []  # 运行时类型，避免循环导入
        self.root: Optional[tk.Tk] = None

        # 在子线程中启动 Tkinter
        self.manager_thread = threading.Thread(
            target=self._run_manager,
            daemon=True,
            name="ToastManagerThread"
        )
        self.manager_thread.start()

    def _run_manager(self) -> None:
        """在子线程中运行 Tkinter 主循环"""
        logger.debug("启动 Tkinter 主循环线程")
        
        # 创建隐藏的主窗口
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.tk.call('tk', 'scaling', TK_SCALING_FACTOR)

        # 设置窗口关闭时的行为
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 开始处理队列
        self.is_running = True
        self._process_queue()

        # 启动 Tkinter 主循环
        self.root.mainloop()

    def _on_close(self) -> None:
        """关闭所有窗口并退出"""
        logger.debug("关闭 Toast 管理器")
        self.is_running = False
        
        for window in self.active_windows[:]:
            try:
                window.window.destroy()
            except tk.TclError:
                pass
        
        self.active_windows.clear()
        
        if self.root:
            self.root.quit()

    def _process_queue(self) -> None:
        """处理队列中的消息"""
        try:
            if not self.message_queue.empty():
                msg = self.message_queue.get_nowait()
                logger.debug(f"处理消息: type={msg.window_type}, streaming={msg.streaming}")

                # 根据 window_type 选择窗口类
                WindowClass = ToastWindowLabel if msg.window_type == 'label' else ToastWindowText
                
                toast_window = WindowClass(
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
                toast_window.window.bind(
                    '<Destroy>',
                    lambda _, w=toast_window: self._remove_window(w)
                )

            # 清理已销毁的窗口
            self.active_windows = [
                w for w in self.active_windows
                if self._window_exists(w)
            ]

        except Exception as e:
            logger.warning(f"处理队列消息时出错: {e}")

        # 继续处理队列
        if self.is_running and self.root:
            self.root.after(QUEUE_POLL_INTERVAL_MS, self._process_queue)

    def _window_exists(self, window) -> bool:
        """检查窗口是否存在"""
        try:
            return window.window.winfo_exists()
        except tk.TclError:
            return False

    def _remove_window(self, window) -> None:
        """从活动窗口列表中移除窗口"""
        if window in self.active_windows:
            self.active_windows.remove(window)

    def add_message(self, msg: ToastMessage) -> None:
        """添加 ToastMessage 对象到队列
        
        Args:
            msg: Toast 消息配置对象
        """
        logger.debug(f"添加消息到队列: streaming={msg.streaming}")
        self.message_queue.put(msg)

    def update_last_toast(self, new_text: str) -> None:
        """更新最后一个活动的 Toast 文字
        
        Args:
            new_text: 新的完整文本内容
        """
        if self.active_windows:
            last_window = self.active_windows[-1]
            last_window.update_text(new_text)

    def finish_last_toast(self) -> None:
        """完成最后一个 Toast 的流式输出"""
        if self.active_windows:
            last_window = self.active_windows[-1]
            if last_window.streaming:
                last_window.finish()

    def close_last_toast(self) -> None:
        """关闭最后一个 Toast（用于用户按 ESC）"""
        if self.active_windows:
            last_window = self.active_windows[-1]
            try:
                last_window.window.destroy()
                self.active_windows.remove(last_window)
            except (tk.TclError, ValueError):
                pass


# ============================================================
# 公共 API 函数
# ============================================================

def toast(
    text: str,
    font_size: int = 14,
    bg: str = "#C41529",
    fg: str = 'white',
    duration: int = DEFAULT_DURATION_MS,
    initial_width: Union[float, int] = DEFAULT_INITIAL_WIDTH,
    initial_height: int = 0,
    streaming: bool = False,
    window_type: Literal['text', 'label'] = 'text',
    markdown: bool = False
) -> None:
    """显示浮动消息通知
    
    Args:
        text: 消息文本
        font_size: 字体大小
        bg: 背景颜色
        fg: 字体颜色
        duration: 显示时长（毫秒）
        initial_width: 初始宽度，0-1 为屏幕比例，>1 为像素值
        initial_height: 初始高度，0 表示自动计算
        streaming: 是否为流式模式
        window_type: 窗口类型 ('text' 或 'label')
        markdown: 是否启用 Markdown 渲染
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


def toast_stream(
    text: str,
    font_size: int = 14,
    bg: str = "#C41529",
    fg: str = 'white',
    duration: int = DEFAULT_DURATION_MS,
    initial_width: Union[float, int] = DEFAULT_INITIAL_WIDTH,
    initial_height: int = 0,
    window_type: Literal['text', 'label'] = 'text',
    markdown: bool = False
) -> None:
    """模拟流式输入的 Toast（用于测试流式输出效果）
    
    Args:
        text: 消息文本
        font_size: 字体大小
        bg: 背景颜色
        fg: 字体颜色
        duration: 显示时长（毫秒）
        initial_width: 初始宽度
        initial_height: 初始高度
        window_type: 窗口类型 ('text' 或 'label')
        markdown: 是否启用 Markdown 渲染
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

    # 模拟流式输出
    def simulate_streaming():
        for i in range(len(text) + 1):
            if i > 0:
                manager.update_last_toast(text[:i])
            time.sleep(STREAM_CHAR_DELAY_S)
        manager.finish_last_toast()

    stream_thread = threading.Thread(
        target=simulate_streaming,
        daemon=True,
        name="StreamSimulationThread"
    )
    stream_thread.start()


# ============================================================
# 测试代码
# ============================================================

if __name__ == "__main__":
    # 测试时启用日志，保存到模块所在目录
    import os
    log_file = os.path.join(os.path.dirname(__file__), 'toast_debug.log')
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8', mode='w'),
            # logging.StreamHandler()  # 同时输出到控制台
        ]
    )
    logger.info(f"日志文件: {log_file}")
    
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
    
    print("\n[测试 1] Text 版本 - 普通文本 - 非流式 (3秒)")
    toast(plain_text, bg="#075077", fg='white', duration=3000, window_type='text', initial_width=800)
    time.sleep(4)

    print("[测试 2] Text 版本 - 普通文本 - 流式 (5秒)")
    toast_stream(plain_text, bg="#2E7D32", fg='white', duration=5000, window_type='text', initial_width=800, markdown=False)
    time.sleep(7)

    print("[测试 3] Text 版本 - Markdown - 非流式 (3秒)")
    toast(markdown_text, bg="#1565C0", fg='white', duration=3000, window_type='text', initial_width=800, markdown=True)
    time.sleep(4)

    print("[测试 4] Text 版本 - Markdown - 流式 (5秒)")
    toast_stream(markdown_text, bg="#C62828", fg='white', duration=5000, window_type='text', initial_width=800, markdown=True)
    time.sleep(7)

    # ========== Label 版本测试 ==========
    
    print("[测试 5] Label 版本 - 普通文本 - 非流式 (3秒)")
    toast(plain_text, bg="#F57C00", fg='white', duration=3000, window_type='label', initial_width=800)
    time.sleep(4)

    print("[测试 6] Label 版本 - 普通文本 - 流式 (5秒)")
    toast_stream(plain_text, bg="#7B1FA2", fg='white', duration=5000, window_type='label', initial_width=800, markdown=False)
    time.sleep(7)

    print("[测试 7] Label 版本 - Markdown - 非流式 (3秒)")
    toast(markdown_text, bg="#00796B", fg='white', duration=3000, window_type='label', initial_width=800, markdown=True)
    time.sleep(4)

    print("[测试 8] Label 版本 - Markdown - 流式 (5秒)")
    toast_stream(markdown_text, bg="#5D4037", fg='white', duration=5000, window_type='label', initial_width=800, markdown=True)
    time.sleep(7)

    print("\n" + "=" * 60)
    print("所有测试完成！按 Ctrl+C 退出程序")
    print("=" * 60)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n程序退出")
