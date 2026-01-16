# coding: utf-8
"""
鼠标监听模块

提供 MouseHandler 类用于监听鼠标前进键（X2/XBUTTON2）控制录音。
仅支持 Windows 平台。
"""

from __future__ import annotations

import time
from platform import system
from typing import TYPE_CHECKING, Optional

from config import ClientConfig as Config
from util.logger import get_logger

if TYPE_CHECKING:
    from util.client.input.shortcut import ShortcutHandler

# 日志记录器
logger = get_logger('client')

# Windows 鼠标消息常量
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_XBUTTONDBLCLK = 0x020D

# XBUTTON 按键标识
XBUTTON1 = 0x0001  # 后退键
XBUTTON2 = 0x0002  # 前进键


class MouseHandler:
    """
    鼠标监听器
    
    监听鼠标前进键（X2）控制录音，复用 ShortcutHandler 的录音逻辑。
    仅支持 Windows 平台。
    """
    
    def __init__(self, shortcut_handler: 'ShortcutHandler', suppress: bool = True):
        """
        初始化鼠标处理器
        
        Args:
            shortcut_handler: 快捷键处理器实例，用于复用录音控制逻辑
            suppress: 是否阻塞鼠标事件（默认 True）
        """
        self.shortcut_handler = shortcut_handler
        self.suppress = suppress
        self.mouse_listener = None
        self._recording_start_time = 0.0
    
    def _mouse_logic(self, msg: int) -> None:
        """
        处理鼠标事件逻辑
        
        Args:
            msg: Windows 消息类型
        """
        state = self.shortcut_handler.state
        
        if msg == WM_XBUTTONDOWN:
            if not state.recording:
                logger.info("鼠标 X2 键按下：开始录音")
                self._recording_start_time = time.time()
                self.shortcut_handler._launch_task()
                
        elif msg == WM_XBUTTONUP:
            if state.recording:
                duration = time.time() - self._recording_start_time if self._recording_start_time > 0 else 0
                logger.debug(f"鼠标 X2 键松开：持续时间 {duration:.2f}s")
                
                if duration < Config.threshold:
                    logger.info("鼠标 X2 键松开：取消录音（时间过短）")
                    self.shortcut_handler._cancel_task()
                else:
                    logger.info("鼠标 X2 键松开：完成录音")
                    self.shortcut_handler._finish_task()
                
                self._recording_start_time = 0.0
    
    def _create_mouse_filter(self):
        """
        创建鼠标 Windows 事件过滤器
        
        Returns:
            callable: 事件过滤函数
        """
        
        def win32_event_filter(msg, data):
            """
            鼠标事件过滤器
            
            Args:
                msg: Windows 消息类型
                data: MSLLHOOKSTRUCT 结构，包含鼠标数据
                
            Returns:
                bool: 返回 True 允许事件继续传递
            """
            # 只处理 XBUTTON 消息，其他的直接放行
            if msg not in (WM_XBUTTONDOWN, WM_XBUTTONUP, WM_XBUTTONDBLCLK):
                return True
            
            # 只处理前进键（X2），其他所有按键放行
            xbutton = (data.mouseData >> 16) & 0xFFFF
            if xbutton != XBUTTON2:
                return True
            
            # 处理录音逻辑
            self._mouse_logic(msg)
            
            # 判断是否阻塞事件
            if self.suppress:
                self.mouse_listener.suppress_event()
            
            return True
        
        return win32_event_filter
    
    def start(self) -> None:
        """启动鼠标监听器"""
        if system() != 'Windows':
            logger.warning("鼠标 X2 键控制功能仅支持 Windows 平台")
            return
        
        try:
            from pynput import mouse
            
            self.mouse_listener = mouse.Listener(
                win32_event_filter=self._create_mouse_filter()
            )
            self.mouse_listener.start()
            logger.info("鼠标 X2 键监听器已启动")
        except ImportError:
            logger.error("无法导入 pynput，鼠标监听功能不可用")
        except Exception as e:
            logger.error(f"启动鼠标监听器失败: {e}")
    
    def stop(self) -> None:
        """停止鼠标监听器"""
        if self.mouse_listener and self.mouse_listener.running:
            self.mouse_listener.stop()
            logger.debug("鼠标 X2 键监听器已停止")
