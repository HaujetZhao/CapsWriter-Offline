# coding: utf-8
"""
基于文本重叠的拼接算法

提供鲁棒的文本层级合并功能，不依赖时间戳。
"""

import re
from core.constants import TextMerge, Punctuation
from . import logger


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

