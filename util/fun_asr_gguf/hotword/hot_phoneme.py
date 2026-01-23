# coding: utf-8
"""
基于 RAG 的拼音纠错模块

使用音素编辑距离进行模糊匹配，实现智能热词替换。
"""

import logging
import os
import time
import threading
from typing import List, Tuple, Dict, Set, Optional, NamedTuple
from collections import defaultdict
from pathlib import Path

from .algo_phoneme import get_phoneme_info, Phoneme
from .rag_fast import FastRAG
from .algo_calc import fast_substring_score, fuzzy_substring_score, fuzzy_substring_search_constrained

# 使用统一的 logger（从 __init__.py 导入）
from . import logger


class MatchResult(NamedTuple):
    start: int
    end: int
    score: float
    hotword: str


class CorrectionResult(NamedTuple):
    """纠错结果，包含纠错后的文本和匹配的热词列表"""
    text: str                           # 纠错后的文本
    matchs: List[Tuple[str, str, float]]  # [(原词, 热词, 分数), ...]
    similars: List[Tuple[str, str, float]]  # [(原词, 热词, 分数), ...]
    


class PhonemeCorrector:
    """
    拼音纠错器

    使用两阶段检索策略：
    1. FastRAG 粗筛：使用倒排索引 + Numba JIT 快速过滤候选
    2. AccuRAG 精确计算：使用模糊音权重进行精确匹配

    优势：
    - FastRAG 倒排索引减少 90% 计算量
    - AccuRAG 保留模糊音权重精度 (前后鼻音、平翘舌等)
    - 适合任意规模热词库

    并将相似度超过阈值的片段替换为热词。
    """

    def __init__(self, threshold: float = 0.7, similar_threshold: float = None):
        """
        初始化拼音纠错器
        """
        self.threshold = threshold
        self.similar_threshold = similar_threshold if similar_threshold is not None else threshold - 0.2
        
        self.max_diff = 2             # 滑窗匹配中允许的最大音素差异数
        self.top_k_candidates = 100   # 粗筛保留的候选词数
        
        self.hotwords: Dict[str, List[Phoneme]] = {}
        self.fast_rag = FastRAG(threshold=min(self.threshold, self.similar_threshold) - 0.1)
        self._lock = threading.Lock()

    def update_hotwords(self, hotword_text: str) -> int:
        """更新纠错热词库 (线程安全)"""
        start_time = time.time()
        
        # 预析取有效行
        lines = [line.strip() for line in hotword_text.splitlines() if line.strip() and not line.strip().startswith('#')]
        
        new_hotwords = {}
        for hw in lines:
            phons = get_phoneme_info(hw)
            if phons:
                new_hotwords[hw] = phons
        
        with self._lock:
            self.hotwords = new_hotwords
            self.fast_rag = FastRAG(threshold=min(self.threshold, self.similar_threshold) - 0.1)
            self.fast_rag.add_hotwords(new_hotwords)
        
        logger.debug(f"PhonemeCorrector 已更新 {len(new_hotwords)} 个热词，耗时 {time.time() - start_time:.3f}s")
        return len(new_hotwords)

    def _find_matches(self, text: str, fast_results: List, input_processed: List[Tuple]) -> Tuple[List[MatchResult], List[Tuple[str, str, float]]]:
        """精细匹配逻辑：边界约束的模糊搜索"""
        matches = []
        similars = []
        
        # 预先根据相似度阈值过滤 fast_results，减少重复计算
        for hw, fast_score in fast_results:
            hw_phonemes = self.hotwords[hw]
            hw_compare = [p.info[:5] for p in hw_phonemes]
            
            # 使用新算法：在输入序列中一站式搜索所有符合边界的最优区域
            # 为 Similar 列表使用更宽松的 initial 阈值，确保能抓到压线匹配
            search_threshold = min(self.threshold, self.similar_threshold) - 0.1
            
            # 搜索匹配
            found_segments = fuzzy_substring_search_constrained(hw_compare, input_processed, threshold=search_threshold)
            
            for score, start_phon_idx, end_phon_idx in found_segments:
                # 从 input_processed 直接拿 char 索引
                char_start = input_processed[start_phon_idx][5]
                char_end = input_processed[end_phon_idx-1][6]
                
                res = MatchResult(char_start, char_end, score, hw)
                origin_val = text[char_start:char_end]
                
                # 分类到 matches 和 similars
                if score >= self.threshold:
                    matches.append(res)
                
                # 所有超过相似度阈值的都记入 similars（用于提示）
                if score >= self.similar_threshold:
                    similars.append((origin_val, hw, score))

        # 潜在热词去重与排序 (不再简单按 seen_hw 排重，而是按分数和覆盖范围排序)
        # 为潜在建议列表保留前 k 个最相关的不同热词
        final_similars = []
        seen_hw = set()
        
        # 按得分降序，同分按长度降序
        similars.sort(key=lambda x: (x[2], len(x[1])), reverse=True)
        
        for origin, hw, score in similars:
            if hw not in seen_hw:
                final_similars.append((origin, hw, score))
                seen_hw.add(hw)
                
        return matches, final_similars

    def _resolve_and_replace(self, text: str, matches: List[MatchResult]) -> Tuple[str, List[Tuple[str, float]], List[Tuple[str, float]]]:
        """冲突去重与文本替换"""
        # 分数优先 > 长度优先
        matches.sort(key=lambda x: (x.score, x.end - x.start), reverse=True)
        
        final_matches = []
        all_matched_info = []
        occupied_ranges = []

        seen_hw_score = set()
        for m in matches:
            if (m.hotword, m.score) not in seen_hw_score:
                all_matched_info.append((m.hotword, m.score))
                seen_hw_score.add((m.hotword, m.score))

            if m.score < self.threshold: continue
            
            is_overlap = False
            for r_start, r_end in occupied_ranges:
                if not (m.end <= r_start or m.start >= r_end):
                    is_overlap = True
                    break
            
            if not is_overlap:
                # 检查是否真的有变化（避免原地替换）
                if text[m.start : m.end] != m.hotword:
                    final_matches.append(m)
                occupied_ranges.append((m.start, m.end))

        # 执行替换
        final_matches.sort(key=lambda x: x.start, reverse=True)
        result_list = list(text)
        for m in final_matches:
            result_list[m.start : m.end] = list(m.hotword)
            
        return "".join(result_list), [(text[m.start:m.end], m.hotword, m.score) for m in final_matches], all_matched_info

    def correct(self, text: str, k: int = 10) -> CorrectionResult:
        """
        执行纠错替换

        Args:
            text: 输入文本
            k: 返回上下文相关的前 k 个热词
        """
        if not text or not self.hotwords:
            return CorrectionResult(text=text, matchs=[], similars=[])

        # 1. 提取带位置信息的音素序列
        input_phonemes = get_phoneme_info(text)
        if not input_phonemes:
            return CorrectionResult(text=text, matchs=[], similars=[])

        # DEBUG: 检查 input_phonemes 的类型和内容
        logger.debug(f"[DEBUG] input_phonemes type: {type(input_phonemes)}")
        if input_phonemes:
            logger.debug(f"[DEBUG] input_phonemes[0] type: {type(input_phonemes[0])}, value: {input_phonemes[0]}")
            logger.debug(f"[DEBUG] input_phonemes[0].info type: {type(input_phonemes[0].info)}, value: {input_phonemes[0].info}")

        # 2. 检索与匹配
        with self._lock:
            # 粗筛
            fast_results = self.fast_rag.search(input_phonemes, top_k=100)
            logger.debug(f"[DEBUG] fast_results type: {type(fast_results)}, count: {len(fast_results)}")

            # 预处理输入 (转换为全能七元组：值, 语言, 字始, 字终, 是调, 始位, 终位)
            try:
                input_processed = [p.info for p in input_phonemes]
                logger.debug(f"[DEBUG] input_processed type: {type(input_processed)}, count: {len(input_processed)}")
                if input_processed:
                    logger.debug(f"[DEBUG] input_processed[0] type: {type(input_processed[0])}, value: {input_processed[0]}")
            except Exception as e:
                logger.error(f"[ERROR] Failed to build input_processed: {e}")
                logger.error(f"[ERROR] input_phonemes details: {[(type(p), p) for p in input_phonemes[:5]]}")
                raise

            # 精筛
            matches, similars = self._find_matches(text, fast_results, input_processed)

        # 3. 冲突解决与替换
        new_text, final_hw_info, all_hw_info = self._resolve_and_replace(text, matches)
        
        # similars 已经是 [(origin, hw, score), ...] 的元组列表
        return CorrectionResult(text=new_text, matchs=final_hw_info, similars=similars[:k])


if __name__ == "__main__":
    from .. import setup_logging
    setup_logging(level=logging.DEBUG)
    
    print("\n--- PhonemeCorrector 测试 ---")
    corrector = PhonemeCorrector(threshold=0.7)
    
    hotwords = """
# 中文热词
撒贝宁
康辉
周涛
乐清
东方财富
科大讯飞

# 英文热词
CapsWriter
Python
Microsoft
iPhone
7-Zip

# 杂项
Claude
Bilibili
Microsoft
麦当劳
肯德基
VsCode
七浦路
句子
    """
    corrector.update_hotwords(hotwords)
    
    print("\n=== 中文测试 ===")
    test_cases_zh = [
        "我非常喜欢撒贝你说的新闻",
        "康灰是央视著名主持人",
        "今天天气真不错",
        "在月清这个地方",
        "东方菜富股票上涨了",
        "科大迅飞的语音识别",
        "我想去吃买当劳和啃得鸡",
        "喜欢刷Bili Bili",
        "请把那个锯子发给我一下",
        "我很喜欢 cloud",
    ]
    for text in test_cases_zh:
        result = corrector.correct(text)
        print(f"  '{text}' -> '{result.text}'")
        if result.matchs:
            print(f"    匹配热词: {result.matchs}")
        if result.similars:
            print(f"    相似热词: {result.similars}")
    
    print("\n=== 英文测试 ===")
    test_cases_en = [
        "use caps riter to type",
        "download pythn code",
        "install micro soft office",
        "my i fone is broken",
        "compress with 7 zip",
    ]
    for text in test_cases_en:
        result = corrector.correct(text)
        print(f"  '{text}' -> '{result.text}'")
        if result.matchs:
            print(f"    匹配热词: {result.matchs}")
        if result.similars:
            print(f"    相似热词: {result.similars}")

    # =====================================================================
    # 对比测试: FastRAG (粗筛) vs AccuRAG (精筛)
    # =====================================================================
    print("\n" + "="*70)
    print("【对比测试】FastRAG (粗筛) vs AccuRAG (精筛)")
    print("="*70)

    # 导入
    from .rag_fast import FastRAG
    from .rag_accu import AccuRAG
    from .algo_phoneme import get_phoneme_info

    # 构建热词映射
    hotword_map = {}
    for word in [line.strip() for line in hotwords.splitlines()
                    if line.strip() and not line.strip().startswith('#')]:
        phonemes = get_phoneme_info(word)
        if phonemes:
            hotword_map[word] = phonemes

    # 创建检索器
    fast_rag = FastRAG(threshold=0.6)  # FastRAG 阈值稍低
    fast_rag.add_hotwords(hotword_map)
    
    accu_rag = AccuRAG(threshold=0.6)
    accu_rag.update_hotwords(hotword_map)

    print(f"\n测试用例:")
    comparison_tests = test_cases_zh + test_cases_en

    # 打印格式说明
    # print(f"\n{'输入文本':<20} {'FastRAG (Top1)':<25} {'AccuRAG (Top1)':<25}")
    # print("-"*80)

    for text in comparison_tests:
        input_phonemes = get_phoneme_info(text)
        
        # 1. FastRAG 检索
        fast_results = fast_rag.search(input_phonemes, top_k=5)
        # 格式化列表: [(词, 分数), ...]
        fast_str = str([(h, f"{s:.2f}") for h, s in fast_results])
        
        # 2. AccuRAG 检索
        accu_results = accu_rag.search(input_phonemes, top_k=5)
        # 格式化列表: [(词, 分数), ...] - AccuRAG returns (hw, score, start, end)
        accu_str = str([(h, f"{s:.2f}") for h, s, _, _ in accu_results])

        print(f"Original: {text}")
        print(f"    FastRAG: {fast_str}")
        print(f"    AccuRAG: {accu_str}")

    print("="*70)

    # =====================================================================
    # 性能测试
    # =====================================================================
    print("\n" + "="*70)
    print("【性能测试】5000+ 热词检索耗时")
    print("="*70)

    # 准备长文本输入
    long_text = "撒贝你主持康灰的节目，在东方菜富和科大迅飞工作的月清员工"
    input_phonemes = get_phoneme_info(long_text)
    print(f"输入: {long_text}")
    print(f"音素数: {len(input_phonemes)}")

    # 测试 PhonemeCorrector
    iterations = 100
    start = time.time()
    for _ in range(iterations):
        _ = corrector.correct(long_text)
    pc_time = (time.time() - start) / iterations * 1000

    print(f"\n平均耗时: {pc_time:.2f}ms / iter")
    print("="*70)
