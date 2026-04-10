# coding: utf-8
"""
服务端状态管理模块

提供 ServerState (主进程) 和 WorkerState (子进程) 类。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from multiprocessing import Queue, Process
from typing import TYPE_CHECKING, Dict, List, Optional, Any

import websockets
from rich.console import Console

from util.server.schema import Result, RecognitionSession

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
    sockets_id: Optional[List] = None
    
    # 消息队列
    queue_in: Queue = field(default_factory=Queue)
    queue_out: Queue = field(default_factory=Queue)

    # 识别子进程
    recognize_process: Optional[Process] = None

    def initialize(self) -> None:
        """初始化状态（如有需要）"""
        pass


@dataclass
class WorkerState:
    """
    识别子进程运行状态
    
    存储识别 Worker 进程运行时的状态：
    - sessions: 活跃识别会话，以 task_id 为键
    """
    # 识别会话集
    sessions: Dict[str, RecognitionSession] = field(default_factory=dict)

    def get_session(self, task_id: str, socket_id: str = '', source: str = '') -> RecognitionSession:
        """获取或创建识别会话"""
        if task_id not in self.sessions:
            result = Result(task_id=task_id, socket_id=socket_id, source=source)
            self.sessions[task_id] = RecognitionSession(task_id=task_id, result=result)
        return self.sessions[task_id]
    
    def clear_sessions_by_socket_id(self, socket_id: str) -> int:
        """清理指定 socket_id 关联的所有任务结果缓存"""
        tasks_to_remove = [
            task_id for task_id, session in self.sessions.items() 
            if session.result.socket_id == socket_id
        ]
        for task_id in tasks_to_remove:
            self.sessions.pop(task_id, None)
        return len(tasks_to_remove)
