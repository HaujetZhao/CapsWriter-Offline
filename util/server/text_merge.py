# coding: utf-8
"""
文本拼接模块

提供简单文本拼接和时间戳拼接的工具函数。
"""

import re
from typing import List, Tuple

from util.constants import TextMerge, Punctuation
from util.logger import get_logger

logger = get_logger('server')


def _fuzzy_match(s1: str, s2: str, max_errors: int) -> bool:
    """
    模糊匹配：允许最多 max_errors 个字符不同
    
    使用简单的字符比较，允许一定数量的错误。
    
    Args:
        s1: 字符串1
        s2: 字符串2  
        max_errors: 允许的最大错误数
        
    Returns:
        是否匹配（错误数 <= max_errors）
    """
    if len(s1) != len(s2):
        return False
    
    errors = sum(1 for c1, c2 in zip(s1, s2) if c1 != c2)
    return errors <= max_errors


def _find_fuzzy_overlap(tail: str, new_text: str, max_errors: int) -> int:
    """
    在 tail 末尾和 new_text 开头寻找模糊重叠
    
    从长到短尝试匹配，允许 max_errors 个字符错误。
    
    重要约束：匹配长度必须 > max_errors，否则错误率会超过 50%，
    导致几乎任何内容都能匹配。
    
    Args:
        tail: prev_text 的末尾部分
        new_text: 新文本
        max_errors: 允许的最大错误数
        
    Returns:
        匹配长度（0 表示未找到匹配）
    """
    # 最小匹配长度：必须大于容错数，确保正确字符多于错误字符
    min_match_len = max_errors + 2  # 至少比容错多2个字符
    
    for match_len in range(min(len(tail), len(new_text)), min_match_len - 1, -1):
        tail_part = tail[-match_len:]
        new_part = new_text[:match_len]
        
        if _fuzzy_match(tail_part, new_part, max_errors):
            return match_len
    
    return 0


def merge_by_text(
    prev_text: str, 
    new_text: str, 
    overlap_chars: int = TextMerge.OVERLAP_CHARS,
    error_tolerance: int = TextMerge.ERROR_TOLERANCE
) -> str:
    """
    基于文本重叠进行拼接（不依赖时间戳）
    
    通过在 prev_text 末尾和 new_text 开头寻找重叠来去重拼接。
    支持容错匹配：允许 error_tolerance 个字符错误。
    
    容错场景举例：
    - 音频截断在字的中间，导致开头/末尾有错字
    - 前后语境不同导致的生成错误
    
    Args:
        prev_text: 之前累积的文本
        new_text: 新识别的文本
        overlap_chars: 在末尾/开头查找重叠的字符数
        error_tolerance: 允许的错误字符数
        
    Returns:
        合并后的文本
    """
    if not prev_text:
        return new_text
    if not new_text:
        return prev_text
    
    # 去除 prev_text 末尾的标点符号（用于匹配）
    prev_for_match = prev_text.rstrip(Punctuation.ALL)
    # 去除 new_text 开头的标点符号（用于匹配）
    new_stripped_count = 0
    new_for_match = new_text
    while new_for_match and new_for_match[0] in Punctuation.ALL:
        new_for_match = new_for_match[1:]
        new_stripped_count += 1
    
    # 取 prev_for_match 末尾 N 个字符
    tail = prev_for_match[-overlap_chars:] if len(prev_for_match) >= overlap_chars else prev_for_match
    
    # 先尝试精确匹配
    for match_len in range(min(len(tail), len(new_for_match)), 0, -1):
        if tail[-match_len:] == new_for_match[:match_len]:
            # 匹配成功，计算实际需要保留的 prev_text 长度
            # prev_text 保留到匹配点（去掉末尾标点和重叠部分）
            keep_len = len(prev_for_match) - match_len
            logger.debug(f"文本拼接: 精确匹配 {match_len} 字符")
            return prev_text[:keep_len] + new_text[new_stripped_count:]
    
    # 精确匹配失败，尝试模糊匹配
    if error_tolerance > 0:
        match_len = _find_fuzzy_overlap(tail, new_for_match, error_tolerance)
        if match_len > 0:
            keep_len = len(prev_for_match) - match_len
            logger.debug(f"文本拼接: 模糊匹配 {match_len} 字符 (容错={error_tolerance})")
            return prev_text[:keep_len] + new_text[new_stripped_count:]
    
    # 未找到重叠，直接拼接
    logger.debug("文本拼接: 未找到重叠，直接拼接")
    return prev_text + new_text


def calculate_timestamp_boundaries(
    timestamps: List[float], 
    overlap: float, 
    duration: float,
    is_first_segment: bool,
    is_final: bool
) -> Tuple[int, int]:
    """
    根据时间戳计算去重边界
    
    通过分析重叠区域的时间戳，确定有效 token 的起止索引。
    
    Args:
        timestamps: 当前片段的时间戳列表
        overlap: 重叠时间（秒）
        duration: 片段总时长（秒）
        is_first_segment: 是否为第一个片段
        is_final: 是否为最后一个片段
        
    Returns:
        (start_index, end_index) 有效 token 的起止索引
    """
    n_tokens = len(timestamps)
    start_idx = n_tokens
    end_idx = n_tokens
    
    # 找到起始边界
    for i, ts in enumerate(timestamps):
        if ts > overlap / 2:
            start_idx = i
            break
    
    # 找到结束边界
    for i, ts in enumerate(timestamps, start=1):
        end_idx = i
        if ts > duration - overlap / 2:
            break
    
    # 特殊处理
    if is_first_segment:
        start_idx = 0
    if is_final:
        end_idx = n_tokens
    
    logger.debug(
        f"时间戳边界: start={start_idx}, end={end_idx}, "
        f"tokens={n_tokens}, overlap={overlap:.2f}s"
    )
    
    return start_idx, end_idx


def deduplicate_at_boundary(
    prev_tokens: List[str],
    new_tokens: List[str],
    new_timestamps: List[float]
) -> Tuple[List[str], List[float]]:
    """
    在片段边界处进行细粒度去重
    
    检查新片段开头是否与前一片段末尾有重复 token。
    
    Args:
        prev_tokens: 之前累积的 tokens
        new_tokens: 新片段的 tokens
        new_timestamps: 新片段的 timestamps
        
    Returns:
        (去重后的 tokens, 去重后的 timestamps)
    """
    if not prev_tokens or not new_tokens:
        return new_tokens, new_timestamps
    
    skip = 0
    if prev_tokens[-2:] == new_tokens[:2]:
        skip = 2
    elif prev_tokens[-1:] == new_tokens[:1]:
        skip = 1
    
    if skip > 0:
        logger.debug(f"边界去重: 跳过 {skip} 个重复 token")
        return new_tokens[skip:], new_timestamps[skip:]
    
    return new_tokens, new_timestamps


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
    将 tokens 合并为文本
    
    处理 Paraformer 的 @@ 标记（表示后续 token 应直接拼接）。
    
    Args:
        tokens: token 列表
        
    Returns:
        合并后的文本
    """
    # 处理 @@ 标记：表示与下一个 token 直接拼接（无空格）
    text = ' '.join(tokens).replace('@@ ', '')
    # 非英文数字后面的空格去掉
    text = re.sub('([^a-zA-Z0-9]) (?![a-zA-Z0-9])', r'\1', text)
    return text


def remove_trailing_punctuation(
    tokens: List[str], 
    timestamps: List[float]
) -> Tuple[List[str], List[float]]:
    """
    移除末尾的标点符号
    
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
