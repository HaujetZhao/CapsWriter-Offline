# coding: utf-8
"""
audio 子模块

包含音频录制、音频流管理和音频文件管理功能。
"""

from .. import logger
from core.client.audio.recorder import AudioRecorder
from core.client.audio.stream import AudioStreamManager
from core.client.audio.file_manager import AudioFileManager

__all__ = [
    'logger',
    'AudioRecorder',
    'AudioStreamManager',
    'AudioFileManager',
]
