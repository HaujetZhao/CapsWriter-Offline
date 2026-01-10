# coding: utf-8
"""
服务端模块

提供 CapsWriter 服务端的所有功能模块。

模块架构：
- server_cosmic: 全局状态管理（连接池、消息队列）
- server_classes: 数据类定义（Task、Result）
- server_check_model: 模型文件检查
- server_init_recognizer: 识别器初始化和主循环
- server_recognize: 语音识别处理
- server_ws_recv: WebSocket 接收处理
- server_ws_send: WebSocket 发送处理
"""

from util.server.server_cosmic import Cosmic, console
from util.server.server_classes import Task, Result

__all__ = [
    'Cosmic',
    'console',
    'Task',
    'Result',
]
