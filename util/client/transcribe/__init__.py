# coding: utf-8
"""
transcribe 子模块

包含文件转录功能。
"""

from .. import logger
from util.client.transcribe.file_transcriber import FileTranscriber
from util.client.transcribe.srt_adjuster import SrtAdjuster

__all__ = [
    'logger',
    'FileTranscriber',
    'SrtAdjuster',
]
