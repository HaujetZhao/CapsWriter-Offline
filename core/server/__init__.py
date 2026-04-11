# coding: utf-8
"""
服务端模块

提供 CapsWriter 服务端的所有功能模块。

模块架构：
- context: 全局上下文管理（连接池、消息队列）
- schema: 数据类定义（Task, Result）
- check_model: 模型文件检查
- worker: 识别工作进程入口 (由 init_recognizer 处理)
- recognize: 语音识别核心流程
- ws_recv: WebSocket 接收处理
- ws_send: WebSocket 发送处理
"""

from core.server.state import console
from core.logger import get_logger, setup_logger
from config_server import ServerConfig as Config, __version__

setup_logger('server', level=Config.log_level)
logger = get_logger('server')

from core.server.schema import Task, Result

__all__ = [
    'console',
    'logger',
    'Task',
    'Result',
]
