# coding: utf-8
"""
基于 RAG 的拼音纠错模块

使用音素编辑距离进行模糊匹配，实现智能热词替换。
"""

import threading
from typing import List, Tuple, Dict, NamedTuple
import time

import logging

from .algo_phoneme import get_phoneme_info, Phoneme
from .rag_accu import AccuRAG
from .rag_fast import FastRAG

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

    使用两阶段检索策略：
    1. FastRAG 粗筛：使用倒排索引 + Numba JIT 快速过滤候选
    2. AccuRAG 精确计算：使用模糊音权重进行精确匹配

    优势：
    - FastRAG 倒排索引减少 90% 计算量
    - AccuRAG 保留模糊音权重精度 (前后鼻音、平翘舌等)
    - 适合任意规模热词库

    并将相似度超过阈值的片段替换为热词。
    """

    def __init__(self, threshold: float = 0.6, similar_threshold: float = None):
        """
        初始化拼音纠错器

        Args:
            threshold: 替换阈值 (0-1)，越高越严格，用于实际替换操作
            similar_threshold: 相似列表阈值 (0-1)，低于替换阈值，用于 LLM 上下文
                             如果为 None，则自动设为 threshold - 0.2
        """
        self.threshold = threshold  # 替换阈值（高阈值，避免误替换）
        self.similar_threshold = similar_threshold if similar_threshold is not None else threshold - 0.2
        self.hotwords: Dict[str, List[Phoneme]] = {}  # {hotword: phoneme_seq}
        self._lock = threading.Lock()

        # 两阶段检索组件
        self.accu_rag = AccuRAG(threshold=threshold)
        self.fast_rag = FastRAG(threshold=threshold - 0.1)  # 第一阶段阈值放宽

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

            # 更新两阶段检索
            self.accu_rag.update_hotwords(new_hotwords)
            self.fast_rag.add_hotwords(new_hotwords)

        logger.debug(f"PhonemeCorrector 已更新 {len(new_hotwords)} 个热词，耗时 {time.time() - start_time:.3f}s")
        return len(new_hotwords)

    def correct(self, text: str) -> CorrectionResult:
        """
        执行纠错替换

        Args:
            text: 原始文本

        Returns:
            CorrectionResult(text=纠错后的文本, matched_hotwords=匹配的热词列表)
            matched_hotwords 可直接传给 HotwordRAG.search() 的 precomputed_results 参数
        """
        if not text or not self.hotwords:
            return CorrectionResult(text=text, matched_hotwords=[])

        # 1. 获取输入文本的音素序列和字符索引映射
        input_phonemes, char_indices = get_phoneme_info(text)
        if not input_phonemes:
            return CorrectionResult(text=text, matched_hotwords=[])

        # 2. 两阶段检索寻找匹配
        matches: List[MatchResult] = []
        all_matches: List[MatchResult] = []  # 用于相似列表（包含低阈值匹配）

        with self._lock:
            # 阶段1: FastRAG 粗筛 (快速获取候选，使用相似列表阈值)
            fast_results = self.fast_rag.search(input_phonemes, top_k=100)
            candidate_hws = [hw for hw, _ in fast_results]

            # 阶段2: AccuRAG 精确计算 (禁用阈值过滤，获取所有候选)
            precise_results = self.accu_rag.search(
                input_phonemes,
                candidate_hws=candidate_hws,
                top_k=50,
                apply_threshold=False  # 不过滤，获取所有候选
            )

        # 转换结果为 MatchResult
        for hw, score, start_idx, end_idx in precise_results:
            if start_idx < len(char_indices) and end_idx > 0 and end_idx <= len(char_indices):
                char_start = char_indices[start_idx][0]
                char_end = char_indices[end_idx-1][1]
                match = MatchResult(char_start, char_end, score, hw)
                all_matches.append(match)

                # 只将高阈值匹配加入替换列表
                if score >= self.threshold:
                    matches.append(match)

        if not all_matches:
            return CorrectionResult(text=text, matched_hotwords=[])

        # 收集所有匹配的热词（用于 LLM 上下文）- 使用相似列表阈值过滤
        # 按分数从高到低排序
        all_matched_hotwords = sorted(
            [(m.hotword, m.score) for m in all_matches if m.score >= self.similar_threshold],
            key=lambda x: x[1],
            reverse=True
        )

        if not matches:
            # 没有达到替换阈值，直接返回原文本和相似热词列表
            return CorrectionResult(text=text, matched_hotwords=all_matched_hotwords)

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

            logger.info(f"音素纠错: '{original_segment}' -> '{m.hotword}' (相似度: {m.score:.2f})")
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

    print("\n=== 股票热词测试 (stocks.txt) ===")
    # 读取 stocks.txt 文件
    import os
    import time
    stocks_path = os.path.join(os.path.dirname(__file__), "stocks.txt")
    if os.path.exists(stocks_path):
        with open(stocks_path, "r", encoding="utf-8") as f:
            stocks_text = f.read()
        count = corrector.update_hotwords(stocks_text)
        print(f"已加载 {count} 个股票热词")

        # 测试股票名称的纠错
        test_cases_stocks = [
            "我看好平昂银行的发展",  # 平安银行
            "中选天楹发布了财报",     # 中国天楹
            "科打讯飞的语音技术很强",  # 科大讯飞
            "格力电汽股价上涨",        # 格力电器
            "招商 Yin行很不错",         # 招商银行
            "我想买一点贵州茂台",       # 贵州茅台
            "比亚迪汽车销量不错",       # 比亚迪 (完全匹配)
            "宁波 Fang展",              # 宁波银行
        ]
        for text in test_cases_stocks:
            result = corrector.correct(text)
            print(f"  '{text}' -> '{result.text}'")
            if result.matched_hotwords:
                # 只显示前3个匹配的热词，避免输出过长
                displayed = result.matched_hotwords[:3]
                if len(result.matched_hotwords) > 3:
                    displayed.append(f"...(共{len(result.matched_hotwords)}个)")
                print(f"    匹配热词: {displayed}")

        # =====================================================================
        # 对比测试: PhonemeCorrector vs FastRAG 结果一致性验证
        # =====================================================================
        print("\n" + "="*70)
        print("【对比测试】PhonemeCorrector vs FastRAG 结果一致性")
        print("="*70)

        # 导入 FastRAG
        from .rag_fast import FastRAG
        from .algo_phoneme import get_phoneme_info

        # 构建热词映射
        hotword_map = {}
        for word in [line.strip() for line in stocks_text.splitlines()
                     if line.strip() and not line.strip().startswith('#')]:
            phonemes, _ = get_phoneme_info(word)
            if phonemes:
                hotword_map[word] = phonemes

        # 创建 FastRAG
        fast_rag = FastRAG(threshold=0.7)
        fast_rag.add_hotwords(hotword_map)

        print(f"\n测试用例:")
        comparison_tests = [
            "撒贝你主持节目",
            "康灰是央视主持人",
            "东方菜富股票",
            "科大迅飞语音",
            "月清这个地方",
        ]

        print(f"\n{'输入文本':<20} {'PhonemeCorrector':<25} {'FastRAG':<25} {'一致?'}")
        print("-"*70)

        all_match = True
        for text in comparison_tests:
            # PhonemeCorrector 结果
            result_pc = corrector.correct(text)
            pc_top = result_pc.matched_hotwords[0] if result_pc.matched_hotwords else None

            # FastRAG 结果
            input_phonemes, _ = get_phoneme_info(text)
            fast_results = fast_rag.search(input_phonemes, top_k=1)
            fast_top = fast_results[0] if fast_results else None

            # 对比
            pc_str = f"{pc_top[0]}({pc_top[1]:.2f})" if pc_top else "无匹配"
            fast_str = f"{fast_top[0]}({fast_top[1]:.2f})" if fast_top else "无匹配"

            is_match = (pc_top and fast_top and
                       pc_top[0] == fast_top[0] and
                       abs(pc_top[1] - fast_top[1]) < 0.01)
            status = "✓" if is_match else "✗"

            if not is_match:
                all_match = False

            print(f"{text:<20} {pc_str:<25} {fast_str:<25} {status}")

        print("="*70)
        if all_match:
            print("✓ 两种方法结果完全一致")
        else:
            print("✗ 存在不一致，请检查算法实现")

        # =====================================================================
        # 性能对比测试
        # =====================================================================
        print("\n" + "="*70)
        print("【性能对比】5000+ 热词检索耗时")
        print("="*70)

        # 准备长文本输入
        long_text = "撒贝你主持康灰的节目，在东方菜富和科大迅飞工作的月清员工"
        input_phonemes, _ = get_phoneme_info(long_text)
        print(f"输入: {long_text}")
        print(f"音素数: {len(input_phonemes)}")

        # 测试 PhonemeCorrector (传统算法)
        iterations = 10
        start = time.time()
        for _ in range(iterations):
            _ = corrector.correct(long_text)
        pc_time = (time.time() - start) / iterations * 1000

        # 测试 FastRAG
        start = time.time()
        for _ in range(iterations):
            _ = fast_rag.search(input_phonemes, top_k=10)
        fast_time = (time.time() - start) / iterations * 1000

        print(f"\n{'方法':<20} {'平均耗时':<15} {'加速比'}")
        print("-"*70)
        print(f"{'PhonemeCorrector':<20} {pc_time:>10.2f}ms      1.0x")
        print(f"{'FastRAG':<20} {fast_time:>10.2f}ms      {pc_time/fast_time:.1f}x")
        print("="*70)

    else:
        print(f"  警告: 未找到 stocks.txt 文件 ({stocks_path})")
