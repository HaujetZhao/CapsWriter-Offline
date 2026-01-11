# coding: utf-8
"""
RAG 核心算法模块

提供基于音素的模糊编辑距离计算功能。
"""
from typing import List, Tuple

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
]

def get_phoneme_cost(p1: str, p2: str) -> float:
    """计算音素匹配代价"""
    if p1 == p2:
        return 0.0
    
    pair = {p1, p2}
    for s in SIMILAR_PHONEMES:
        if pair.issubset(s):
            return 0.5
            
    return 1.0


def find_best_match(main_seq: List[str], sub_seq: List[str]) -> Tuple[float, int, int]:
    """
    寻找最佳模糊匹配位置

    Args:
        main_seq: 主序列（长）
        sub_seq: 子序列（短，热词）
    
    Returns:
        (score, start_index, end_index)
        score: 相似度 0-1
        start_index: 匹配在 main_seq 中的起始索引 (inclusive)
        end_index: 匹配在 main_seq 中的结束索引 (exclusive)
    """
    n = len(sub_seq)
    m = len(main_seq)
    if n == 0:
        return 0.0, 0, 0
    if m == 0:
        return 0.0, 0, 0

    # DP 矩阵: rows=n+1, cols=m+1
    # distance[i][j] 表示 sub_seq[:i] 和 main_seq[...:j] (suffix ending at j) 的最小编辑距离
    # 注意：我们允许从 main_seq 的任意位置开始，所以第一行初始化为 0 (Free start)
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]

    # Initialize first column: transforming sub_seq[:i] to empty string requires i deletions
    for i in range(1, n + 1):
        dp[i][0] = float(i)

    # No initialization for first row needed (zeros), allowing start at any position

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = get_phoneme_cost(sub_seq[i-1], main_seq[j-1])
            
            dp[i][j] = min(
                dp[i-1][j] + 1.0,     # Deletion
                dp[i][j-1] + 1.0,     # Insertion
                dp[i-1][j-1] + cost   # Match/Mismatch/Similar
            )

    # 找到最后一行最小值的位置，即最佳结束位置
    min_dist = float('inf')
    end_pos = 0
    for j in range(1, m + 1):
        if dp[n][j] < min_dist:
            min_dist = dp[n][j]
            end_pos = j
            
    # 计算分数
    score = 1.0 - (min_dist / n)

    # 回溯找到起始位置 (Traceback)
    # 从 (n, end_pos) 开始往回走，直到 row 0
    curr_i, curr_j = n, end_pos
    while curr_i > 0:
        # 必须往回走 i
        
        # Check diagonal (Match/Similar/Mismatch)
        cost = get_phoneme_cost(sub_seq[curr_i-1], main_seq[curr_j-1])
        
        # 使用近似比较处理浮点数
        if curr_j > 0 and abs(dp[curr_i][curr_j] - (dp[curr_i-1][curr_j-1] + cost)) < 1e-9:
            curr_i -= 1
            curr_j -= 1
        elif abs(dp[curr_i][curr_j] - (dp[curr_i-1][curr_j] + 1.0)) < 1e-9:
             curr_i -= 1
        elif curr_j > 0 and abs(dp[curr_i][curr_j] - (dp[curr_i][curr_j-1] + 1.0)) < 1e-9:
             curr_j -= 1
        else:
            # Should not happen in valid DP, but as fail-safe
            curr_i -= 1
            
    start_pos = curr_j
    
    return score, start_pos, end_pos


def fuzzy_substring_distance(main_seq: List[str], sub_seq: List[str]) -> float:
    """
    计算子序列在主序列中的最小编辑距离（允许子序列匹配主序列的任意部分）
    使用滚动数组优化的动态规划实现
    """
    n = len(sub_seq)
    m = len(main_seq)
    if n == 0:
        return 0.0
    if m == 0:
        return float(n)

    prev = [0.0] * (m + 1)
    curr = [0.0] * (m + 1)

    for i in range(1, n + 1):
        curr[0] = float(i)

        for j in range(1, m + 1):
            cost = get_phoneme_cost(sub_seq[i-1], main_seq[j-1])

            curr[j] = min(
                prev[j] + 1.0,
                curr[j-1] + 1.0,
                prev[j-1] + cost
            )

        prev, curr = curr, prev

    return min(prev)
