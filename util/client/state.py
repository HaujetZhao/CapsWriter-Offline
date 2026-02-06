# coding: utf-8
"""
客户端状态管理模块

提供 ClientState 类用于管理客户端的全局状态。
使用 dataclass 提供类型安全和清晰的状态定义。
"""

from __future__ import annotations

import asyncio
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Dict, Any

if TYPE_CHECKING:
    import sounddevice as sd
    from websockets.legacy.client import WebSocketClientProtocol

from rich.console import Console
from rich.theme import Theme

from . import logger


# 配置 Rich console
_theme = Theme({
    'markdown.code': 'cyan',
    'markdown.item.number': 'yellow'
})
console = Console(highlight=False, soft_wrap=True, theme=_theme)


@dataclass
class ClientState:
    """
    客户端运行状态

    管理客户端运行过程中的所有共享状态，包括事件循环、消息队列、
    WebSocket 连接、音频流和录音状态等。

    Attributes:
        loop: asyncio 事件循环
        queue_in: 音频数据输入队列
        queue_out: 处理结果输出队列（保留）
        websocket: WebSocket 客户端连接
        stream: 音频输入流
        recording: 是否正在录音
        recording_start_time: 录音开始时间戳
        audio_files: 任务ID到音频文件路径的映射
        last_recognition_text: 最近一次识别的最终文本（热词替换后），供"添加纠错记录"使用
    """

    loop: Optional[asyncio.AbstractEventLoop] = None
    queue_in: Optional[asyncio.Queue] = None
    queue_out: Optional[asyncio.Queue] = None
    websocket: Optional['WebSocketClientProtocol'] = None
    stream: Optional['sd.InputStream'] = None

    # 组件引用 (用于清理)
    shortcut_handler: Any = None
    stream_manager: Any = None
    processor: Any = None
    mouse_handler: Any = None
    udp_controller: Any = None

    recording: bool = False
    recording_start_time: float = 0.0
    audio_files: Dict[str, Path] = field(default_factory=dict)

    # 最近一次识别结果（用于手动添加纠错记录）
    last_recognition_text: Optional[str] = None
    
    # 最近一次输出内容（如果是 LLM 润色，则是润色结果；否则是原始识别结果）
    last_output_text: Optional[str] = None
    
    def initialize(self) -> None:
        """
        初始化状态
        
        创建事件循环和消息队列，准备开始接收音频数据。
        """
        self.loop = asyncio.get_event_loop()
        self.queue_in = asyncio.Queue()
        self.queue_out = asyncio.Queue()
        logger.debug("客户端状态已初始化")
    
    def reset(self) -> None:
        """
        重置状态
        
        清理所有状态，关闭连接和流。用于重新初始化或退出时清理。
        """
        logger.debug("正在重置客户端状态...")
        
        # 关闭 WebSocket 连接
        if self.websocket is not None:
            try:
                if not self.websocket.closed:
                    logger.debug("WebSocket 连接将被关闭")
            except Exception:
                pass
            self.websocket = None
        
        # 关闭音频流
        if self.stream is not None:
            try:
                self.stream.close()
                logger.debug("音频流已关闭")
            except Exception:
                pass
            self.stream = None
        
        # 重置其他状态
        self.recording = False
        self.recording_start_time = 0.0
        self.audio_files.clear()
        
        logger.debug("客户端状态重置完成")
    
    def start_recording(self, start_time: float) -> None:
        """
        开始录音
        
        Args:
            start_time: 录音开始的时间戳
        """
        self.recording = True
        self.recording_start_time = start_time
        logger.debug(f"录音状态已更新: recording=True, start_time={start_time:.2f}")
    
    def stop_recording(self) -> float:
        """
        停止录音
        
        Returns:
            录音持续时间（秒）
        """
        duration = 0.0
        if self.recording_start_time > 0:
            duration = time.time() - self.recording_start_time
        
        self.recording = False
        self.recording_start_time = 0.0
        logger.debug(f"录音状态已更新: recording=False, duration={duration:.2f}s")
        return duration
    
    @property
    def is_connected(self) -> bool:
        """检查 WebSocket 是否已连接"""
        if self.websocket is None:
            return False
        try:
            return not self.websocket.closed
        except AttributeError:
            return self.websocket is not None
    
    def register_audio_file(self, task_id: str, file_path: Path) -> None:
        """
        注册音频文件
        
        Args:
            task_id: 任务ID
            file_path: 音频文件路径
        """
        self.audio_files[task_id] = file_path
        logger.debug(f"注册音频文件: task_id={task_id}, path={file_path}")
    
    def pop_audio_file(self, task_id: str) -> Optional[Path]:
        """
        获取并移除音频文件路径
        
        Args:
            task_id: 任务ID
            
        Returns:
            音频文件路径，如果不存在则返回 None
        """
        file_path = self.audio_files.pop(task_id, None)
        if file_path:
            logger.debug(f"获取音频文件: task_id={task_id}, path={file_path}")
        return file_path

    def set_output_text(self, text: str) -> None:
        """
        设置最近一次输出文本并通过 UDP 广播（如果启用）
        
        Args:
            text: 输出文本内容
        """
        from config_client import ClientConfig as Config
        
        # 更新状态
        self.last_output_text = text
        
        # UDP 广播到配置的目标地址（如果启用）
        if Config.udp_broadcast and Config.udp_broadcast_targets:
            message = text.encode('utf-8')
            for addr, port in Config.udp_broadcast_targets:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                        sock.sendto(message, (addr, port))
                        logger.debug(f"UDP 发送输出文本到 {addr}:{port}, 长度: {len(text)}")
                except Exception as e:
                    logger.warning(f"UDP 发送输出文本到 {addr}:{port} 失败: {e}")


# 全局状态实例
_global_state: Optional[ClientState] = None


def get_state() -> ClientState:
    """
    获取全局客户端状态实例
    
    如果尚未初始化，则创建新实例。
    
    Returns:
        ClientState 实例
    """
    global _global_state
    if _global_state is None:
        _global_state = ClientState()
        logger.debug("创建全局 ClientState 实例")
    return _global_state
