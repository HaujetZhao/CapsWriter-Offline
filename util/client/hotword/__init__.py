# coding: utf-8
"""
热词模块

提供热词替换和纠错功能，包括：
- PhonemeCorrector: 基于音素的纠错器
- RuleCorrector: 基于规则表达式的纠错器
- RectificationRAG: 纠错历史检索器
- HotwordManager: 热词管理器（单例）
"""

from util import get_logger
logger = get_logger('client')


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
    'init_hotword_system',
]


def init_hotword_system():
    """初始化热词系统（加载词典并启动监控）"""
    from pathlib import Path
    from config_client import ClientConfig as Config
    
    logger.info("正在加载热词...")
    hotword_files = {
        'hot': Path('hot.txt'),
        'rule': Path('hot-rule.txt'),
        'rectify': Path('hot-rectify.txt'),
    }
    manager = get_hotword_manager(
        hotword_files=hotword_files,
        threshold=Config.hot_thresh,
        similar_threshold=Config.hot_similar,
        rectify_threshold=Config.hot_rectify
    )
    manager.load_all()
    manager.start_file_watcher()
