"""
LLM 输出中断监控

监听用户按下中断键（默认 ESC），停止 LLM 流式输出
"""
import keyboard
import logging
import threading
from typing import Optional
from config import ClientConfig as Config

logger = logging.getLogger(__name__)


# 全局事件：用于通知 LLM 停止输出（用于手动按 ESC 键的情况）
_stop_event = threading.Event()

# 线程局部存储：每个任务独立的停止标志
_thread_local = threading.local()


def should_stop() -> bool:
    """
    检查是否应该停止输出

    Returns:
        True 表示应该停止
    """
    # 优先检查线程局部停止标志
    local_stop = getattr(_thread_local, 'stop_event', None)
    if local_stop and local_stop.is_set():
        return True

    # 检查全局停止标志（ESC 键触发）
    return _stop_event.is_set()


def reset():
    """重置停止标志（开始新的输出前调用）"""
    _stop_event.clear()
    # 重置线程局部停止标志
    local_stop = getattr(_thread_local, 'stop_event', None)
    if local_stop:
        local_stop.clear()


def create_stop_callback() -> 'threading.Event':
    """
    为新的 LLM 任务创建独立的停止事件

    Returns:
        停止事件对象
    """
    stop_event = threading.Event()
    _thread_local.stop_event = stop_event
    return stop_event


def on_stop_pressed():
    """用户按下中断键时的回调"""
    _stop_event.set()

    # 如果有 toast，关闭它
    try:
        from util.ui.toast import ToastMessageManager
        toast_manager = ToastMessageManager()
        # 注意：close_last_toast() 方法不存在，这里先注释掉
        # TODO: 实现关闭最后一个 toast 的逻辑
        # toast_manager.close_last_toast()
    except Exception as e:
        logger.warning(f"关闭 toast 失败: {e}")


def start_monitor():
    """启动中断键监控（在模块导入时自动调用）"""
    keyboard.add_hotkey(Config.llm_stop_key, on_stop_pressed)


# 自动启动监控
start_monitor()
