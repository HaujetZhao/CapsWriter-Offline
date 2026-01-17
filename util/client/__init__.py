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

# 核心模块
from util.client.state import ClientState, get_state, console
from util.client.websocket_manager import WebSocketManager

# 音频模块
from util.client.audio import AudioRecorder, AudioStreamManager, AudioFileManager

# 快捷键模块
from util.client.shortcut import Shortcut, ShortcutManager

# 输出模块
from util.client.output import ResultProcessor, TextOutput

# 转录模块
from util.client.transcribe import FileTranscriber, SrtAdjuster

# 日记模块
from util.client.diary import DiaryWriter

# UI 模块
from util.client.ui import TipsDisplay

__all__ = [
    # 核心
    'ClientState',
    'get_state',
    'console',
    'WebSocketManager',
    
    # 音频
    'AudioRecorder',
    'AudioStreamManager',
    'AudioFileManager',
    
    # 快捷键
    'Shortcut',
    'ShortcutManager',
    
    # 输出
    'ResultProcessor',
    'TextOutput',
    
    # 转录
    'FileTranscriber',
    'SrtAdjuster',
    
    # 日记
    'DiaryWriter',
    
    # UI
    'TipsDisplay',
]

