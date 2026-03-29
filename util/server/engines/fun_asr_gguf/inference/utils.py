"""
FunASR-GGUF 通用工具函数
"""

import time
from typing import Any, Callable, Tuple

from . import logger

def timer(func: Callable, *args, **kwargs) -> Tuple[Any, float]:
    """
    执行函数并返回其结果与耗时（秒）。
    用法:
        result, elapsed = timer(my_func, arg1, arg2, kwarg=val)
    """
    start = time.perf_counter()
    res = func(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return res, elapsed

def vprint(message: str, verbose: bool = True):
    """条件输出：仅在 verbose=True 时输出到控制台，并始终记录到日志"""
    if verbose:
        print(message)
    # 始终记录到日志系统，方便排查问题
    logger.info(message)

def format_ms(seconds: float) -> str:
    """将秒转换为毫秒字符串"""
    return f"{seconds * 1000:5.0f}ms"
