import time
import os
import asyncio
import signal
import sys
import threading
import atexit
import logging
from typing import List, Callable, Optional

class LifecycleManager:
    """
    应用程序生命周期管理器 (单例模式)
    
    统一管理：
    1. 信号处理 (Signal Handling)
    2. 退出请求 (Shutdown Request)
    3. 资源清理 (Resource Cleanup)
    4. 退出状态 (Shutdown State)
    """
    
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(LifecycleManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._is_shutting_down = False
        self._shutdown_event = asyncio.Event()
        self._cleanup_callbacks: List[Callable] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # 默认 Logger (Console), init 时可覆盖
        self.logger = logging.getLogger('lifecycle')
        self._exit_on_signal = False
        self._last_sigint_time = 0.0
        
        # 注册 atexit 作为最后一道防线
        atexit.register(self._atexit_handler)

    # ... (initialize method unchanged) ...

    def initialize(self, 
                   loop: asyncio.AbstractEventLoop = None, 
                   logger: logging.Logger = None,
                   exit_on_signal: bool = False):
        """
        初始化管理器
        
        Args:
            loop: 事件循环
            logger: 日志记录器（传入 Client 或 Server 的 logger）
            exit_on_signal: 是否在收到信号后立即调用 sys.exit(0) (用于 Client 端)
        """
        if loop:
            self._loop = loop
        else:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
        
        if logger:
            self.logger = logger
            
        self._exit_on_signal = exit_on_signal

        self._register_signals()
        self.logger.debug("LifecycleManager 初始化完成")

    # ... (register_signals unchanged) ...

    def _register_signals(self):
        """注册 SIGINT 和 SIGTERM 信号处理器"""
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            self.logger.debug("信号处理器已注册 (LifecycleManager)")
        except Exception as e:
            self.logger.warning(f"注册信号处理器失败: {e}")

    def _signal_handler(self, signum, frame):
        """信号回调"""
        signal_name = signal.Signals(signum).name
        
        # 防手抖逻辑 (仅对 SIGINT/Ctrl+C 有效)
        if signum == signal.SIGINT:
            current_time = time.time()
            if current_time - self._last_sigint_time > 1.0:
                self._last_sigint_time = current_time
                print(f"\n收到 {signal_name}，1秒内再次按下将会退出...")
                # 同时也记录日志，但不用 info 级别以免刷屏，用 debug
                self.logger.debug(f"收到 {signal_name}, 等待确认...")
                return
            else:
                print(f"确认退出...")

        self.logger.info(f"LifecycleManager 收到信号: {signal_name} ({signum})")
        self.request_shutdown(reason=f"Signal {signal_name}")
        
        if self._exit_on_signal:
            self.logger.debug("Exit On Signal 启用，正在强制退出...")
            try:
                self.cleanup()
            finally:
                self.logger.debug("调用 os._exit(0) 立即终止")
                os._exit(0)

    def register_on_shutdown(self, callback: Callable):
        """注册清理函数 (LIFO 执行顺序)"""
        if callback not in self._cleanup_callbacks:
            self._cleanup_callbacks.insert(0, callback) # 后注册先执行

    def request_shutdown(self, reason="Unknown"):
        """请求退出应用"""
        if self._is_shutting_down:
            self.logger.debug(f"正在退出中，忽略重复请求 (Reason: {reason})")
            return

        self._is_shutting_down = True
        self.logger.info(f"收到退出请求 (Reason: {reason})，开始关闭流程...")

        # 1. 设置 Asyncio 事件，通知主循环退出
        if self._loop and not self._loop.is_closed():
            try:
                self._loop.call_soon_threadsafe(self._shutdown_event.set)
            except RuntimeError:
                # 循环可能已经关闭
                pass
        elif self._shutdown_event:
             # 如果没有 loop 引用，但有 event (sync context?)
             # 通常 event 需要 loop，所以这里主要是防御性编程
            pass

        # 2. 如果没有运行在 asyncio loop 中，或者需要立即清理（比如非 async 程序），
        # 可以在这里做一些同步处理。但为了安全，我们通常依赖主循环响应 event 后调用 cleanup。

    async def wait_for_shutdown(self):
        """等待退出信号 (Coroutine)"""
        await self._shutdown_event.wait()
        self.logger.info("Shutdown event set, resuming execution...")

    def cleanup(self):
        """执行所有清理回调 (确保只执行一次)"""
        if hasattr(self, '_cleanup_done') and self._cleanup_done:
            return
        self._cleanup_done = True
        self._is_shutting_down = True  # 标记为正在退出

        self.logger.debug("LifecycleManager 开始执行清理回调...")
        for callback in self._cleanup_callbacks:
            try:
                name = getattr(callback, '__name__', str(callback))
                self.logger.debug(f"执行清理: {name}")
                callback()
            except Exception as e:
                self.logger.error(f"清理回调执行失败: {e}", exc_info=True)
        self.logger.debug("LifecycleManager 清理完成")

    def _atexit_handler(self):
        """atexit 处理器，确保最后被调用"""
        if not self._is_shutting_down:
            # 这里可能 logger 已经关闭了，打印可能不可靠
            # 但尽力清理
            try:
                self.logger.debug("Atexit 触发，执行清理...")
                self.cleanup()
            except:
                pass

    @property
    def is_shutting_down(self) -> bool:
        return self._is_shutting_down

# 全局实例
lifecycle = LifecycleManager()
