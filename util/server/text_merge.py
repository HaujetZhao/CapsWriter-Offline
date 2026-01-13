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
    基于文本重叠进行鲁棒拼接
    
    算法优化：
    不再要求重叠必须在 prev_text 的绝对末尾。
    而是在 prev_text 的末尾窗口内寻找 new_text 的最长匹配前缀。
    如果发现匹配，则以匹配点为界进行拼接，丢弃 prev_text 匹配点之后的“尾部噪音”。
    
    Args:
        prev_text: 之前累积的文本
        new_text: 新识别的文本
        overlap_chars: 查找重叠的后端窗口大小
        error_tolerance: 容错字符数
    """
    if not prev_text:
        return new_text
    if not new_text:
        return prev_text
    
    # 1. 预处理：提取用于匹配的纯文本（去掉两端标点）
    prev_clean = prev_text.rstrip(Punctuation.ALL)
    
    # 记录 new_text 开头被去掉的标点数量，用于最终拼接
    new_match_start = 0
    while new_match_start < len(new_text) and new_text[new_match_start] in Punctuation.ALL:
        new_match_start += 1
    new_clean = new_text[new_match_start:]
    
    if not prev_clean or not new_clean:
        return prev_text + new_text

    # 2. 确定搜索窗口（prev_text 的末尾部分）
    search_window = prev_clean[-overlap_chars:]
    window_offset = len(prev_clean) - len(search_window)

    # 3. 寻找最长匹配重叠
    # 策略：不仅搜 new_clean 的绝对开头，还允许跳过 new_clean 开头的几个字（处理开头截断不准）
    max_skip_new = 10  # 允许跳过新片段开头的字数
    max_to_check = min(len(search_window), len(new_clean))
    min_exact_len = 2
    min_fuzzy_len = error_tolerance + 2

    best_match_skip_new = -1
    best_match_pos_in_window = -1
    best_match_len = 0

    # 3.1 尝试【精确匹配】
    # 优先级：匹配越长越好 > 跳过越少越好 > 越靠近 prev 尾部越好
    for match_len in range(max_to_check, min_exact_len - 1, -1):
        for skip_new in range(min(max_skip_new, len(new_clean) - match_len + 1)):
            target_prefix = new_clean[skip_new : skip_new + match_len]
            idx = search_window.rfind(target_prefix)
            if idx != -1:
                best_match_skip_new = skip_new
                best_match_pos_in_window = idx
                best_match_len = match_len
                break
        if best_match_len > 0:
            break
            
    # 3.2 如果没找到精确匹配，且开启了容错，则尝试【模糊匹配】
    if best_match_len == 0 and error_tolerance > 0:
        for match_len in range(max_to_check, min_fuzzy_len - 1, -1):
            for skip_new in range(min(max_skip_new, len(new_clean) - match_len + 1)):
                target_prefix = new_clean[skip_new : skip_new + match_len]
                found_idx = -1
                for i in range(len(search_window) - match_len, -1, -1):
                    if _fuzzy_match(search_window[i:i+match_len], target_prefix, error_tolerance):
                        found_idx = i
                        break
                if found_idx != -1:
                    best_match_skip_new = skip_new
                    best_match_pos_in_window = found_idx
                    best_match_len = match_len
                    break
            if best_match_len > 0:
                break

    # 4. 执行拼接
    if best_match_len > 0:
        # prev_text 保留到匹配开始的地方
        keep_prev_len = window_offset + best_match_pos_in_window
        
        # 衔接点：跳过 new_text 开头的标点以及我们认为多余的 skip_new 个噪音字
        res_prev = prev_clean[:keep_prev_len]
        res_new = new_text[new_match_start + best_match_skip_new:]
        
        discard_prev = len(prev_clean) - keep_prev_len - best_match_len
        logger.debug(
            f"文本拼接成功: 匹配长度 {best_match_len}, "
            f"丢弃 prev 尾部噪音 {discard_prev} 字, "
            f"跳过 new 开头噪音 {best_match_skip_new} 字"
        )
        return res_prev + res_new
    
    # 5. 未找到匹配，兜底逻辑
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
