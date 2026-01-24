# coding: utf-8
"""
文本拼接模块

提供简单文本拼接和时间戳拼接的工具函数。
"""

import re
from typing import List, Tuple

from util.constants import TextMerge, Punctuation
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


def merge_tokens_by_sequence_matcher(
    prev_tokens: List[str],
    prev_timestamps: List[float],
    new_tokens: List[str],
    new_timestamps: List[float],
    offset: float,
    overlap: float,
    is_first_segment: bool = False
) -> Tuple[List[str], List[float]]:
    """
    使用 SequenceMatcher 进行精确的 token 级别拼接
    
    算法：
    1. 提取 prev 和 new 在重叠区域的 tokens
    2. 使用 SequenceMatcher 找到最长公共子序列
    3. 在匹配点截断 prev，拼接 new 从匹配点开始的部分
    
    Args:
        prev_tokens: 之前累积的 tokens
        prev_timestamps: 之前累积的时间戳（全局时间）
        new_tokens: 新片段的 tokens
        new_timestamps: 新片段的时间戳（片段内相对时间）
        offset: 当前片段的全局起始偏移
        overlap: 重叠时间（秒）
        is_first_segment: 是否为第一个片段
        
    Returns:
        (合并后的 tokens, 合并后的时间戳)
    """
    import difflib
    
    # 转换新片段时间戳为全局时间
    new_global_timestamps = [t + offset for t in new_timestamps]
    
    # 如果是第一个片段，直接返回
    if is_first_segment or not prev_tokens:
        return new_tokens, new_global_timestamps
    
    if not new_tokens:
        return prev_tokens, prev_timestamps
    
    # 标点集合，用于后处理
    from util.constants import Punctuation
    puncs = set(Punctuation.ALL + " ")
    
    # 1. 提取重叠区域
    # prev 的重叠区：时间戳 >= offset - 1.0 的部分
    overlap_start_time = offset - 1.0
    prev_overlap_indices = [i for i, t in enumerate(prev_timestamps) if t >= overlap_start_time]
    prev_overlap_tokens = [prev_tokens[i] for i in prev_overlap_indices]
    prev_overlap_text = "".join(prev_overlap_tokens)
    
    # new 的重叠区：时间戳 <= overlap + 1.0 的部分
    overlap_end_time = overlap + 1.0
    new_overlap_indices = [i for i, t in enumerate(new_timestamps) if t <= overlap_end_time]
    new_overlap_tokens = [new_tokens[i] for i in new_overlap_indices]
    new_overlap_text = "".join(new_overlap_tokens)
    
    # 2. 使用 SequenceMatcher 寻找最佳对齐
    sm = difflib.SequenceMatcher(None, prev_overlap_text, new_overlap_text)
    match = sm.find_longest_match(0, len(prev_overlap_text), 0, len(new_overlap_text))
    
    if match.size >= 2:  # 至少匹配上 2 个字符
        # a. 找到 prev 的截断点
        # match.a 是 prev_overlap_text 中的字符索引
        # 我们需要将其映射回 prev_overlap_indices
        char_count = 0
        prev_cut_local_idx = 0
        for idx, token in enumerate(prev_overlap_tokens):
            if char_count >= match.a:
                prev_cut_local_idx = idx
                break
            char_count += len(token)
        else:
            prev_cut_local_idx = len(prev_overlap_tokens)
        
        # 转换为全局索引
        if prev_overlap_indices and prev_cut_local_idx < len(prev_overlap_indices):
            prev_cut_global_idx = prev_overlap_indices[prev_cut_local_idx]
        else:
            prev_cut_global_idx = len(prev_tokens)
        
        # b. 找到 new 的起始点
        # match.b 是 new_overlap_text 中的字符索引
        char_count = 0
        new_start_local_idx = 0
        for idx, token in enumerate(new_overlap_tokens):
            if char_count >= match.b:
                new_start_local_idx = idx
                break
            char_count += len(token)
        else:
            new_start_local_idx = len(new_overlap_tokens)
        
        # 转换为全局索引
        if new_overlap_indices and new_start_local_idx < len(new_overlap_indices):
            new_start_global_idx = new_overlap_indices[new_start_local_idx]
        else:
            new_start_global_idx = 0
        
        # c. 执行拼接
        result_tokens = prev_tokens[:prev_cut_global_idx] + new_tokens[new_start_global_idx:]
        result_timestamps = prev_timestamps[:prev_cut_global_idx] + new_global_timestamps[new_start_global_idx:]
        
        logger.debug(
            f"SequenceMatcher 拼接: 匹配长度 {match.size}, "
            f"prev 截断位置 {prev_cut_global_idx}, "
            f"new 起始位置 {new_start_global_idx}"
        )
        
    else:
        # 兜底：基于时间戳硬拼接
        last_time = prev_timestamps[-1] if prev_timestamps else offset
        new_start_idx = 0
        for i, t in enumerate(new_global_timestamps):
            if t > last_time + 0.1:
                new_start_idx = i
                break
        else:
            new_start_idx = len(new_tokens)
        
        result_tokens = prev_tokens + new_tokens[new_start_idx:]
        result_timestamps = prev_timestamps + new_global_timestamps[new_start_idx:]
        
        logger.debug(f"时间戳兜底拼接: 从 new[{new_start_idx}] 开始")
    
    # 3. 后处理：清理连续重复标点
    clean_tokens = []
    clean_timestamps = []
    for token, ts in zip(result_tokens, result_timestamps):
        if clean_tokens and token in puncs and clean_tokens[-1] == token:
            continue
        clean_tokens.append(token)
        clean_timestamps.append(ts)
    
    return clean_tokens, clean_timestamps



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
    # 直接拼接所有 token，仅处理 Paraformer 的 @@ 标记
    # 对于现代模型（如 Fun-ASR-Nano），空格本身就是作为独立 token 存在的
    text = "".join(tokens).replace('@@', '')
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
