# coding: utf-8
"""
悬浮窗桥接模块

提供 OverlayBridge 类，用于在客户端异步线程和 Tkinter 主线程之间
安全地传递悬浮窗事件。

使用队列 + tkinter.after() 轮询机制实现跨线程通信。

支持两种模式：
1. GUI 模式：调用 set_overlay() + start_polling() 绑定已有窗口
2. 命令行模式：调用 start() 自动创建 Tk 线程和悬浮窗
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

from util.client.ui import logger

if TYPE_CHECKING:
    from gui.status_overlay import StatusOverlay


class OverlayEventType(Enum):
    """悬浮窗事件类型"""
    SHOW = auto()       # 显示悬浮窗
    HIDE = auto()       # 隐藏悬浮窗
    SET_VOLUME = auto() # 更新音量


@dataclass
class OverlayEvent:
    """悬浮窗事件"""
    type: OverlayEventType
    status: Optional[str] = None    # 状态 (recording/processing/done/error)
    role: Optional[str] = None      # 角色名称
    volume: float = 0.0             # 音量值 (0.0-1.0)
    timestamp: float = 0.0          # 事件时间戳


class OverlayBridge:
    """
    悬浮窗桥接器
    
    连接客户端异步线程和 Tkinter 主线程，通过事件队列传递悬浮窗操作。
    
    使用方式 A (GUI 环境):
        1. bridge.set_overlay(existing_overlay)
        2. bridge.start_polling()  # 在 Tkinter 主线程调用
        3. bridge.show('recording') / bridge.hide() / bridge.set_volume(0.5)
    
    使用方式 B (命令行环境):
        1. bridge.start()  # 自动创建 Tk 线程和悬浮窗
        2. bridge.show('recording') / bridge.hide() / bridge.set_volume(0.5)
        3. bridge.stop()  # 程序退出时调用
    """
    
    # 轮询间隔（毫秒）
    POLL_INTERVAL = 16  # ~60fps
    
    # 单例实例
    _instance: Optional['OverlayBridge'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._queue: queue.Queue[OverlayEvent] = queue.Queue()
        self._overlay: Optional['StatusOverlay'] = None
        self._polling: bool = False
        self._poll_id: Optional[str] = None
        self._initialized = True
        
        # 命令行模式相关
        self._tk_thread: Optional[threading.Thread] = None
        self._tk_root = None
        self._running = False
        self._enabled = True  # 是否启用悬浮窗功能
        
        logger.debug("OverlayBridge 初始化完成")
    
    def set_enabled(self, enabled: bool) -> None:
        """
        启用/禁用悬浮窗功能
        
        Args:
            enabled: 是否启用
        """
        self._enabled = enabled
        if not enabled and self._overlay:
            self._overlay.hide()
    
    def set_overlay(self, overlay: 'StatusOverlay') -> None:
        """
        设置悬浮窗实例（GUI 模式使用）
        
        Args:
            overlay: StatusOverlay 实例
        """
        self._overlay = overlay
        logger.debug("OverlayBridge 已绑定悬浮窗")
    
    def start(self, position: str = 'bottom_center', opacity: float = 0.9) -> None:
        """
        启动悬浮窗系统（命令行模式使用）
        
        在单独的线程中创建 Tkinter 主循环和 StatusOverlay。
        
        Args:
            position: 悬浮窗位置
            opacity: 透明度
        """
        if self._running:
            return
        
        if not self._enabled:
            logger.debug("悬浮窗功能已禁用，跳过启动")
            return
        
        self._running = True
        self._tk_thread = threading.Thread(
            target=self._run_tk_thread,
            args=(position, opacity),
            daemon=True,
            name="OverlayTkThread"
        )
        self._tk_thread.start()
        logger.info("悬浮窗线程已启动")
    
    def _run_tk_thread(self, position: str, opacity: float) -> None:
        """Tkinter 线程主函数"""
        try:
            import tkinter as tk
            from gui.status_overlay import StatusOverlay
            
            # 创建隐藏的根窗口
            self._tk_root = tk.Tk()
            self._tk_root.withdraw()
            
            # 创建悬浮窗
            self._overlay = StatusOverlay(
                position=position,
                opacity=opacity
            )
            
            # 启动轮询
            self._polling = True
            self._poll_events()
            
            logger.debug("Tkinter 主循环开始")
            
            # 运行主循环
            self._tk_root.mainloop()
            
        except ImportError as e:
            logger.warning(f"无法导入悬浮窗模块: {e}")
            self._running = False
        except Exception as e:
            logger.error(f"悬浮窗线程异常: {e}")
            self._running = False
    
    def stop(self) -> None:
        """停止悬浮窗系统"""
        self._running = False
        self._polling = False
        
        if self._tk_root:
            try:
                self._tk_root.after(0, self._tk_root.quit)
            except Exception:
                pass
        
        self._overlay = None
        self._tk_root = None
        logger.debug("悬浮窗系统已停止")
    
    def start_polling(self) -> None:
        """启动事件轮询（在 Tkinter 主线程调用，GUI 模式使用）"""
        if self._polling:
            return
        
        if self._overlay is None:
            logger.warning("未设置悬浮窗，无法启动轮询")
            return
        
        self._polling = True
        self._poll_events()
        logger.debug("OverlayBridge 轮询已启动")
    
    def stop_polling(self) -> None:
        """停止事件轮询"""
        self._polling = False
        if self._poll_id and self._overlay:
            try:
                self._overlay.after_cancel(self._poll_id)
            except Exception:
                pass
        self._poll_id = None
        logger.debug("OverlayBridge 轮询已停止")
    
    def _poll_events(self) -> None:
        """轮询并处理事件队列"""
        if not self._polling or self._overlay is None:
            return
        
        # 处理队列中的所有事件
        events_processed = 0
        max_events_per_poll = 10  # 每次轮询最多处理的事件数
        
        while events_processed < max_events_per_poll:
            try:
                event = self._queue.get_nowait()
                self._handle_event(event)
                events_processed += 1
            except queue.Empty:
                break
        
        # 安排下次轮询
        self._poll_id = self._overlay.after(self.POLL_INTERVAL, self._poll_events)
    
    def _handle_event(self, event: OverlayEvent) -> None:
        """处理单个事件"""
        if self._overlay is None or not self._enabled:
            return
        
        try:
            if event.type == OverlayEventType.SHOW:
                self._overlay.show(status=event.status, role=event.role)
            elif event.type == OverlayEventType.HIDE:
                self._overlay.hide()
            elif event.type == OverlayEventType.SET_VOLUME:
                self._overlay.set_volume(event.volume)
        except Exception as e:
            logger.error(f"处理悬浮窗事件失败: {e}")
    
    # ========== 客户端调用接口 ==========
    
    def show(self, status: str = 'recording', role: str = None) -> None:
        """
        显示悬浮窗（线程安全）
        
        Args:
            status: 状态 ('recording', 'processing', 'done', 'error')
            role: 角色名称（可选）
        """
        if not self._enabled:
            return
        
        event = OverlayEvent(
            type=OverlayEventType.SHOW,
            status=status,
            role=role,
            timestamp=time.time()
        )
        self._queue.put(event)
    
    def hide(self) -> None:
        """隐藏悬浮窗（线程安全）"""
        event = OverlayEvent(
            type=OverlayEventType.HIDE,
            timestamp=time.time()
        )
        self._queue.put(event)
    
    def set_volume(self, volume: float) -> None:
        """
        设置音量（线程安全）
        
        Args:
            volume: 音量值 (0.0-1.0)
        """
        if not self._enabled:
            return
        
        # 音量事件可能非常频繁，只保留最新的
        event = OverlayEvent(
            type=OverlayEventType.SET_VOLUME,
            volume=max(0.0, min(1.0, volume)),
            timestamp=time.time()
        )
        self._queue.put(event)


# 全局实例
_bridge_instance: Optional[OverlayBridge] = None

def get_overlay_bridge() -> OverlayBridge:
    """获取全局 OverlayBridge 实例"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = OverlayBridge()
    return _bridge_instance

