# coding: utf-8
"""
基于文本重叠的拼接算法

提供鲁棒的文本层级合并功能，不依赖时间戳。
使用 difflib 自动寻找最佳对齐点，无需固定窗口大小。
"""

from __future__ import annotations
import difflib
from core.constants import Punctuation
from . import logger


def merge_by_text(
    prev_text: str,
    new_text: str,
    *_args,
    **_kwargs,
) -> str:
    """
    基于文本重叠进行鲁棒拼接

    算法：在 prev_text 尾部和 new_text 头部寻找最佳对齐点。
    使用多尺度匹配策略：先尝试长精确匹配，再逐步放宽。
    约束匹配必须在 prev 尾部（匹配点越靠后越好）。
    """
    if not prev_text:
        return new_text
    if not new_text:
        return prev_text

    # 1. 预处理：去掉两端标点，避免标点差异干扰匹配
    prev_clean = prev_text.rstrip(Punctuation.ALL)

    new_start = 0
    while new_start < len(new_text) and new_text[new_start] in Punctuation.ALL:
        new_start += 1
    new_clean = new_text[new_start:]

    if not prev_clean or not new_clean:
        return prev_text + new_text

    # 2. 在 prev 尾部和 new 头部寻找对齐
    #    搜索范围：prev 最后 100 字 + new 前 100 字
    tail = prev_clean[-100:]
    head = new_clean[:100]

    best = _find_best_overlap(tail, head)

    # 最短匹配长度要求
    if best is None:
        logger.debug("文本拼接: 未找到重叠，直接拼接")
        return prev_text + new_text

    match_pos_in_tail, match_pos_in_head, match_len = best

    # 3. 在匹配点处拼接
    #    prev 保留到匹配起点 + 匹配长度（含重叠部分），new 从匹配终点之后续接
    keep_prev_len = len(prev_clean) - len(tail) + match_pos_in_tail + match_len
    skip_new_len = match_pos_in_head + match_len

    res_prev = prev_clean[:keep_prev_len]
    res_new = new_text[new_start + skip_new_len:]

    discarded_prev = len(prev_clean) - keep_prev_len - match_len
    logger.debug(
        f"文本拼接成功: 匹配长度 {match_len}, "
        f"丢弃 prev 尾部 {discarded_prev} 字, "
        f"跳过 new 开头 {skip_new_len} 字"
    )
    return res_prev + res_new


def _find_best_overlap(tail: str, head: str) -> tuple[int, int, int] | None:
    """
    在 tail（prev 尾部）和 head（new 头部）之间找最佳对齐。

    核心约束：合法的重叠必须出现在 tail 的后半段 + head 的前半段。
    匹配越靠近 tail 末尾和 head 开头越好。
    """
    min_match = 2

    sm = difflib.SequenceMatcher(None, tail, head, autojunk=False)
    matches = sm.get_matching_blocks()

    # 位置约束：
    #   匹配在 tail 中的终点 (a+size) 必须在后半段（重叠在 prev 尾部）
    #   匹配在 head 中的起点 (b) 必须在前半段（重叠在 new 头部）
    tail_end_threshold = len(tail) // 4 * 3
    head_start_threshold = len(head) // 4

    candidates = [
        (a, b, size) for a, b, size in matches
        if size >= min_match and a + size > tail_end_threshold and b <= head_start_threshold
    ]
    if not candidates:
        return None

    # 评分：长度主导，位置辅助
    # length² 让长匹配碾压短匹配；+a 靠近尾部加分，-b 靠近头部加分
    def score(item):
        a, b, size = item
        return size * size + a - b

    return max(candidates, key=score)
