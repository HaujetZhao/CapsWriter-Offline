# coding: utf-8
"""
服务端状态管理模块
"""
from dataclasses import dataclass
from typing import Optional, Any
from multiprocessing import Process
import threading

@dataclass
class ServerState:
    """
    服务端运行状态
    """
    recognize_process: Optional[Process] = None

# 模块级全局实例 (Python 模块天生是单例)
_global_state = ServerState()

def get_state() -> ServerState:
    return _global_state
