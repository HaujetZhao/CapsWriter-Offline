# coding: utf-8
"""
文本处理器模块

提供识别结果的后期加工功能，包括格式化、标点补全、ITN转换等。
"""

from .. import logger
from .text_formatter import TextFormatter

__all__ = ['TextFormatter']
