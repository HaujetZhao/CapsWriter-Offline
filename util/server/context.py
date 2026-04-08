# coding: utf-8
"""
服务端全局状态模块

提供服务端运行时的全局共享状态，包括 WebSocket 连接池和消息队列。
使用类变量实现全局状态，方便跨模块访问。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from multiprocessing import Queue, Process
from typing import Dict, List, Optional, Any

import websockets
from rich.console import Console

from util.server.schema import Result, RecognitionSession

# Rich console 用于控制台输出（服务端统一使用此实例）
console = Console(highlight=False)


@dataclass
class ServerContext:
    """
    服务端全局上下文容器
    
    存储服务端运行时的共享状态：
    - sockets: WebSocket 连接字典，以 socket_id 为键
    - sockets_id: 跨进程的 socket ID 列表（由 Manager 创建）
    - queue_in: 任务输入队列（主进程 -> 识别进程）
    - queue_out: 结果输出队列（识别进程 -> 主进程）
    - recognize_process: 识别子进程句柄
    - sessions: 活跃识别会话，以 task_id 为键
    """
    # WebSocket 连接池
    sockets: Dict[str, websockets.WebSocketClientProtocol] = field(default_factory=dict)
    
    # 跨进程共享的 socket ID 列表（需要用 Manager().list() 初始化）
    sockets_id: Optional[List] = None
    
    # 消息队列
    queue_in: Queue = field(default_factory=Queue)
    queue_out: Queue = field(default_factory=Queue)

    # 识别子进程
    recognize_process: Optional[Process] = None

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


# 全局状态实例
_global_context: Optional[ServerContext] = None


def get_context() -> ServerContext:
    """
    获取全局服务端上下文实例
    
    如果尚未初始化，则创建新实例。
    """
    global _global_context
    if _global_context is None:
        _global_context = ServerContext()
    return _global_context