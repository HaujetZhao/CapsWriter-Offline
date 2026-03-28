# coding: utf-8
"""
基于时间戳对齐的 Token 拼接算法

使用 SequenceMatcher 进行精确的字级对齐，适用于字幕生成等对时间戳要求高的场景。
"""

import difflib
from typing import List, Tuple
from util.constants import Punctuation
from . import logger


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

