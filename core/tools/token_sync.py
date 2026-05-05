# coding: utf-8
"""
将格式化后的文本中的标点/热词/ITN 同步回 token 序列

格式化器（PuncModel + ITN + HotwordReplace）会在 text 中插入标点、改写内容和
替换热词，但 tokens 列表从未更新，导致 JSON 导出的 tokens 缺标点/不正确。

本模块通过 SequenceMatcher 对比格式化前后的文本差异，
将差异注入 token 序列，同时处理 ITN、热词替换等场景。

升级说明（v2）：
- expand + merge 策略：先将多字符 token 展开为单字符，再执行 SequenceMatcher 对齐，
  避免多字符 token 被局部修改时丢字符（如 "cloud" → "Claude" 中 "l" 被跳过的问题）。
- _handle_insert 不再只保留标点：所有插入文本（热词、标点等）都用 _tokenize_replacement
  切分后完整保留。
"""

import difflib
from typing import List, Tuple
from core.constants import Punctuation


# 标点符号集合（含中文+英文）
_PUNC_SET = set(Punctuation.ALL)


def _expand_tokens(tokens: List[str], timestamps: List[float]) -> Tuple[List[str], List[float]]:
    """将多字符 token 展开为单字符，每个字符继承原 token 的时间戳"""
    flat_tokens = []
    flat_timestamps = []
    for token, ts in zip(tokens, timestamps):
        for ch in token:
            flat_tokens.append(ch)
            flat_timestamps.append(ts)
    return flat_tokens, flat_timestamps


def _merge_ascii_tokens(tokens: List[str], timestamps: List[float]) -> Tuple[List[str], List[float]]:
    """合并连续的 ASCII alnum 单字符 token 回单词

    与 _tokenize_replacement 互为逆操作:
    - CJK 字符 → 保持独立
    - ASCII alnum 连续序列 → 合并为一个 token
    - 其他字符（空格、标点） → 保持独立
    """
    merged_tokens = []
    merged_timestamps = []
    buf = []
    buf_ts = []

    def flush():
        if buf:
            merged_tokens.append(''.join(buf))
            merged_timestamps.append(buf_ts[0])  # 取第一个字符的时间戳
            buf.clear()
            buf_ts.clear()

    for token, ts in zip(tokens, timestamps):
        if token.isascii() and token.isalnum():
            buf.append(token)
            buf_ts.append(ts)
        else:
            flush()
            merged_tokens.append(token)
            merged_timestamps.append(ts)

    flush()
    return merged_tokens, merged_timestamps


def sync_tokens_from_text(
    raw_tokens: List[str],
    raw_timestamps: List[float],
    formatted_text: str,
) -> Tuple[List[str], List[float]]:
    """
    将格式化文本中的修改同步回 token 序列

    用 SequenceMatcher 对比 ``raw_text``（tokens 拼接）和 ``formatted_text``：
    - 'equal': 输出对应的原始 token（不重复）
    - 'insert': 用 _tokenize_replacement 切分并插入（不限于标点）
    - 'replace': 找出被替换的原始 token，用格式化后的新文本替换（ITN / 热词兼容）
    - 'delete': 跳过被删除的原始 token

    升级策略：先展开多字符 token 为单字符（expand），使 SequenceMatcher 的
    字符级对齐与 token 索引一致，同步完成后再合并回词级（merge）。这样
    "cloud" 的每个字符都是独立 token，"c→C" 的 replace 不会误吞 "l"。

    Args:
        raw_tokens: 原始 token 列表
        raw_timestamps: 对应的时间戳列表
        formatted_text: 格式化后的文本（含标点 / ITN / 热词）

    Returns:
        (new_tokens, new_timestamps) 同步后的 token 序列
    """
    # ── Phase 1: 展开多字符 token ──────────────────────────
    need_merge = any(len(t) > 1 for t in raw_tokens)
    if need_merge:
        work_tokens, work_timestamps = _expand_tokens(raw_tokens, raw_timestamps)
    else:
        work_tokens, work_timestamps = raw_tokens, raw_timestamps

    raw_text = ''.join(work_tokens)

    if formatted_text == raw_text or not work_tokens:
        return list(raw_tokens), list(raw_timestamps)

    # ── Phase 2: SequenceMatcher 对齐 ────────────────────

    # 构建 raw_text 字符偏移 → token 索引的映射
    # 展开后每个字符独立为 token，所以 mapping 是 [0, 1, 2, ..., n-1]
    char_to_tok: List[int] = []
    for idx, token in enumerate(work_tokens):
        char_to_tok.extend([idx] * len(token))

    sm = difflib.SequenceMatcher(None, raw_text, formatted_text)

    new_tokens: List[str] = []
    new_timestamps: List[float] = []
    emitted: set = set()

    for op, ri1, ri2, fi1, fi2 in sm.get_opcodes():
        if op == 'equal':
            _handle_equal(work_tokens, work_timestamps, char_to_tok,
                          ri1, ri2, new_tokens, new_timestamps, emitted)

        elif op == 'insert':
            _handle_insert(formatted_text, fi1, fi2,
                           new_tokens, new_timestamps, work_timestamps)

        elif op == 'delete':
            _handle_delete(char_to_tok, ri1, ri2, emitted)

        elif op == 'replace':
            _handle_replace(work_tokens, work_timestamps, char_to_tok,
                            formatted_text, fi1, fi2, ri1, ri2,
                            new_tokens, new_timestamps, emitted)

    # ── Phase 3: 合并回词级 ──────────────────────────────
    if need_merge:
        new_tokens, new_timestamps = _merge_ascii_tokens(new_tokens, new_timestamps)

    return new_tokens, new_timestamps


# ── 内部处理函数 ─────────────────────────────────────────


def _handle_equal(raw_tokens, raw_timestamps, char_to_tok,
                  ri1, ri2, new_tokens, new_timestamps, emitted):
    """'equal' — 输出对应的原始 token"""
    for ri in range(ri1, ri2):
        ti = char_to_tok[ri]
        if ti not in emitted:
            new_tokens.append(raw_tokens[ti])
            new_timestamps.append(raw_timestamps[ti])
            emitted.add(ti)


def _handle_insert(formatted_text, fi1, fi2,
                   new_tokens, new_timestamps, raw_timestamps):
    """'insert' — 将插入文本完整切分为 token（不限于标点）

    升级后：所有插入内容都用 _tokenize_replacement 切分后保留，
    不再只保留标点。适用于标点插入、热词新增、空格调整等场景。
    """
    text = formatted_text[fi1:fi2]
    if not text:
        return
    ts = new_timestamps[-1] if new_timestamps else (raw_timestamps[0] if raw_timestamps else 0.0)
    for token in _tokenize_replacement(text):
        new_tokens.append(token)
        new_timestamps.append(ts)


def _handle_delete(char_to_tok, ri1, ri2, emitted):
    """'delete' — 标记被删除的原始 token 为已输出（跳过）"""
    if ri1 >= ri2:
        return
    ti_start = char_to_tok[ri1]
    ti_end = char_to_tok[ri2 - 1] + 1
    for ti in range(ti_start, ti_end):
        emitted.add(ti)


def _handle_replace(raw_tokens, raw_timestamps, char_to_tok,
                    formatted_text, fi1, fi2, ri1, ri2,
                    new_tokens, new_timestamps, emitted):
    """
    'replace' — 找出被替换的原始 token，替换为新文本

    ITN 会把 "二" → "2"、"三百" → "300"，跨 token 边界的替换也支持。
    新文本按字符类型（CJK / ASCII alnum / 其他）自动切分为 token，
    时间戳取被替换的第一个原始 token。
    """
    if ri1 >= ri2:
        return

    # 找出被替换的原始 token 范围
    ti_start = char_to_tok[ri1]
    ti_end = char_to_tok[ri2 - 1] + 1

    # 标记这些原始 token 为已输出
    for ti in range(ti_start, ti_end):
        emitted.add(ti)

    # 切分替换文本为 token
    replacement = formatted_text[fi1:fi2]
    if not replacement:
        return

    replace_tokens = _tokenize_replacement(replacement)
    ts = raw_timestamps[ti_start]  # 用第一个被替换 token 的时间戳
    for rt in replace_tokens:
        new_tokens.append(rt)
        new_timestamps.append(ts)


def _tokenize_replacement(text: str) -> List[str]:
    """
    将替换文本按字符类型切分为 token

    规则（与 ParaformerEngine._post_process_tokens 一致）：
    - CJK 字符 → 单个 token
    - ASCII alnum 连续序列 → 一个 token
    - 其他字符（空格、标点） → 单个 token
    """
    tokens = []
    buf: List[str] = []

    def flush():
        if buf:
            tokens.append(''.join(buf))
            buf.clear()

    for ch in text:
        if ch.isascii() and ch.isalnum():
            buf.append(ch)
        elif ch.isalnum():
            # 非 ASCII alnum（中文等）→ 独立 token
            flush()
            tokens.append(ch)
        else:
            # 空格、标点等 → 独立 token
            flush()
            tokens.append(ch)

    flush()
    return tokens
