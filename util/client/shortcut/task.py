# coding: utf-8
"""
快捷键任务模块

管理单个快捷键的录音任务状态
"""

import asyncio
import time
from threading import Event, Timer
from typing import TYPE_CHECKING, Optional

from . import logger
from util.tools.my_status import Status

if TYPE_CHECKING:
    from util.client.shortcut.shortcut_config import Shortcut
    from util.client.state import ClientState
    from util.client.audio.recorder import AudioRecorder

# 延迟导入悬浮窗桥接（避免循环依赖）
_overlay_bridge = None

def _get_overlay_bridge():
    """获取悬浮窗桥接实例（延迟导入）"""
    global _overlay_bridge
    if _overlay_bridge is None:
        try:
            from util.client.ui.overlay_bridge import get_overlay_bridge
            _overlay_bridge = get_overlay_bridge()
        except ImportError:
            pass
    return _overlay_bridge



class ShortcutTask:
    """
    单个快捷键的录音任务

    跟踪每个快捷键独立的录音状态，防止互相干扰。
    """

    def __init__(self, shortcut: 'Shortcut', state: 'ClientState', recorder_class=None):
        """
        初始化快捷键任务

        Args:
            shortcut: 快捷键配置
            state: 客户端状态实例
            recorder_class: AudioRecorder 类（可选，用于延迟导入）
        """
        self.shortcut = shortcut
        self.state = state
        self._recorder_class = recorder_class

        # 任务状态
        self.task: Optional[asyncio.Future] = None
        self.recording_start_time: float = 0.0
        self.is_recording: bool = False

        # hold_mode 状态跟踪
        self.pressed: bool = False
        self.released: bool = True
        self.event: Event = Event()

        # 线程池（用于 countdown）
        self.pool = None

        # 录音状态动画
        self._status = Status('开始录音', spinner='point')

        # 延迟启动状态（hold_mode 用）
        self._pending_launch: bool = False
        self._launch_timer: Timer | None = None

    def _get_recorder(self) -> 'AudioRecorder':
        """获取 AudioRecorder 实例"""
        if self._recorder_class is None:
            from util.client.audio.recorder import AudioRecorder
            self._recorder_class = AudioRecorder
        return self._recorder_class(self.state)

    def start_pending_launch(self) -> None:
        """启动延迟启动定时器（hold_mode 用）"""
        if self._pending_launch or self.is_recording:
            return
        
        self._pending_launch = True
        self._launch_timer = Timer(self.threshold, self._on_launch_timer)
        self._launch_timer.daemon = True
        self._launch_timer.start()
        logger.debug(f"[{self.shortcut.key}] 开始计时，{self.threshold}s 后启动录音")

    def _on_launch_timer(self) -> None:
        """定时器回调：启动录音"""
        if self._pending_launch and not self.is_recording:
            self._pending_launch = False
            self.launch()

    def cancel_pending_launch(self) -> bool:
        """取消待启动状态，返回是否成功取消"""
        if not self._pending_launch:
            return False
        
        self._pending_launch = False
        if self._launch_timer:
            self._launch_timer.cancel()
            self._launch_timer = None
        logger.debug(f"[{self.shortcut.key}] 取消延迟启动（单击）")
        return True

    def launch(self) -> None:
        """启动录音任务"""
        logger.info(f"[{self.shortcut.key}] 触发：开始录音")

        # 记录开始时间
        self.recording_start_time = time.time()
        self.is_recording = True
        
        # 设置当前活动的 LLM 角色（从快捷键配置读取）
        self.state.current_role = self.shortcut.role
        if self.shortcut.role:
            logger.info(f"[{self.shortcut.key}] 使用 LLM 角色: {self.shortcut.role}")

        # 将开始标志放入队列
        asyncio.run_coroutine_threadsafe(
            self.state.queue_in.put({'type': 'begin', 'time': self.recording_start_time, 'data': None}),
            self.state.loop
        )

        # 更新录音状态
        self.state.start_recording(self.recording_start_time)

        # 打印动画：正在录音
        self._status.start()
        
        # 显示悬浮窗
        bridge = _get_overlay_bridge()
        if bridge:
            bridge.show('recording')

        # 启动识别任务
        recorder = self._get_recorder()
        self.task = asyncio.run_coroutine_threadsafe(
            recorder.record_and_send(),
            self.state.loop,
        )

    def cancel(self) -> None:
        """取消录音任务（时间过短）"""
        logger.debug(f"[{self.shortcut.key}] 取消录音任务（时间过短）")

        self.is_recording = False
        self.state.stop_recording()
        self._status.stop()
        
        # 隐藏悬浮窗
        bridge = _get_overlay_bridge()
        if bridge:
            bridge.hide()

        self.task.cancel()
        self.task = None

    def finish(self) -> None:
        """完成录音任务"""
        logger.info(f"[{self.shortcut.key}] 释放：完成录音")

        self.is_recording = False
        self.state.stop_recording()
        self._status.stop()
        
        # 显示悬浮窗：处理中
        bridge = _get_overlay_bridge()
        if bridge:
            bridge.show('processing')

        asyncio.run_coroutine_threadsafe(
            self.state.queue_in.put({
                'type': 'finish',
                'time': time.time(),
                'data': None
            }),
            self.state.loop
        )

        # 执行 restore（可恢复按键 + 非阻塞模式）
        # 阻塞模式下按键不会发送到系统，状态不会改变，不需要恢复
        if self.shortcut.is_toggle_key() and not self.shortcut.suppress:
            self._restore_key()

    def _restore_key(self) -> None:
        """恢复按键状态（防自捕获逻辑由 ShortcutManager 处理）"""
        # 通知管理器执行 restore
        # 防自捕获：管理器会设置 flag 再发送按键
        manager = self._manager_ref()
        if manager:
            logger.debug(f"[{self.shortcut.key}] 自动恢复按键状态 (suppress={self.shortcut.suppress})")
            manager.schedule_restore(self.shortcut.key)
        else:
            logger.warning(f"[{self.shortcut.key}] manager 引用丢失，无法 restore")
