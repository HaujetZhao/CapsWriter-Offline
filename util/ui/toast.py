"""
Toast 消息通知模块

提供简单的浮动消息通知功能。

Usage:
    # 普通 Toast
    toast("消息内容", duration=3000)

    # 流式 Toast（用于测试）
    toast_stream("消息内容", markdown=False)
"""
import time
import logging
import threading
from typing import Union, Literal
import sys
import os

# 直接运行时，将项目根目录添加到 sys.path
if __name__ == "__main__":
    file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(file_dir))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from util.ui.toast_manager import ToastMessageManager, ToastMessage
    from util.ui.toast_constants import (
        DEFAULT_DURATION_MS,
        DEFAULT_INITIAL_WIDTH,
        STREAM_CHAR_DELAY_S,
    )
    from util.ui.toast_logger import get_toast_logger
else:
    from .toast_manager import ToastMessageManager, ToastMessage
    from .toast_constants import (
        DEFAULT_DURATION_MS,
        DEFAULT_INITIAL_WIDTH,
        STREAM_CHAR_DELAY_S,
    )
    from .toast_logger import get_toast_logger


# 配置日志（智能检测主程序配置）
logger = get_toast_logger(__name__)


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
    msg_id = manager.add_message(msg)

    # 模拟流式输出
    def simulate_streaming():
        for i in range(len(text) + 1):
            if i > 0:
                manager.update_toast(msg_id, text[:i])
            time.sleep(STREAM_CHAR_DELAY_S)
        manager.finish_toast(msg_id)

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
    log_file = os.path.join(os.path.dirname(__file__), 'toast_debug.log')

    # 配置根日志（因为独立运行）
    from util.ui.toast_logger import configure_toast_logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8', mode='w'),
            # logging.StreamHandler()  # 同时输出到控制台
        ],
        force=True  # 强制重新配置
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
    plain_text = 5*"""在这个快节奏、信息爆炸的时代，我们似乎总是被一种无形的压力所裹挟，焦虑、烦恼、疲惫，像潮水般涌入我们的内心。我们争分夺秒地奔波于工作、学习、社交之间，却往往忽略了内心深处那片安静的土地。在这样的背景下，寻找静心，成为了我们重新审视自我、找回平衡的重要途径。"""

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

> 这是一段引用文字"""*1

    # ========== Text 版本测试 ==========

    # print("\n[测试 1] Text 版本 - 普通文本 - 非流式 (3秒)")
    # toast(plain_text, bg="#075077", fg='white', duration=3000, window_type='text', initial_width=800)
    # time.sleep(4)

    # print("[测试 2] Text 版本 - 普通文本 - 流式 (5秒)")
    # toast_stream(plain_text, bg="#2E7D32", fg='white', duration=5000, window_type='text', initial_width=800, markdown=False)
    # time.sleep(7)

    # print("[测试 3] Text 版本 - Markdown - 非流式 (3秒)")
    # toast(markdown_text, bg="#1565C0", fg='white', duration=3000, window_type='text', initial_width=800, markdown=True)
    # time.sleep(4)

    # print("[测试 4] Text 版本 - Markdown - 流式 (5秒)")
    # toast_stream(markdown_text, bg="#C62828", fg='white', duration=5000, window_type='text', initial_width=800, markdown=True)
    # time.sleep(7)

    # ========== Label 版本测试 ==========

    # print("[测试 5] Label 版本 - 普通文本 - 非流式 (3秒)")
    # toast(plain_text, bg="#F57C00", fg='white', duration=3000, window_type='label', initial_width=800)
    # time.sleep(4)

    # print("[测试 6] Label 版本 - 普通文本 - 流式 (5秒)")
    # toast_stream(plain_text, bg="#7B1FA2", fg='white', duration=5000, window_type='label', initial_width=800, markdown=False)
    # time.sleep(7)

    print("[测试 7] Label 版本 - Markdown - 非流式 (3秒)")
    toast(markdown_text, bg="#00796B", fg='white', duration=3000, window_type='label', initial_width=800, markdown=True)
    time.sleep(4)

    # print("[测试 8] Label 版本 - Markdown - 流式 (5秒)")
    # toast_stream(markdown_text, bg="#5D4037", fg='white', duration=5000, window_type='label', initial_width=800, markdown=True)
    # time.sleep(7)

    print("\n" + "=" * 60)
    print("所有测试完成！按 Ctrl+C 退出程序")
    print("=" * 60)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n程序退出")
