# coding: utf-8
"""
热词模块

提供热词替换和纠错功能，包括：
- PhonemeCorrector: 基于音素的纠错器
- RuleCorrector: 基于规则表达式的纠错器
- HotwordManager: 热词管理器（单例）
"""

from .. import logger


from .hot_phoneme import PhonemeCorrector, CorrectionResult
from .hot_rule import RuleCorrector
__all__ = [
    'PhonemeCorrector',
    'CorrectionResult',
    'RuleCorrector',
    'logger',
]
