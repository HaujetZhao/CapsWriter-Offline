# coding: utf-8
"""
基于时间戳对齐的 Token 拼接算法

使用 SequenceMatcher 进行精确的字级对齐，适用于字幕生成等对时间戳要求高的场景。
"""

from __future__ import annotations
import difflib
from typing import List, Tuple
from core.constants import Punctuation
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
    使用 SequenceMatcher 进行 token 级别拼接

    算法：
    1. 将 prev 尾部和 new 头部的 tokens 拼成文本
    2. 用 SequenceMatcher 找到所有公共子串，加位置约束选最佳
    3. 将匹配点映射回 token 索引，执行拼接

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
    # 转换新片段时间戳为全局时间
    new_global_timestamps = [t + offset for t in new_timestamps]

    if is_first_segment or not prev_tokens:
        return new_tokens, new_global_timestamps
    if not new_tokens:
        return prev_tokens, prev_timestamps

    # 1. 提取 prev 尾部和 new 头部的文本（基于 overlap 动态确定范围）
    #    重叠区域的字符数估计：overlap 秒 × 约 5 字/秒
    overlap_char_estimate = max(int(overlap * 5), 20)
    prev_tail_len = min(len(prev_tokens), overlap_char_estimate * 3)
    new_head_len = min(len(new_tokens), overlap_char_estimate * 3)

    prev_tail_text = "".join(prev_tokens[-prev_tail_len:])
    new_head_text = "".join(new_tokens[:new_head_len])

    # 2. 寻找最佳对齐
    best = _find_best_token_overlap(prev_tail_text, new_head_text)

    if best is None:
        logger.debug("Token 拼接: 未找到重叠，直接拼接")
        return _fallback_merge(prev_tokens, prev_timestamps, new_tokens, new_global_timestamps, offset)

    match_pos_prev, match_pos_new, match_len = best

    # 3. 将字符位置映射回 token 索引
    prev_cut = _char_pos_to_token_idx(
        prev_tokens, len(prev_tokens) - prev_tail_len,
        match_pos_prev + match_len  # prev 保留到匹配终点
    )
    new_start = _char_pos_to_token_idx(
        new_tokens, 0,
        match_pos_new + match_len  # new 从匹配终点之后开始
    )

    # 4. 执行拼接
    result_tokens = prev_tokens[:prev_cut] + new_tokens[new_start:]
    result_timestamps = prev_timestamps[:prev_cut] + new_global_timestamps[new_start:]

    logger.debug(
        f"Token 拼接: 匹配长度 {match_len}, "
        f"prev 截断 token[{prev_cut}], new 起始 token[{new_start}]"
    )

    # 5. 后处理：清理连续重复标点
    return _clean_repeated_punct(result_tokens, result_timestamps)


def _find_best_token_overlap(prev_tail: str, new_head: str) -> tuple[int, int, int] | None:
    """
    在 prev_tail 和 new_head 之间找最佳对齐（与 text_merger 相同策略）。

    位置约束：匹配终点在 prev_tail 后半段，匹配起点在 new_head 前半段。
    """
    min_match = 2

    sm = difflib.SequenceMatcher(None, prev_tail, new_head, autojunk=False)
    matches = sm.get_matching_blocks()

    tail_end_threshold = len(prev_tail) // 4 * 3
    head_start_threshold = len(new_head) // 4

    candidates = [
        (a, b, size) for a, b, size in matches
        if size >= min_match and a + size > tail_end_threshold and b <= head_start_threshold
    ]
    if not candidates:
        return None

    def score(item):
        a, b, size = item
        return size * size + a - b

    return max(candidates, key=score)


def _char_pos_to_token_idx(tokens: List[str], base_offset: int, char_pos: int) -> int:
    """
    将字符位置映射回 token 索引（全局）。

    从 base_offset 开始累计字符数，找到 >= char_pos 的 token 边界。
    """
    char_count = 0
    for i in range(base_offset, len(tokens)):
        if char_count >= char_pos:
            return i
        char_count += len(tokens[i])
    return len(tokens)


def _fallback_merge(
    prev_tokens, prev_timestamps, new_tokens, new_global_timestamps, offset
) -> Tuple[List[str], List[float]]:
    """兜底：基于时间戳硬拼接"""
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
    return result_tokens, result_timestamps


def _clean_repeated_punct(
    tokens: List[str], timestamps: List[float]
) -> Tuple[List[str], List[float]]:
    """清理连续重复标点"""
    puncs = set(Punctuation.ALL + " ")
    clean_tokens = []
    clean_timestamps = []
    for token, ts in zip(tokens, timestamps):
        if clean_tokens and token in puncs and clean_tokens[-1] == token:
            continue
        clean_tokens.append(token)
        clean_timestamps.append(ts)
    return clean_tokens, clean_timestamps
