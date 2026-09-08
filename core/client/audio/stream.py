# coding: utf-8
"""
音频流管理模块

提供 AudioStreamManager 类用于管理音频输入流，包括流的创建、
启动、停止和设备检测。
"""

from __future__ import annotations

import time
import threading
from typing import TYPE_CHECKING, Optional

import numpy as np
import sounddevice as sd

from core.client.state import console
from . import logger

if TYPE_CHECKING:
    from core.client.state import ClientState
    from ..app import CapsWriterClient



class AudioStreamManager:
    """
    音频流管理器

    负责管理音频输入流的生命周期，包括：
    - 检测和选择音频设备
    - 创建和启动音频流
    - 处理音频数据回调
    - 流的重启和关闭

    Attributes:
        state: 客户端状态实例
        sample_rate: 采样率（默认 48000Hz）
        block_duration: 每个数据块的时长（秒，默认 0.05s）
    """

    SAMPLE_RATE = 48000
    BLOCK_DURATION = 0.05  # 50ms
    RETRY_DELAY = 2.0

    def __init__(self, app: CapsWriterClient):
        """
        初始化音频流管理器

        Args:
            app: 客户端 App 实例
        """
        self.app = app
        self._channels = 1
        self._running = False  # 当前音频流是否已启动
        self._want_running = False  # 设备缺失时仍保留运行意图
        self._lock = threading.RLock()
        self._restart_timer = None
        self._restarting = False
        self._last_error = None

    @property
    def state(self) -> ClientState:
        """快捷访问状态单例"""
        return self.app.state

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info,
        status: sd.CallbackFlags
    ) -> None:
        """
        音频数据回调函数

        当音频流接收到新数据时调用，将数据放入异步队列中。
        """
        # 只在录音状态时处理数据
        if not self.state.recording:
            return

        import asyncio

        # 将数据放入队列
        if self.app.loop and self.state.queue_in:
            asyncio.run_coroutine_threadsafe(
                self.state.queue_in.put({
                    'type': 'data',
                    'time': time.time(),
                    'data': indata.copy(),
                }),
                self.app.loop
            )

    def _on_stream_finished(self) -> None:
        """立即离开 PortAudio 回调，交由其他线程恢复设备。"""
        if not self._want_running or self._restarting:
            return
        loop = self.app.loop
        if loop and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(self._schedule_restart)
            except RuntimeError:
                pass  # 程序退出时，事件循环可能刚好关闭。

    def _schedule_restart(self) -> None:
        with self._lock:
            if not self._want_running or self._restart_timer is not None:
                return
            self._restart_timer = threading.Timer(self.RETRY_DELAY, self._retry)
            self._restart_timer.daemon = True
            self._restart_timer.start()

    def _retry(self) -> None:
        with self._lock:
            self._restart_timer = None
            if self._want_running:
                self.reopen()

    def _report_unavailable(self, error: Exception) -> None:
        message = str(error)
        if message != self._last_error:
            logger.warning("Microphone unavailable; retrying in the background: %s", message)
            console.print("[yellow]麦克风暂不可用，正在后台重试；重新连接后将自动恢复录音。[/]")
            if '-9999' in message:
                console.print(
                    '[yellow]请检查 Windows 麦克风隐私权限，以及设备的独占模式和音频增强设置。[/]'
                )
            self._last_error = message
        self._schedule_restart()

    def start(self) -> Optional[sd.InputStream]:
        """启动音频流；设备暂不可用时后台重试，不依赖控制台输入。"""
        with self._lock:
            self._want_running = True
            if self._running:
                return self.state.stream
            stream = None
            try:
                try:
                    device = sd.query_devices(kind='input')
                except UnicodeDecodeError:
                    logger.warning("无法获取音频设备名称（编码问题），尝试默认单声道设备")
                    device = {'name': '未知设备', 'max_input_channels': 1}
                self._channels = min(2, device['max_input_channels'])
                if self._channels < 1:
                    raise sd.PortAudioError('No input channels available')
                stream = sd.InputStream(
                    samplerate=self.SAMPLE_RATE,
                    blocksize=int(self.BLOCK_DURATION * self.SAMPLE_RATE),
                    device=None,
                    dtype="float32",
                    channels=self._channels,
                    callback=self._audio_callback,
                    finished_callback=self._on_stream_finished,
                )
                stream.start()
                if not stream.active:
                    raise sd.PortAudioError('Input stream stopped during startup')
                self.state.stream = stream
                self._running = True
                self._last_error = None
                if self._restart_timer is not None:
                    self._restart_timer.cancel()
                    self._restart_timer = None
                logger.info("Microphone connected: %s", device.get('name', 'default'))
                console.print(
                    f"使用默认音频设备：{device.get('name', '未知设备')}，声道数：{self._channels}",
                    markup=False,
                )
                return stream
            except Exception as error:
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass
                self.state.stream = None
                self._running = False
                self._report_unavailable(error)
                return None

    def _close_stream(self) -> None:
        stream, self.state.stream = self.state.stream, None
        self._running = False
        if stream is not None:
            try:
                stream.close()
            except Exception as error:
                logger.debug("Closing unavailable microphone: %s", error)

    def stop(self) -> None:
        """关闭音频流并取消待执行的重连，防止退出后再次开启设备。"""
        with self._lock:
            self._want_running = False
            if self._restart_timer is not None:
                self._restart_timer.cancel()
                self._restart_timer = None
            self._close_stream()

    def reopen(self) -> Optional[sd.InputStream]:
        """在 PortAudio 回调之外关闭旧流、刷新设备列表并重新打开。"""
        with self._lock:
            if not self._want_running:
                return None
            self._restarting = True
            try:
                self._close_stream()
                # 刷新设备列表即可；仍有回调指针时不能卸载 CFFI 共享库。
                sd._terminate()
                sd._initialize()
                return self.start()
            except Exception as error:
                self._report_unavailable(error)
                return None
            finally:
                self._restarting = False
