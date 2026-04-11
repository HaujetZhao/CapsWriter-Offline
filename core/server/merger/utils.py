# coding: utf-8
"""
Token 处理工具函数

提供对识别结果中的 Token 列表进行基础处理的辅助方法。
"""

from typing import List, Tuple
from core.constants import Punctuation
from . import logger



def process_tokens_safely(tokens: List) -> List[str]:
    """
    安全处理 tokens，过滤无效 UTF-8 编码
    
    Args:
        tokens: 原始 token 列表
        
    Returns:
        清理后的字符串 token 列表
    """
    clean_tokens = []
    for token in tokens:
        if isinstance(token, bytes):
            token = token.decode('utf-8', errors='ignore')
        clean_tokens.append(token)
    return clean_tokens


def tokens_to_text(tokens: List[str]) -> str:
    """
    将 tokens 序列化为最终显示文本
    
    处理 Paraformer 特有的 @@ 标记（表示后续 token 应直接拼接）。
    对于现代模型（如 Fun-ASR-Nano），空格本身通常已存在于 token 列表中。
    
    Args:
        tokens: token 列表
        
    Returns:
        合并后的完整文本
    """
    return "".join(tokens).replace('@@', '')


def remove_trailing_punctuation(
    tokens: List[str], 
    timestamps: List[float]
) -> Tuple[List[str], List[float]]:
    """
    移除末尾的标点符号
    
    常用于某些模型在片段末尾产生的重复或不必要的标点。
    
    Args:
        tokens: token 列表
        timestamps: 时间戳列表
        
    Returns:
        (处理后的 tokens, 处理后的 timestamps)
    """
    if tokens and tokens[-1] in Punctuation.ALL:
        logger.debug(f"移除末尾标点: '{tokens[-1]}'")
        return tokens[:-1], timestamps[:-1] if timestamps else timestamps
    return tokens, timestamps
