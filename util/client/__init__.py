# coding: utf-8
"""
客户端模块

提供 CapsWriter 客户端的所有功能模块。

模块架构：
- state: 客户端状态管理
- websocket_manager: WebSocket 连接管理
- audio/: 音频相关（录制、流、文件管理）
- input/: 输入处理（快捷键）
- processing/: 结果处理（热词、输出）
- transcribe/: 文件转录
- diary/: 日记写入
- ui/: 用户界面
"""

# 核心模块
from util.client.state import ClientState, get_state, console
from util.client.websocket_manager import WebSocketManager

# 音频模块
from util.client.audio import AudioRecorder, AudioStreamManager, AudioFileManager

# 输入模块
from util.client.input import Shortcut, ShortcutManager

# 处理模块
from util.client.processing import ResultProcessor, HotwordManager, TextOutput

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
    
    # 输入
    'Shortcut',
    'ShortcutManager',
    
    # 处理
    'ResultProcessor',
    'HotwordManager',
    'TextOutput',
    
    # 转录
    'FileTranscriber',
    'SrtAdjuster',
    
    # 日记
    'DiaryWriter',
    
    # UI
    'TipsDisplay',
]
