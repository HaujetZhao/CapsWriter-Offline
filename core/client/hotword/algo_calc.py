# coding: utf-8
"""
RAG 核心算法模块

提供基于音素的模糊编辑距离计算功能。
"""
from typing import List, Tuple
from .algo_phoneme import Phoneme

# 相似音素集合（模糊匹配权重 0.5）
SIMILAR_PHONEMES = [
    # 前后鼻音
    {'an', 'ang'},
    {'en', 'eng'},
    {'in', 'ing'},
    {'ian', 'iang'},
    {'uan', 'uang'},
    # 平翘舌
    {'z', 'zh'},
    {'c', 'ch'},
    {'s', 'sh'},
    # 鼻音/边音
    {'l', 'n'},
    # 唇齿音/声门音 (Hu Jian / Fu Jian)
    {'f', 'h'},
    # 常见易混韵母
    {'ai', 'ei'},
    {'o', 'uo'},
    {'e', 'ie'},
    # 清浊音/送气不送气 (在某些语境下音近)
    {'p', 't'},
    {'p', 'b'},
    {'t', 'd'},
    {'k', 'g'},
]


def _is_similar_phoneme(a: str, b: str) -> bool:
    """检查两个音素是否属于同一个相似音素集"""
    pair = {a, b}
    return any(pair.issubset(s) for s in SIMILAR_PHONEMES)


def lcs_length(s1: str, s2: str) -> int:
    """
    计算两个字符串的最长公共子序列 (LCS) 长度

    时间复杂度: O(m*n)
    空间复杂度: O(min(m,n)) - 使用滚动数组优化
    """
    if len(s1) < len(s2):
        s1, s2 = s2, s1

    m, n = len(s1), len(s2)
    if n == 0:
        return 0

    prev = [0] * (n + 1)
    curr = [0] * (n + 1)

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i-1] == s2[j-1]:
                curr[j] = prev[j-1] + 1
            else:
                curr[j] = max(prev[j], curr[j-1])
        prev, curr = curr, prev

    return prev[n]


def get_phoneme_cost(p1: Phoneme, p2: Phoneme) -> float:
    """
    计算音素匹配代价（基于 Phoneme 对象的语言属性）

    返回值范围: 0.0 (完全匹配) ~ 1.0 (完全不匹配)
    """
    if p1.lang != p2.lang:
        return 1.0

    if p1.value == p2.value:
        return 0.0

    if p1.lang == 'zh' and _is_similar_phoneme(p1.value, p2.value):
        return 0.5

    if p1.lang == 'en':
        lcs_len = lcs_length(p1.value, p2.value)
        max_len = max(len(p1.value), len(p2.value))
        return 1.0 - (lcs_len / max_len)

    return 1.0


def find_best_match(main_seq: List[Phoneme], sub_seq: List[Phoneme]) -> Tuple[float, int, int]:
    """寻找最佳模糊匹配位置（基于 Phoneme 对象，限制只能从字边界开始）"""
    n = len(sub_seq)
    m = len(main_seq)
    if n == 0:
        return 0.0, 0, 0
    if m == 0:
        return 0.0, 0, 0

    valid_starts = [j for j in range(m) if main_seq[j].is_word_start]

    dp = [[0.0] * (m + 1) for _ in range(n + 1)]

    for j in range(m + 1):
        if j in valid_starts:
            dp[0][j] = 0.0
        else:
            dp[0][j] = float('inf')

    for i in range(1, n + 1):
        dp[i][0] = dp[i-1][0] + 1.0

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = get_phoneme_cost(sub_seq[i-1], main_seq[j-1])
            dp[i][j] = min(
                dp[i-1][j] + 1.0,
                dp[i][j-1] + 1.0,
                dp[i-1][j-1] + cost
            )

    min_dist = float('inf')
    end_pos = 0
    best_start = 0

    for j in range(1, m + 1):
        if dp[n][j] < min_dist:
            curr_i, curr_j = n, j
            while curr_i > 0:
                cost = get_phoneme_cost(sub_seq[curr_i-1], main_seq[curr_j-1])
                if curr_j > 0 and abs(dp[curr_i][curr_j] - (dp[curr_i-1][curr_j-1] + cost)) < 1e-9:
                    curr_i -= 1
                    curr_j -= 1
                elif abs(dp[curr_i][curr_j] - (dp[curr_i-1][curr_j] + 1.0)) < 1e-9:
                    curr_i -= 1
                elif curr_j > 0 and abs(dp[curr_i][curr_j] - (dp[curr_i][curr_j-1] + 1.0)) < 1e-9:
                    curr_j -= 1
                else:
                    curr_i -= 1

            if curr_j in valid_starts:
                min_dist = dp[n][j]
                end_pos = j
                best_start = curr_j

    score = 1.0 - (min_dist / n)
    return score, best_start, end_pos


def fuzzy_substring_search_constrained(hw_info: List[Tuple], input_info: List[Tuple], threshold: float = 0.6) -> List[Tuple[float, int, int]]:
    """
    在输入序列中搜索热词的最佳匹配片段（边界约束版）

    使用 DP 计算局部相似度，要求：
    1. 起始位置必须是原句的词起始 (is_word_start)
    2. 结束位置必须是原句的词结束 (is_word_end)
    3. 允许长度在一定范围内缩放

    参数:
        hw_info: 热词音素 info 元组列表 (值, 语言, 字始, 字终, 声调, ...)
        input_info: 输入文本音素 info 元组列表
        threshold: 相似度阈值

    返回:
        List[(score, start_idx, end_idx)] - 匹配结果列表（按分数降序）
    """
    n = len(hw_info)
    m = len(input_info)
    if n == 0 or m == 0:
        return []

    dp = [[float('inf')] * (m + 1) for _ in range(n + 1)]
    path = [[(0, 0)] * (m + 1) for _ in range(n + 1)]

    # 预提取 input 信息，减少循环内解包开销
    input_vals = [t[0] for t in input_info]
    input_langs = [t[1] for t in input_info]
    input_starts = [t[2] for t in input_info]
    input_ends = [t[3] for t in input_info]
    input_phones = [t[4] for t in input_info]

    hw_vals = [t[0] for t in hw_info]
    hw_langs = [t[1] for t in hw_info]
    hw_phones = [t[4] for t in hw_info]

    # 初始化第一行：允许从任何词起始边界开始匹配
    for j in range(m + 1):
        if j == 0 or (j < m and input_starts[j]):
            dp[0][j] = 0.0
            path[0][j] = (0, j)

    for i in range(1, n + 1):
        h_v, h_l, h_p = hw_vals[i-1], hw_langs[i-1], hw_phones[i-1]
        row_min = float('inf')

        for j in range(1, m + 1):
            i_v, i_l, i_p = input_vals[j-1], input_langs[j-1], input_phones[j-1]
            if h_l != i_l:
                cost = 1.0
            elif h_v == i_v:
                cost = 0.0
            elif h_l == 'zh':
                if h_p:
                    cost = 0.5
                elif _is_similar_phoneme(h_v, i_v):
                    cost = 0.5
                else:
                    cost = 1.0
            elif h_l == 'en':
                lcs = lcs_length(h_v, i_v)
                cost = 1.0 - (lcs / max(len(h_v), len(i_v)))
            else:
                cost = 1.0

            dist_match = dp[i-1][j-1] + cost
            dist_del = dp[i-1][j] + 1.0
            dist_ins = dp[i][j-1] + 1.0

            if dist_match <= dist_del:
                if dist_match <= dist_ins:
                    dp[i][j] = dist_match
                    path[i][j] = path[i-1][j-1]
                else:
                    dp[i][j] = dist_ins
                    path[i][j] = path[i][j-1]
            else:
                if dist_del <= dist_ins:
                    dp[i][j] = dist_del
                    path[i][j] = path[i-1][j]
                else:
                    dp[i][j] = dist_ins
                    path[i][j] = path[i][j-1]

            if dp[i][j] < row_min:
                row_min = dp[i][j]

        if row_min > n * (1.0 - threshold) + 2:
            break

    results = []
    for j in range(1, m + 1):
        if not input_info[j-1][3]:  # is_word_end
            continue

        dist = dp[n][j]
        if dist >= n * 0.8:
            continue

        score = 1.0 - (dist / n)
        if score >= threshold:
            start_idx = path[n][j][1]
            results.append((score, start_idx, j))

    results.sort(key=lambda x: x[0], reverse=True)

    final_res = []
    used_ends = {}
    for score, s, e in results:
        if e not in used_ends or score > used_ends[e][0]:
            used_ends[e] = (score, s, e)

    return sorted(used_ends.values(), key=lambda x: x[0], reverse=True)
