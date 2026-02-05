# coding: utf-8
"""
服务端全局状态模块

提供服务端运行时的全局共享状态，包括 WebSocket 连接池和消息队列。
使用类变量实现全局状态，方便跨模块访问。
"""

from multiprocessing import Queue
from typing import Dict, List, Optional

import websockets

from util.common.safe_console import create_safe_console

# Rich console 用于控制台输出（服务端统一使用此实例）
console = create_safe_console(highlight=False)


class Cosmic:
    """
    服务端全局状态容器
    
    存储服务端运行时的共享状态：
    - sockets: WebSocket 连接字典，以 socket_id 为键
    - sockets_id: 跨进程的 socket ID 列表（由 Manager 创建）
    - queue_in: 任务输入队列（主进程 -> 识别进程）
    - queue_out: 结果输出队列（识别进程 -> 主进程）
    
    Note:
        使用类变量而非实例变量，确保全局唯一。
        sockets_id 需要在 core_server.py 中使用 Manager().list() 初始化。
    """
    # WebSocket 连接池
    sockets: Dict[str, websockets.WebSocketClientProtocol] = {}
    
    # 跨进程共享的 socket ID 列表（需要用 Manager().list() 初始化）
    sockets_id: Optional[List] = None
    
    # 消息队列
    queue_in: Queue = Queue()
    queue_out: Queue = Queue()
