# coding: utf-8
"""
processing 子模块

包含识别结果处理相关功能。
"""

from util.client.processing.result_processor import ResultProcessor
from util.client.processing.hotword import HotwordManager
from util.client.processing.output import TextOutput

__all__ = [
    'ResultProcessor',
    'HotwordManager',
    'TextOutput',
]
