"""
LLM 输出中断监控

监听用户按下中断键（默认 ESC），停止 LLM 流式输出

使用 pynput GlobalHotKeys 替代 keyboard 库
"""
import threading
from typing import Optional
from config_client import ClientConfig as Config
from . import logger


class StopMonitor:
    """LLM 输出中断监控类"""
    
    def __init__(self):
        # 任务独立的停止事件
        self._stop_event = threading.Event()
        # 线程局部存储：每个任务独立的停止标志
        self._thread_local = threading.local()
        # 快捷键管理器引用
        self._hotkey_manager = None
        self._is_running = False

    def should_stop(self) -> bool:
        """
        检查是否应该停止输出

        Returns:
            True 表示应该停止
        """
        # 优先检查线程局部停止标志
        local_stop = getattr(self._thread_local, 'stop_event', None)
        if local_stop and local_stop.is_set():
            return True

        # 检查全局停止标志（ESC 键触发）
        return self._stop_event.is_set()

    def reset(self):
        """重置停止标志（开始新的输出前调用）"""
        self._stop_event.clear()
        # 重置线程局部停止标志
        local_stop = getattr(self._thread_local, 'stop_event', None)
        if local_stop:
            local_stop.clear()

    def create_stop_callback(self) -> 'threading.Event':
        """
        为新的 LLM 任务创建独立的停止事件

        Returns:
            停止事件对象
        """
        stop_event = threading.Event()
        self._thread_local.stop_event = stop_event
        return stop_event

    def on_stop_pressed(self):
        """用户按下中断键时的回调"""
        logger.debug("检测到 ESC 键按下，停止 LLM 输出")
        self._stop_event.set()

        # 如果有 toast，关闭它
        try:
            from core.ui.toast import ToastMessageManager
            toast_manager = ToastMessageManager()
            # 注意：close_last_toast() 方法目前未实现，此处保留逻辑结构
        except Exception as e:
            logger.warning(f"关闭 toast 失败: {e}")

    def start(self):
        """启动中断键监控"""
        if self._is_running:
            return
            
        try:
            from core.client.global_hotkey import get_global_hotkey_manager
            
            self._hotkey_manager = get_global_hotkey_manager()
            
            # 将 Config.llm_stop_key 转换为 pynput 格式
            stop_key = Config.llm_stop_key.lower().strip()
            if not stop_key.startswith('<'):
                stop_key = f'<{stop_key}>'
            
            self._hotkey_manager.register(stop_key, self.on_stop_pressed)
            self._hotkey_manager.start()
            self._is_running = True
            logger.debug(f"LLM 中断键监控已启动: {stop_key}")
        except Exception as e:
            logger.warning(f"启动 LLM 中断键监控失败: {e}")

    def stop(self):
        """停止中断键监控"""
        if self._hotkey_manager and self._is_running:
            try:
                # 注意：目前 GlobalHotkeyManager 是单例，stop() 可能会影响全局
                # 但这里是按照实例化的逻辑进行封装
                self._hotkey_manager.stop()
                self._is_running = False
                logger.debug("LLM 中断键监控已停止")
            except Exception as e:
                logger.warning(f"停止 LLM 中断键监控失败: {e}")
