# coding: utf-8
"""
客户端模块

提供 CapsWriter 客户端的所有功能模块。

模块架构：
- state: 客户端状态管理
- websocket_manager: WebSocket 连接管理
- audio/: 音频相关（录制、流、文件管理）
- shortcut/: 快捷键处理（原 input/）
- output/: 结果处理和输出（原 processing/）
- udp/: UDP 控制
- transcribe/: 文件转录
- diary/: 日记写入
- ui/: 用户界面
"""

from util import get_logger
logger = get_logger('client')

# 门面类
from util.client.app import CapsWriterClient

__all__ = [
    'CapsWriterClient',
]

