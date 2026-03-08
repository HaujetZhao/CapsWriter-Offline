# coding: utf-8
"""
高性能 RAG 加速模块

使用以下技术优化检索性能：
1. 锚点搜索 (Anchor Scanning) 缩小搜索范围
2. 首音素倒排索引极速过滤
3. 纯 Python 极限循环优化 (属性提取与剪枝)
"""

# 彻底移除 Numba 兼容逻辑，保持代码清晰
from typing import List, Dict, Tuple, Set, Union
from collections import defaultdict
import time
from . import logger

HAS_NUMBA = False


# =============================================================================
# 音素编码器（字符串 -> 整数）
# =============================================================================

from .algo_phoneme import Phoneme
from .algo_calc import SIMILAR_PHONEMES

class PhonemeEncoder:
    """将音素字符串编码为整数，加速比较效率"""
    
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
    
    def encode_sequence(self, phonemes: List[str]) -> List[int]:
        """将音素序列编码为整数列表"""
        return [self.encode(p) for p in phonemes]

    def get_similar_codes(self, code: int) -> List[int]:
        """获取相似音素的编码列表"""
        if not hasattr(self, '_sim_map'):
            # 延迟初始化相似地图
            self._sim_map = defaultdict(list)
            for s_set in SIMILAR_PHONEMES:
                codes = [self.phoneme_to_code.get(p) for p in s_set if p in self.phoneme_to_code]
                for c1 in codes:
                    for c2 in codes:
                        if c1 != c2: self._sim_map[c1].append(c2)
        return self._sim_map.get(code, [])


# =============================================================================
# 倒排索引
# =============================================================================

class PhonemeIndex:
    """
    多音素倒排索引
    
    按热词前几个音素分桶，检索时只匹配音素在输入中出现过的热词，减少计算量。
    - 中文：索引前两个音素（声母+韵母，即第一个字的完整拼音）
    - 英文：索引前两个音素（容错首音素识别错误，如 klaude -> Claude）
    """
    
    def __init__(self):
        self.encoder = PhonemeEncoder()
        # {音素编码: [(热词原文, 整数列表), ...]}
        self.index: Dict[int, List[Tuple[str, List[int]]]] = defaultdict(list)
        self.all_hotwords: List[Tuple[str, List[int]]] = []
        
    def add(self, hotword: str, phonemes: List[Phoneme]):
        """添加热词到索引，内部自动决定索引哪些位置"""
        if not phonemes:
            return
        
        # 将音素对象编码为整数 ID 序列
        phoneme_strs = [p.value for p in phonemes]
        codes = self.encoder.encode_sequence(phoneme_strs)
        
        # 索引策略：统一索引前两个音素
        # - 中文：声母+韵母（第一个字的完整拼音）
        # - 英文：前两个音素（容错首音素识别错误，如 klaude -> Claude）
        limit = min(len(codes), 2)
        indices = list(range(limit))
            
        # 收集去重后的 target_codes
        target_codes = {codes[i] for i in indices if i < len(codes)}
        
        for code in target_codes:
            self.index[code].append((hotword, codes))
            
        self.all_hotwords.append((hotword, codes))
        
    def get_candidates(self, input_codes: List[int]) -> List[Tuple[str, List[int], List[int]]]:
        """
        获取候选热词及其在输入中出现的索引位置 (锚点)
        """
        # 收集输入中音素出现的全部位置 {code: [idx1, idx2, ...]}
        code_positions = defaultdict(list)
        for idx, code in enumerate(input_codes):
            code_positions[code].append(idx)
            # [性能优化] 同时将相似音素的位置也统计进来，增加召回鲁棒性
            for sim_code in self.encoder.get_similar_codes(code):
                code_positions[sim_code].append(idx)
            
        # 收集候选与其锚点位置
        candidate_data = {} # {hw: (codes, [positions])}
        for code, positions in code_positions.items():
            for hw, codes in self.index.get(code, []):
                if hw not in candidate_data:
                    candidate_data[hw] = (codes, [])
                candidate_data[hw][1].extend(positions)

        # 格式化输出 [(hw, codes, [pos1, ...]), ...]
        return [(hw, data[0], sorted(list(set(data[1])))) for hw, data in candidate_data.items()]
    
    def encode_input(self, phonemes: List[Phoneme]) -> List[int]:
        """编码输入序列"""
        return [self.encoder.encode(p.value) for p in phonemes]


# =============================================================================
# 高性能 RAG 检索器
# =============================================================================

class FastRAG:
    """
    高性能 RAG 检索器
    
    特点：
    1. 纯 Python 实现，易于维护与部署
    2. 基于锚点的局部扫描算法
    3. 长度过滤与 DP 剪枝
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

        logger.debug(f"[DEBUG] FastRAG.search: input_phonemes type={type(input_phonemes)}, len={len(input_phonemes)}")
        if input_phonemes:
            logger.debug(f"[DEBUG] FastRAG.search: input_phonemes[0] type={type(input_phonemes[0])}, value={input_phonemes[0]}")

        # 1. 编码输入并获取候选
        input_codes = self.index.encode_input(input_phonemes)
        candidates = self.index.get_candidates(input_codes)

        # 2. 遍历打分与过滤
        results = self._score_candidates(input_codes, candidates)

        # 3. 排序并截断
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _score_candidates(self, input_list: List[int], candidates: List[Tuple[str, List[int], List[int]]]) -> List[Tuple[str, float, int]]:
        """对候选列表进行局部扫描打分"""
        results = []
        input_len = len(input_list)
        
        for hw, hw_list, anchors in candidates:
            hw_len = len(hw_list)
            
            best_score = -1.0
            best_end_pos = -1
            
            # [深度优化] 锚点扫描：不再全量扫描，只在索引命中的位置附近开窗
            # 每个热词可能在多个位置命中索引（例如“的”出现多次）
            for anchor in anchors:
                # 窗口范围：锚点是第一个音素匹配的位置
                # 扫描范围：[anchor, anchor + hw_len + buffer]
                # 加一个小的 buffer (如 3) 以容纳轻微的插入错误
                scan_start = max(0, anchor - 2)
                scan_end = min(input_len, anchor + hw_len + 3)
                
                local_input = input_list[scan_start:scan_end]
                if not local_input: continue
                
                # 计算局部距离
                dist, local_end = self._python_distance_simple(local_input, hw_list)
                
                score = 1.0 - (dist / hw_len)
                if score > best_score:
                    best_score = score
                    best_end_pos = scan_start + local_end
            
            if best_score >= self.threshold:
                results.append((hw, round(best_score, 3), best_end_pos))
        return results

    def _python_distance_simple(self, main_list: List[int], sub_list: List[int]) -> Tuple[float, int]:
        """局部扫描专用的简化版编辑距离，不需要 curr[0]=0 的逻辑"""
        n = len(sub_list)
        m = len(main_list)
        
        # 局部窗口已经对齐起始，所以使用标准编辑距离初始化
        prev = [float(i) for i in range(n + 1)]
        curr = [0.0] * (n + 1)
        
        best_dist = float('inf')
        best_pos = 0
        
        for j in range(1, m + 1):
            curr[0] = float(j) # 标准编辑距离，左边是插入成本
            m_val = main_list[j-1]
            for i in range(1, n + 1):
                cost = 0.0 if sub_list[i-1] == m_val else 1.0
                d_del = prev[i] + 1.0
                d_ins = curr[i-1] + 1.0
                d_match = prev[i-1] + cost
                
                if d_del < d_ins:
                    if d_del < d_match: curr[i] = d_del
                    else: curr[i] = d_match
                else:
                    if d_ins < d_match: curr[i] = d_ins
                    else: curr[i] = d_match
            
            # 记录窗口内的最佳结束位置
            if curr[n] <= best_dist:
                best_dist = curr[n]
                best_pos = j
            prev[:] = curr[:]
            
        return best_dist, best_pos

    def _python_distance(self, main_list: List[int], sub_list: List[int]) -> float:
        """标准模糊子串距离计算 (纯 Python)"""
        n, m = len(sub_list), len(main_list)
        if n == 0: return 0.0
        if m == 0: return float(n)
        
        prev = [float(i) for i in range(n + 1)]
        curr = [0.0] * (n + 1)
        best_dist = float(n)

        for j in range(1, m + 1):
            curr[0] = 0.0 # 允许从任意处开始
            m_val = main_list[j-1]
            for i in range(1, n + 1):
                cost = 0.0 if sub_list[i-1] == m_val else 1.0
                curr[i] = min(prev[i] + 1.0, curr[i-1] + 1.0, prev[i-1] + cost)
            if curr[n] < best_dist: best_dist = curr[n]
            prev[:] = curr[:]
        return best_dist


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    import random
    from .algo_phoneme import get_phoneme_seq
    
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
