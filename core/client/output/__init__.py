# coding: utf-8
"""
output 子模块

包含识别结果输出相关功能。
"""

from .. import logger
from core.client.output.result_processor import ResultProcessor
from core.client.output.text_output import TextOutput

__all__ = [
    'logger',
    'ResultProcessor',
    'TextOutput',
]
