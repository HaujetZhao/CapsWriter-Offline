# coding: utf-8
"""
基于 RAG 的拼音纠错模块

使用音素编辑距离进行模糊匹配，实现智能热词替换。
"""

import threading
from typing import List, Tuple, Dict, NamedTuple
import time

import logging

from .algo_phoneme import get_phoneme_info
from .algo_calc import find_best_match

logger = logging.getLogger(__name__)


class MatchResult(NamedTuple):
    start: int
    end: int
    score: float
    hotword: str


class CorrectionResult(NamedTuple):
    """纠错结果，包含纠错后的文本和匹配的热词列表"""
    text: str                           # 纠错后的文本
    matched_hotwords: List[Tuple[str, float]]  # [(热词, 分数), ...]


class PhonemeCorrector:
    """
    拼音纠错器

    使用由于编辑距离算法，在输入文本中模糊查找热词，
    并将相似度超过阈值的片段替换为热词。
    """

    def __init__(self, threshold: float = 0.6):
        """
        初始化拼音纠错器

        Args:
            threshold: 相似度阈值 (0-1)，越高越严格
        """
        self.threshold = threshold
        self.hotwords: Dict[str, List[str]] = {}  # {hotword: phoneme_seq}
        self._lock = threading.Lock()

    def update_hotwords(self, hotword_text: str) -> int:
        """
        更新热词列表（线程安全）

        Args:
            hotword_text: 热词文本，每行一个

        Returns:
            加载的热词数量
        """
        new_hotwords = {}
        
        # 预计算所有热词的音素
        lines = [line.strip() for line in hotword_text.splitlines() if line.strip() and not line.strip().startswith('#')]
        
        start_time = time.time()
        for word in lines:
            phonemes, _ = get_phoneme_info(word)
            if phonemes:
                new_hotwords[word] = phonemes
        
        with self._lock:
            self.hotwords = new_hotwords
            
        logger.debug(f"PhonemeCorrector 已更新 {len(new_hotwords)} 个热词，耗时 {time.time() - start_time:.3f}s")
        return len(new_hotwords)

    def correct(self, text: str) -> CorrectionResult:
        """
        执行纠错替换

        Args:
            text: 原始文本

        Returns:
            CorrectionResult(text=纠错后的文本, matched_hotwords=匹配的热词列表)
            matched_hotwords 可直接传给 LLMHotwordRAG.search() 的 precomputed_results 参数
        """
        if not text or not self.hotwords:
            return CorrectionResult(text=text, matched_hotwords=[])

        # 1. 获取输入文本的音素序列和字符索引映射
        input_phonemes, char_indices = get_phoneme_info(text)
        if not input_phonemes:
            return CorrectionResult(text=text, matched_hotwords=[])

        # 2. 寻找所有可能的匹配
        matches: List[MatchResult] = []
        
        with self._lock:
            # 复制引用以避免迭代时被修改
            current_hotwords = self.hotwords.copy()

        for hw, hw_phonemes in current_hotwords.items():
            # 优化：如果热词长度差距太大，直接跳过 (例如 input 很短，hotword 很长)
            if len(hw_phonemes) > len(input_phonemes) + 2:
                continue

            score, start_idx, end_idx = find_best_match(input_phonemes, hw_phonemes)
            
            if score >= self.threshold:
                # 转换回字符索引
                # start_idx 是包含的，end_idx 是不包含的
                # 如果 start_idx >= len(char_indices), 说明匹配越界了? find_best_match 应该保证 index 在 range 内
                
                if start_idx < len(char_indices) and end_idx > 0 and end_idx <= len(char_indices):
                     # 获取字符级别的起始和结束位置
                    char_start = char_indices[start_idx][0]
                    # end_idx 是 exclusive，但 char_indices 也是 0-indexed 的 list
                    # char_indices[end_idx-1] 是最后一个匹配的音素
                    char_end = char_indices[end_idx-1][1]
                    
                    matches.append(MatchResult(char_start, char_end, score, hw))

        if not matches:
            return CorrectionResult(text=text, matched_hotwords=[])
        
        # 收集所有匹配的热词（用于 LLM 上下文）
        all_matched_hotwords = [(m.hotword, m.score) for m in matches]

        # 3. 解决重叠匹配
        # 策略：分数优先，其次长度优先
        matches.sort(key=lambda x: (x.score, x.end - x.start), reverse=True)
        
        final_matches = []
        occupied_ranges = [] # [(start, end)]

        for m in matches:
            is_overlap = False
            for r_start, r_end in occupied_ranges:
                # 检查区间重叠: not (end1 <= start2 or start1 >= end2)
                if not (m.end <= r_start or m.start >= r_end):
                    is_overlap = True
                    break
            
            if not is_overlap:
                final_matches.append(m)
                occupied_ranges.append((m.start, m.end))

        # 4. 执行替换
        # 按起始位置排序，从后往前替换，以免影响前面的索引
        final_matches.sort(key=lambda x: x.start, reverse=True)
        
        result_text = text
        for m in final_matches:
            original_segment = result_text[m.start:m.end]
            # 如果原文已经完全一样，就不替换了（虽然分数可能是 1.0）
            if original_segment == m.hotword:
                continue
                
            logger.info(f"拼音纠错: '{original_segment}' -> '{m.hotword}' (相似度: {m.score:.2f})")
            result_text = result_text[:m.start] + m.hotword + result_text[m.end:]
            
        return CorrectionResult(text=result_text, matched_hotwords=all_matched_hotwords)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
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
    ]
    for text in test_cases_zh:
        result = corrector.correct(text)
        print(f"  '{text}' -> '{result.text}'")
        if result.matched_hotwords:
            print(f"    匹配热词: {result.matched_hotwords}")
    
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
        if result.matched_hotwords:
            print(f"    匹配热词: {result.matched_hotwords}")

