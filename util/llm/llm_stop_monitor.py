"""
LLM 输出中断监控

监听用户按下中断键（默认 ESC），停止 LLM 流式输出
"""
import keyboard
import threading
from config import ClientConfig as Config


# 全局事件：用于通知 LLM 停止输出
_stop_event = threading.Event()


def should_stop() -> bool:
    """
    检查是否应该停止输出

    Returns:
        True 表示应该停止
    """
    return _stop_event.is_set()


def reset():
    """重置停止标志（开始新的输出前调用）"""
    _stop_event.clear()


def on_stop_pressed():
    """用户按下中断键时的回调"""
    _stop_event.set()

    # 如果有 toast，关闭它
    try:
        from util.ui.toast import ToastMessageManager
        toast_manager = ToastMessageManager()
        toast_manager.close_last_toast()
    except:
        pass


def start_monitor():
    """启动中断键监控（在模块导入时自动调用）"""
    keyboard.add_hotkey(Config.llm_stop_key, on_stop_pressed)


# 自动启动监控
start_monitor()
