# coding: utf-8
"""
热词模块

提供热词替换和纠错功能，包括：
- PhonemeCorrector: 基于音素的纠错器
- RuleCorrector: 基于规则表达式的纠错器
- RectificationRAG: 纠错历史检索器
- HotwordManager: 热词管理器（单例）
"""

import logging

# 使用主模块的 logger
logger = logging.getLogger("fun_asr_gguf.hotword")


from .hot_phoneme import PhonemeCorrector, CorrectionResult
from .hot_rule import RuleCorrector
from .hot_rectification import RectificationRAG
from .manager import HotwordManager, get_hotword_manager


__all__ = [
    'PhonemeCorrector',
    'CorrectionResult',
    'RuleCorrector',
    'RectificationRAG',
    'HotwordManager',
    'get_hotword_manager',
    'logger',
]
