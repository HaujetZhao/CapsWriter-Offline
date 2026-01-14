# coding: utf-8
"""
高性能 RAG 加速模块

使用以下技术优化检索性能：
1. Numba JIT 编译核心 DP 算法
2. 首音素倒排索引减少候选
3. 长度过滤跳过不可能的匹配
"""

import numpy as np
from typing import List, Dict, Tuple, Set, Union
from collections import defaultdict
import time
import logging

logger = logging.getLogger(__name__)

# 尝试导入 Numba
try:
    from numba import jit, njit
    import numba
    HAS_NUMBA = True
    logger.debug("Numba 可用，使用 JIT 加速")
except ImportError:
    HAS_NUMBA = False
    logger.debug("Numba 不可用，使用纯 Python")


# =============================================================================
# Numba 加速版本
# =============================================================================

if HAS_NUMBA:
    @njit(cache=True)
    def _fuzzy_substring_distance_numba(main_codes: np.ndarray, sub_codes: np.ndarray) -> float:
        """
        Numba 加速的模糊子串距离计算
        
        使用整数编码代替字符串，大幅提升性能。
        """
        n = len(sub_codes)
        m = len(main_codes)
        
        if n == 0 or m == 0:
            return float(n)
        
        # DP 矩阵
        dp = np.zeros((n + 1, m + 1), dtype=np.float32)
        
        # 初始化第一列
        for i in range(1, n + 1):
            dp[i, 0] = float(i)
        
        # 填充 DP 矩阵
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                # 计算代价：相同=0，不同=1
                if sub_codes[i-1] == main_codes[j-1]:
                    cost = 0.0
                else:
                    cost = 1.0
                
                dp[i, j] = min(
                    dp[i-1, j] + 1.0,       # 删除
                    dp[i, j-1] + 1.0,       # 插入
                    dp[i-1, j-1] + cost     # 替换/匹配
                )
        
        # 找最小距离
        min_dist = dp[n, 1]
        for j in range(2, m + 1):
            if dp[n, j] < min_dist:
                min_dist = dp[n, j]
        
        return min_dist


# =============================================================================
# 音素编码器（字符串 -> 整数）
# =============================================================================

from .algo_phoneme import Phoneme
from .algo_calc import SIMILAR_PHONEMES

class PhonemeEncoder:
    """将音素字符串编码为整数，用于 Numba 加速"""
    
    def __init__(self):
        self.phoneme_to_code: Dict[str, int] = {}
        self.code_to_phoneme: Dict[int, str] = {}
        self.next_code = 1  # 0 保留
        
    def encode(self, phoneme: str) -> int:
        if phoneme not in self.phoneme_to_code:
            self.phoneme_to_code[phoneme] = self.next_code
            self.code_to_phoneme[self.next_code] = phoneme
            self.next_code += 1
        return self.phoneme_to_code[phoneme]
    
    def encode_sequence(self, phonemes: List[str]) -> np.ndarray:
        return np.array([self.encode(p) for p in phonemes], dtype=np.int32)


# =============================================================================
# 倒排索引
# =============================================================================

class PhonemeIndex:
    """
    首音素倒排索引
    
    按首音素分桶，检索时只匹配相关桶，减少 90% 计算量
    """
    
    def __init__(self):
        self.encoder = PhonemeEncoder()
        # {首音素编码: [(热词原文, 音素编码数组), ...]}
        self.index: Dict[int, List[Tuple[str, np.ndarray]]] = defaultdict(list)
        self.all_hotwords: List[Tuple[str, np.ndarray]] = []
        
    def add(self, hotword: str, phonemes: List[Phoneme]):
        """添加热词到索引，内部自动决定索引哪些位置"""
        if not phonemes:
            return
        
        # 将音素对象编码为整数 ID 序列
        phoneme_strs = [p.value for p in phonemes]
        codes = self.encoder.encode_sequence(phoneme_strs)
        
        # 索引策略决策
        # 默认只索引首个音素 (适用于中文，区分度高)
        indices = [0]
        
        # 策略优化：如果是英文，索引前两个音素以容错 (如 klaude -> Claude)
        if phonemes[0].lang == 'en':
            limit = min(len(codes), 2)
            indices = list(range(limit))
            
        # 收集去重后的 target_codes
        target_codes = {codes[i] for i in indices if i < len(codes)}
        
        for code in target_codes:
            self.index[code].append((hotword, codes))
            
        self.all_hotwords.append((hotword, codes))
        
    def get_candidates(self, input_phonemes: List[Phoneme]) -> List[Tuple[str, np.ndarray]]:
        """
        获取候选热词

        只返回首音素在输入中出现过的热词

        Args:
            input_phonemes: 输入音素序列 (List[Phoneme])
        """
        # 获取输入中所有唯一的音素（作为潜在首音素）
        input_codes = set()
        
        for p in input_phonemes:
            val = p.value
            code = self.encoder.phoneme_to_code.get(val)
            if code is not None:
                input_codes.add(code)
            
            # [核心增强] 如果是中文，也把相似的音素加入搜索范围，以防首音素识别错误
            if p.lang != 'zh':
                continue

            for s_set in SIMILAR_PHONEMES:
                if val not in s_set:
                    continue
                for sim_val in s_set:
                    sim_code = self.encoder.phoneme_to_code.get(sim_val)
                    if sim_code is None:
                        continue
                    input_codes.add(sim_code)

        # 收集候选
        candidates = []
        seen = set()
        for code in input_codes:
            for hw, codes in self.index.get(code, []):
                if hw in seen:
                    continue
                candidates.append((hw, codes))
                seen.add(hw)

        return candidates
    
    def encode_input(self, phonemes: List[Phoneme]) -> np.ndarray:
        """编码输入序列"""
        phoneme_strs = [p.value for p in phonemes]
        return self.encoder.encode_sequence(phoneme_strs)


# =============================================================================
# 高性能 RAG 检索器
# =============================================================================

class FastRAG:
    """
    高性能 RAG 检索器
    
    特点：
    1. Numba JIT 加速核心算法
    2. 首音素倒排索引减少候选
    3. 长度过滤跳过不可能匹配
    """
    
    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold
        self.index = PhonemeIndex()
        self.hotword_count = 0
        
    def add_hotwords(self, hotwords: Dict[str, List[Phoneme]]):
        """
        批量添加热词
        
        Args:
            hotwords: {热词原文: 音素序列} (key: str, value: List[Phoneme])
        """
        for hw, phonemes in hotwords.items():
            if phonemes:
                self.index.add(hw, phonemes)
                self.hotword_count += 1
                
    def search(self, input_phonemes: List[Phoneme], top_k: int = 10) -> List[Tuple[str, float]]:
        """
        检索相关热词（高层编排）
        """
        if not input_phonemes: return []

        # DEBUG
        from util.logger import get_logger
        logger = get_logger('client')
        logger.debug(f"[DEBUG] FastRAG.search: input_phonemes type={type(input_phonemes)}, len={len(input_phonemes)}")
        if input_phonemes:
            logger.debug(f"[DEBUG] FastRAG.search: input_phonemes[0] type={type(input_phonemes[0])}, value={input_phonemes[0]}")

        # 1. 编码输入并获取候选
        input_codes = self.index.encode_input(input_phonemes)
        candidates = self.index.get_candidates(input_phonemes)

        # 2. 遍历打分与过滤
        results = self._score_candidates(input_codes, candidates)

        # 3. 排序并截断
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _score_candidates(self, input_codes: np.ndarray, candidates: List[Tuple[str, np.ndarray]]) -> List[Tuple[str, float]]:
        """对候选列表进行相似度计算与阈值过滤"""
        results = []
        input_len = len(input_codes)
        
        for hw, hw_codes in candidates:
            hw_len = len(hw_codes)
            
            # 长度过滤：热词太长或太短都不可能匹配
            if hw_len > input_len + 3: continue
            
            # 计算距离
            if HAS_NUMBA:
                min_dist = _fuzzy_substring_distance_numba(input_codes, hw_codes)
            else:
                min_dist = self._python_distance(input_codes, hw_codes)
            
            # 计算分数 (1 - 归一化距离)
            score = 1.0 - (min_dist / hw_len)
            if score >= self.threshold:
                results.append((hw, round(score, 3)))
        return results

    def compute_score(self, input_phonemes: List[str], hotword_phonemes: List[str]) -> float:
        """
        计算单个热词的精确分数 (用于重排序)
        """
        input_codes = self.index.encode_input(input_phonemes)
        hw_codes = self.index.encode_input(hotword_phonemes)
        
        hw_len = len(hw_codes)
        if hw_len == 0:
            return 0.0
            
        if HAS_NUMBA:
            min_dist = _fuzzy_substring_distance_numba(input_codes, hw_codes)
        else:
            min_dist = self._python_distance(input_codes, hw_codes)
            
        return max(0.0, 1.0 - (min_dist / hw_len))

    
    def _python_distance(self, main_codes: np.ndarray, sub_codes: np.ndarray) -> float:
        """纯 Python 版本（Numba 不可用时）"""
        n = len(sub_codes)
        m = len(main_codes)
        
        if n == 0 or m == 0:
            return float(n)
        
        dp = [[0.0] * (m + 1) for _ in range(n + 1)]
        
        for i in range(1, n + 1):
            dp[i][0] = float(i)
        
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                cost = 0.0 if sub_codes[i-1] == main_codes[j-1] else 1.0
                dp[i][j] = min(
                    dp[i-1][j] + 1.0,
                    dp[i][j-1] + 1.0,
                    dp[i-1][j-1] + cost
                )
        
        return min(dp[n][j] for j in range(1, m + 1))


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    import random
    from util.hotword.algo_phoneme import get_phoneme_seq
    
    logging.basicConfig(level=logging.INFO)
    
    print(f"\n=== 高性能 RAG 测试 ===")
    print(f"Numba 可用: {HAS_NUMBA}")
    
    # 生成测试数据
    chinese_chars = '的一是不了在人有我他这个们中来上大为和国地到以说时要就出会可也你对生能而子那得于着下自之年过发后作里如等'
    
    print("\n生成 10000 个热词...")
    hotwords = {}
    for i in range(10000):
        length = random.randint(2, 4)
        word = ''.join(random.choice(chinese_chars) for _ in range(length))
        phonemes = get_phoneme_seq(word)
        hotwords[word] = phonemes
    
    # 创建 FastRAG
    print("构建索引...")
    start = time.time()
    rag = FastRAG(threshold=0.6)
    rag.add_hotwords(hotwords)
    print(f"  索引构建耗时: {time.time() - start:.3f}s")
    
    # 生成输入
    input_text = ''.join(random.choice(chinese_chars) for _ in range(100))
    input_phonemes = get_phoneme_seq(input_text)
    print(f"\n输入: {input_text[:50]}... ({len(input_text)}字, {len(input_phonemes)}音素)")
    
    # 预热 Numba
    if HAS_NUMBA:
        print("\n预热 Numba JIT...")
        _ = rag.search(input_phonemes[:10], top_k=3)
    
    # 测试性能
    print("\n测试检索性能...")
    start = time.time()
    results = rag.search(input_phonemes, top_k=10)
    elapsed = time.time() - start
    
    print(f"  检索耗时: {elapsed:.3f}s")
    print(f"  热词总数: {rag.hotword_count}")
    print(f"  候选数量: {len(rag.index.get_candidates(input_phonemes))}")
    print(f"  结果: {results[:5]}")
