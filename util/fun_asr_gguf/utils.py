"""
FunASR-GGUF 通用工具函数
"""

from typing import Any

def vprint(message: str, verbose: bool = True):
    """条件打印：仅在 verbose=True 时打印"""
    if verbose:
        print(message)

def format_ms(seconds: float) -> str:
    """将秒转换为毫秒字符串"""
    return f"{seconds * 1000:5.0f}ms"
