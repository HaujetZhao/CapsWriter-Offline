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

def lcs_length(s1: str, s2: str) -> int:
    """
    计算两个字符串的最长公共子序列 (LCS) 长度
    
    时间复杂度: O(m*n)
    空间复杂度: O(min(m,n)) - 使用滚动数组优化
    """
    if len(s1) < len(s2):
        s1, s2 = s2, s1  # 确保 s1 是较长的
    
    m, n = len(s1), len(s2)
    if n == 0:
        return 0
    
    # 滚动数组
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


def char_level_substring_score(main_text: str, pattern: str) -> float:
    """
    在主文本中查找模式的最佳字符级匹配分数
    
    用于英文热词匹配：忽略空格和大小写，使用 LCS 计算相似度。
    
    Args:
        main_text: 主文本（已规范化，只含字母数字，小写）
        pattern: 热词模式（已规范化，只含字母数字，小写）
    
    Returns:
        相似度分数 (0.0 ~ 1.0)
    
    示例:
        char_level_substring_score("capswriter", "capswriter") = 1.0
        char_level_substring_score("youcanusecapswritertotype", "capswriter") ≈ 1.0
    """
    if not pattern:
        return 0.0
    if not main_text:
        return 0.0
    
    # 如果模式完全在主文本中（子串），分数为 1.0
    if pattern in main_text:
        return 1.0
    
    # 使用滑动窗口 + LCS 找最佳匹配
    pattern_len = len(pattern)
    best_score = 0.0
    
    # 窗口大小从 pattern_len 到 pattern_len * 1.5
    for window_size in range(pattern_len, min(len(main_text) + 1, int(pattern_len * 1.5) + 1)):
        for start in range(len(main_text) - window_size + 1):
            window = main_text[start:start + window_size]
            lcs_len = lcs_length(window, pattern)
            score = lcs_len / pattern_len
            if score > best_score:
                best_score = score
    
    return best_score


def get_phoneme_cost(p1: str, p2: str) -> float:
    """
    计算音素匹配代价
    
    返回值范围: 0.0 (完全匹配) ~ 1.0 (完全不匹配)
    
    规则:
    1. 完全相同 -> 0.0
    2. 相似音素（前后鼻音、平翘舌等）-> 0.5
    3. 英文单词 -> 使用 LCS 计算字符级相似度
    4. 其他 -> 1.0
    """
    if p1 == p2:
        return 0.0
    
    # 检查相似音素
    pair = {p1, p2}
    for s in SIMILAR_PHONEMES:
        if pair.issubset(s):
            return 0.5
    
    # 英文单词使用 LCS 计算相似度
    # 条件：两个 token 都是纯英文字母且长度 > 1
    if len(p1) > 1 and len(p2) > 1 and p1.isalpha() and p2.isalpha():
        lcs_len = lcs_length(p1, p2)
        max_len = max(len(p1), len(p2))
        similarity = lcs_len / max_len
        # 返回代价 = 1 - 相似度
        return 1.0 - similarity
            
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
