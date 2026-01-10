# coding: utf-8
"""
快捷键处理模块

提供 ShortcutHandler 类用于管理录音快捷键，支持长按模式和单击模式。
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import TYPE_CHECKING, Optional

import keyboard

from config import ClientConfig as Config
from util.client.state import console
from util.tools.my_status import Status
from util.logger import get_logger

if TYPE_CHECKING:
    from util.client.state import ClientState
    from util.client.audio.recorder import AudioRecorder

# 日志记录器
logger = get_logger('client')


class ShortcutHandler:
    """
    快捷键处理器
    
    管理录音快捷键的绑定和事件处理，支持两种模式：
    - 长按模式：按住录音，松开结束
    - 单击模式：单击开始/结束录音，长按发送原始按键
    """
    
    def __init__(self, state: 'ClientState', recorder_class=None):
        """
        初始化快捷键处理器
        
        Args:
            state: 客户端状态实例
            recorder_class: AudioRecorder 类（可选，用于延迟导入）
        """
        self.state = state
        self._recorder_class = recorder_class
        self._task: Optional[asyncio.Future] = None
        self._status = Status('开始录音', spinner='point')
        self._pool = ThreadPoolExecutor()
        self._pressed = False
        self._released = True
        self._event = Event()
    
    def _get_recorder(self) -> 'AudioRecorder':
        """获取 AudioRecorder 实例"""
        if self._recorder_class is None:
            from util.client.audio.recorder import AudioRecorder
            self._recorder_class = AudioRecorder
        return self._recorder_class(self.state)
    
    def _shortcut_correct(self, e: keyboard.KeyboardEvent) -> bool:
        """验证触发的按键是否正确"""
        key_expect = keyboard.normalize_name(Config.shortcut).replace('left ', '')
        key_actual = e.name.replace('left ', '')
        return key_expect == key_actual
    
    def _launch_task(self) -> None:
        """启动录音任务"""
        logger.debug("启动录音任务")
        
        # 记录开始时间
        t1 = time.time()
        
        # 将开始标志放入队列
        asyncio.run_coroutine_threadsafe(
            self.state.queue_in.put({'type': 'begin', 'time': t1, 'data': None}),
            self.state.loop
        )
        
        # 更新录音状态
        self.state.start_recording(t1)
        
        # 打印动画：正在录音
        self._status.start()
        
        # 启动识别任务
        recorder = self._get_recorder()
        self._task = asyncio.run_coroutine_threadsafe(
            recorder.record_and_send(),
            self.state.loop,
        )
    
    def _cancel_task(self) -> None:
        """取消录音任务（时间过短）"""
        logger.debug("取消录音任务（时间过短）")
        
        self.state.stop_recording()
        self._status.stop()
        
        if self._task:
            self._task.cancel()
    
    def _finish_task(self) -> None:
        """完成录音任务"""
        logger.debug("完成录音任务")
        
        self.state.stop_recording()
        self._status.stop()
        
        asyncio.run_coroutine_threadsafe(
            self.state.queue_in.put({
                'type': 'finish',
                'time': time.time(),
                'data': None
            }),
            self.state.loop
        )
    
    # ========== 单击模式 ==========
    
    def _count_down(self, e: Event) -> None:
        """按下后，开始倒数"""
        time.sleep(Config.threshold)
        e.set()
    
    def _manage_task(self, e: Event) -> None:
        """管理录音任务"""
        was_recording = self.state.recording
        
        if not was_recording:
            self._launch_task()
        
        if e.wait(timeout=Config.threshold * 0.8):
            if self.state.recording and was_recording:
                self._finish_task()
        else:
            if not was_recording:
                self._cancel_task()
            keyboard.send(Config.shortcut)
    
    def _click_mode_handler(self, e: keyboard.KeyboardEvent) -> None:
        """单击模式事件处理"""
        if e.event_type == 'down' and self._released:
            self._pressed, self._released = True, False
            self._event = Event()
            self._pool.submit(self._count_down, self._event)
            self._pool.submit(self._manage_task, self._event)
        
        elif e.event_type == 'up' and self._pressed:
            self._pressed, self._released = False, True
            self._event.set()
    
    # ========== 长按模式 ==========
    
    def _hold_mode_handler(self, e: keyboard.KeyboardEvent) -> None:
        """长按模式事件处理"""
        if e.event_type == 'down' and not self.state.recording:
            logger.debug("检测到长按模式：按下")
            self._launch_task()
            
        elif e.event_type == 'up' and self.state.recording:
            recording_start = self.state.recording_start_time
            duration = time.time() - recording_start if recording_start > 0 else 0
            logger.debug(f"检测到长按模式：松开，持续时间: {duration:.2f}s")
            
            if duration < Config.threshold:
                self._cancel_task()
            else:
                self._finish_task()
                
                if Config.restore_key:
                    time.sleep(0.01)
                    keyboard.send(Config.shortcut)
    
    # ========== 公共接口 ==========
    
    def _hold_handler(self, e: keyboard.KeyboardEvent) -> None:
        """长按模式的完整处理器"""
        if not self._shortcut_correct(e):
            return
        self._hold_mode_handler(e)
    
    def _click_handler(self, e: keyboard.KeyboardEvent) -> None:
        """单击模式的完整处理器"""
        if not self._shortcut_correct(e):
            return
        self._click_mode_handler(e)
    
    def bind(self) -> None:
        """绑定快捷键"""
        mode = "长按模式" if Config.hold_mode else "单击模式"
        suppress = not Config.hold_mode or Config.suppress
        
        logger.info(f"绑定快捷键: {Config.shortcut} ({mode}), 阻塞: {suppress}")
        
        if Config.hold_mode:
            keyboard.hook_key(Config.shortcut, self._hold_handler, suppress=Config.suppress)
        else:
            keyboard.hook_key(Config.shortcut, self._click_handler, suppress=True)
    
    def unbind(self) -> None:
        """解绑快捷键"""
        try:
            keyboard.unhook_key(Config.shortcut)
            logger.debug(f"已解绑快捷键: {Config.shortcut}")
        except Exception as e:
            logger.debug(f"解绑快捷键时发生错误: {e}")
