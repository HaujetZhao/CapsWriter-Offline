"""
FunASR-GGUF 通用工具函数
"""

from typing import Any

from . import logger

def vprint(message: str, verbose: bool = True):
    """条件输出：仅在 verbose=True 时输出到控制台，并始终记录到日志"""
    if verbose:
        print(message)
    # 始终记录到日志系统，方便排查问题
    logger.info(message)

def format_ms(seconds: float) -> str:
    """将秒转换为毫秒字符串"""
    return f"{seconds * 1000:5.0f}ms"
