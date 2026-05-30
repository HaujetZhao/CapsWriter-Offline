# coding: utf-8
"""
服务端状态管理模块

提供 ServerState (主进程) 和 WorkerState (子进程) 类。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from multiprocessing import Queue, Process
from multiprocessing.managers import ListProxy
from typing import TYPE_CHECKING, Dict, Optional

import websockets
from rich.console import Console

from core.server.schema import Result, RecognitionSession

if TYPE_CHECKING:
    from .app import CapsWriterServer

# Rich console 用于控制台输出（服务端统一使用此实例）
console = Console(highlight=False)


@dataclass
class ServerState:
    """
    主进程运行状态
    
    存储服务端主进程运行时的共享状态：
    - sockets: WebSocket 连接字典，以 socket_id 为键
    - sockets_id: 跨进程的 socket ID 列表（由 Manager 创建）
    - queue_in: 任务输入队列（主进程 -> 识别进程）
    - queue_out: 结果输出队列（识别进程 -> 主进程）
    - recognize_process: 识别子进程句柄
    """
    app: Optional[CapsWriterServer] = None

    # WebSocket 连接池
    sockets: Dict[str, websockets.WebSocketServerProtocol] = field(default_factory=dict)
    
    # 跨进程共享的 socket ID 列表（需要用 Manager().list() 初始化）
    sockets_id: Optional[ListProxy] = None
    
    # 消息队列
    queue_in: Queue = field(default_factory=Queue)
    queue_out: Queue = field(default_factory=Queue)

    # 识别子进程
    recognize_process: Optional[Process] = None



@dataclass
class WorkerState:
    """
    识别子进程运行状态
    
    存储识别 Worker 进程运行时的状态：
    - sessions: 活跃识别会话，以 task_id 为键
    """
    # 识别会话集
    sessions: Dict[str, RecognitionSession] = field(default_factory=dict)
    
    # GPU 加速状态
    gpu_boosted: bool = False       # 当前是否已执行 GPU 加速
    gpu_last_active: float = 0.0    # 上次任务活跃时间，用于超时取消加速

    def get_session(self, task_id: str, socket_id: str = '', source: str = '') -> RecognitionSession:
        """获取或创建识别会话"""
        if task_id not in self.sessions:
            result = Result(task_id=task_id, socket_id=socket_id, type=source)
            self.sessions[task_id] = RecognitionSession(task_id=task_id, result=result)
        return self.sessions[task_id]
    
    def cleanup_sessions(self, sockets_id: ListProxy) -> int:
        """清理已断开连接的客户端 session"""
        stale_ids = [
            sid for sid, session in list(self.sessions.items())
            if session.result.socket_id not in sockets_id
        ]
        for sid in stale_ids:
            self.sessions.pop(sid, None)
        if stale_ids:
            from . import logger
            logger.debug(f"清理了 {len(stale_ids)} 个已断开连接的 session")
        return len(stale_ids)

