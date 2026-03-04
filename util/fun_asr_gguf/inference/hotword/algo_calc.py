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


def get_phoneme_cost(p1: Phoneme, p2: Phoneme) -> float:
    """
    计算音素匹配代价（基于 Phoneme 对象的语言属性）

    返回值范围: 0.0 (完全匹配) ~ 1.0 (完全不匹配)

    规则:
    1. 完全相同（value + lang）-> 0.0
    2. 相似音素（前后鼻音、平翘舌等）-> 0.5（仅限中文音素）
    3. 英文单词之间 -> 使用 LCS 计算字符级相似度
    4. 不同语言音素混合 -> 1.0（完全不匹配）
    5. 其他 -> 1.0
    """
    # 不同语言，直接返回不匹配
    if p1.lang != p2.lang:
        return 1.0

    # 相同语言，比较 value
    if p1.value == p2.value:
        return 0.0

    # 中文音素：检查相似音素
    if p1.lang == 'zh' and p2.lang == 'zh':
        pair = {p1.value, p2.value}
        for s in SIMILAR_PHONEMES:
            if pair.issubset(s):
                return 0.5

    # 英文单词：使用 LCS 计算相似度
    if p1.lang == 'en' and p2.lang == 'en':
        lcs_len = lcs_length(p1.value, p2.value)
        max_len = max(len(p1.value), len(p2.value))
        similarity = lcs_len / max_len
        return 1.0 - similarity

    return 1.0


def find_best_match(main_seq: List[Phoneme], sub_seq: List[Phoneme]) -> Tuple[float, int, int]:
    """
    寻找最佳模糊匹配位置（基于 Phoneme 对象，限制只能从字边界开始）

    Args:
        main_seq: 主音素序列（长）
        sub_seq: 子音素序列（短，热词）

    Returns:
        (score, start_index, end_index)
        score: 相似度 0-1
        start_index: 匹配在 main_seq 中的起始索引 (inclusive)
        end_index: 匹配在 main_seq 中的结束索引 (exclusive)
    """
    # DEBUG
    import logging
    logger = logging.getLogger('fun_asr_gguf.hotword.algo_calc')
    logger.debug(f"[DEBUG] find_best_match: main_seq type={type(main_seq)}, len={len(main_seq)}")
    logger.debug(f"[DEBUG] find_best_match: sub_seq type={type(sub_seq)}, len={len(sub_seq)}")
    if main_seq:
        logger.debug(f"[DEBUG] find_best_match: main_seq[0] type={type(main_seq[0])}, value={main_seq[0]}")
    if sub_seq:
        logger.debug(f"[DEBUG] find_best_match: sub_seq[0] type={type(sub_seq[0])}, value={sub_seq[0]}")

    n = len(sub_seq)
    m = len(main_seq)
    if n == 0:
        return 0.0, 0, 0
    if m == 0:
        return 0.0, 0, 0

    # 预计算字边界：只允许从这些位置开始匹配
    # 使用 Phoneme 对象的 is_word_start 属性，无需重复计算
    try:
        valid_starts = [j for j in range(m) if main_seq[j].is_word_start]
        logger.debug(f"[DEBUG] find_best_match: valid_starts={valid_starts[:5]}...")
    except Exception as e:
        logger.error(f"[ERROR] Failed to build valid_starts: {e}")
        logger.error(f"[ERROR] main_seq details: {[(type(item), item) for item in main_seq[:5]]}")
        raise

    # DP 矩阵: rows=n+1, cols=m+1
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]

    # Initialize first row (Start Constraints)
    # dp[0][j] = 0 means we can start matching at position j (main_seq[j]) with 0 cost.
    # We only allow starting at valid word boundaries.
    for j in range(m + 1):
        if j in valid_starts:
            dp[0][j] = 0.0
        else:
            # Special case: allow starting at absolute beginning if it matches word start
            # (valid_starts usually includes 0 if main_seq[0] is start)
            # But we also accept start at end of string (j=m) as valid "empty match", though useless for non-empty sub.
            dp[0][j] = float('inf')
            
    # Allow 0 to be valid if valid_starts is empty? No, pure boundary constraint.
    # If j=m, it's out of bounds for main_seq, so cannot start a word there. 
    # Unless we match empty string? But let's keep it simple.
    # Note: dp[0][0] must be 0 if 0 is in valid_starts.
    
    # Initialize first column (Deletion cost from valid start)
    # This loop depends on dp[0][0] being 0 or inf.
    for i in range(1, n + 1):
        dp[i][0] = dp[i-1][0] + 1.0

    # 填充 DP 矩阵
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = get_phoneme_cost(sub_seq[i-1], main_seq[j-1])

            dp[i][j] = min(
                dp[i-1][j] + 1.0,     # Deletion
                dp[i][j-1] + 1.0,     # Insertion
                dp[i-1][j-1] + cost   # Match/Mismatch/Similar
            )

    # 找到最后一行最小值的位置，且起始位置必须在字边界
    min_dist = float('inf')
    end_pos = 0
    best_start = 0

    for j in range(1, m + 1):
        if dp[n][j] < min_dist:
            # 回溯找到起始位置
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

            # 检查起始位置是否在字边界
            if curr_j in valid_starts:
                min_dist = dp[n][j]
                end_pos = j
                best_start = curr_j

    # 计算分数
    score = 1.0 - (min_dist / n)

    return score, best_start, end_pos


def fast_substring_score(hw_info: List[Tuple], input_info: List[Tuple]) -> float:
    """
    高性能音素序列相似度计算 (针对 info 五元组/七元组)
    
    规则：保持与 get_phoneme_cost 一致但直接操作元组以提升性能。
    元组索引: 0=value, 1=lang, 4/4=is_tone (info[:5] 中的第5项)
    """
    n = len(hw_info)
    m = len(input_info)
    if n == 0: return 0.0
    
    # 简单的线性比对（因为目前滑动窗口已经对齐了长度）
    # 如果需要更复杂的编辑距离，可以使用类似 fuzzy_substring_score 的逻辑
    diff = 0.0
    for i in range(n):
        h_val, h_lang, _, _, h_tone = hw_info[i][:5]
        i_val, i_lang, _, _, i_tone = input_info[i][:5]
        
        if h_lang != i_lang:
            diff += 1.0
            continue
            
        if h_val == i_val:
            continue
            
        # 相似音素判断
        if h_lang == 'zh':
            pair = {h_val, i_val}
            is_similar = False
            for s in SIMILAR_PHONEMES:
                if pair.issubset(s):
                    is_similar = True
                    break
            if is_similar:
                diff += 0.5
                continue
        
        diff += 1.0
        
    return 1.0 - (diff / n)


def fuzzy_substring_distance(hw_info: List[Tuple], input_info: List[Tuple]) -> float:
    """
    计算子序列在主序列中的最小编辑距离（允许子序列匹配主序列的任意部分）
    使用滚动数组优化的动态规划实现

    参数:
        hw_info: 热词音素序列（info 元组列表）
        input_info: 输入音素序列（info 元组列表）
    """
    n = len(hw_info)
    m = len(input_info)
    if n == 0:
        return 0.0
    if m == 0:
        return float(n)

    prev = [0.0] * (m + 1)
    curr = [0.0] * (m + 1)

    for i in range(1, n + 1):
        curr[0] = float(i)

        for j in range(1, m + 1):
            # 直接从元组计算代价（避免创建 Phoneme 对象）
            cost = _get_tuple_cost(hw_info[i-1], input_info[j-1])

            curr[j] = min(
                prev[j] + 1.0,
                curr[j-1] + 1.0,
                prev[j-1] + cost
            )

        prev, curr = curr, prev

    return min(prev)


def fuzzy_substring_score(hw_info: List[Tuple], input_info: List[Tuple]) -> float:
    """
    计算子序列在主序列中的相似度分数（0-1之间）

    基于编辑距离，将距离转换为相似度：
    - 完全匹配 -> 1.0
    - 完全不匹配 -> 0.0

    参数:
        hw_info: 热词音素序列（info 元组列表）
        input_info: 输入音素序列（info 元组列表）

    返回:
        相似度分数 (0.0 - 1.0)
    """
    n = len(hw_info)
    if n == 0:
        return 0.0

    # 计算最小编辑距离
    distance = fuzzy_substring_distance(hw_info, input_info)

    # 转换为相似度分数：距离越小，相似度越高
    # 使用归一化：score = 1 - (distance / max_possible_distance)
    # 最大可能距离是热词长度
    score = 1.0 - (distance / n)

    return max(0.0, min(1.0, score))


def _get_tuple_cost(t1: Tuple, t2: Tuple) -> float:
    """
    计算两个音素元组的匹配代价

    参数:
        t1, t2: 音素 info 元组 (值, 语言, 字始, 字终, 声调, ...)
    """
    # 不同语言，直接返回不匹配
    if t1[1] != t2[1]:
        return 1.0

    # 相同语言，比较 value
    if t1[0] == t2[0]:
        return 0.0

    # 中文相似音素判断
    if t1[1] == 'zh':
        if t1[4]:  # is_tone
             return 0.5
             
        pair = {t1[0], t2[0]}
        for s in SIMILAR_PHONEMES:
            if pair.issubset(s):
                return 0.5

    # 英文单词字符级相似度
    if t1[1] == 'en':
        lcs_len = _lcs_length(t1[0], t2[0])
        max_len = max(len(t1[0]), len(t2[0]))
        if max_len > 0:
            return 1.0 - (lcs_len / max_len)

    return 1.0


def fuzzy_substring_search_constrained(hw_info: List[Tuple], input_info: List[Tuple], threshold: float = 0.6) -> List[Tuple[float, int, int]]:
    """
    在输入序列中搜索热词的最佳匹配片段（边界约束版）

    使用 DP 计算局部相似度，要求：
    1. 起始位置必须是原句的词起始 (is_word_start)
    2. 结束位置必须是原句的词结束 (is_word_end)
    3. 允许长度在一定范围内缩放，不再死磕等长

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

    # DP 矩阵: [n+1][m+1]
    # dp[i][j] 表示 hw 前 i 个音素匹配以 input[j-1] 结尾的某个片段的最小距离
    dp = [[float('inf')] * (m + 1) for _ in range(n + 1)]

    # 路径记录，用于找起始点: (prev_i, prev_j)
    path = [[(0, 0)] * (m + 1) for _ in range(n + 1)]

    # 初始化第一行：允许从任何词起始边界开始匹配
    # 如果 input_info[j] 是词起始，则我们可以在索引 j 处开始匹配 hw[0]
    # 对应的 DP 状态是 dp[1][j+1]，其依赖于 dp[0][j]
    for j in range(m + 1):
        if j == 0:
            dp[0][j] = 0.0
            path[0][j] = (0, j)
        elif j < m and input_info[j][2]:  # is_word_start
            dp[0][j] = 0.0
            path[0][j] = (0, j)

    # 填充 DP
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = _get_tuple_cost(hw_info[i-1], input_info[j-1])

            # 候选路径：匹配、删除热词音素、插入额外音素
            dist_match = dp[i-1][j-1] + cost
            dist_del = dp[i-1][j] + 1.0    # 只有在匹配英文时我们宽容长度差异
            dist_ins = dp[i][j-1] + 1.0

            # 选最小并记录路径
            min_dist = min(dist_match, dist_del, dist_ins)
            dp[i][j] = min_dist
            
            if min_dist == dist_match:
                path[i][j] = path[i-1][j-1]
            elif min_dist == dist_del:
                path[i][j] = path[i-1][j]
            else:
                path[i][j] = path[i][j-1]

    # 收集结果
    results = []
    seen_ranges = set()

    for j in range(1, m + 1):
        # 约束：终点必须是词边界
        if not input_info[j-1][3]:  # is_word_end
            continue

        dist = dp[n][j]
        # 针对末尾差异做极简优化：如果是英文且差值只是一个音素，且该音素分值较低
        # (如 Claude 多出来的空音素)，则稍微给予补偿
        if n > 1 and dist > 0.5:
             # 如果最后一个音素不匹配，且它在输入中是边界结束
             pass # 未来可加入更精细的补偿
             
        if dist >= n * 0.8: continue  # 距离太大，强制过滤

        score = 1.0 - (dist / n)
        if score >= threshold:
            start_idx = path[n][j][1]
            end_idx = j # 它是 input 中的第 j 个，索引是 j-1
            
            # 返回音素层级的索引，不要在核心算法里死磕 char 索引
            results.append((score, start_idx, end_idx))

    # 按得分降序
    results.sort(key=lambda x: x[0], reverse=True)
    
    # 区间排重（如果同一结束点有多个起始点，只留最优）
    final_res = []
    used_ends = {}
    for score, s, e in results:
        if e not in used_ends or score > used_ends[e][0]:
            used_ends[e] = (score, s, e)
    
    return sorted(used_ends.values(), key=lambda x: x[0], reverse=True)


def _lcs_length(s1: str, s2: str) -> int:
    """计算最长公共子序列长度"""
    m, n = len(s1), len(s2)
    if m == 0 or n == 0:
        return 0

    # 使用滚动数组优化
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
