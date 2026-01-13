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
from .rag_fast import FastRAG
from .algo_calc import fast_substring_score, fuzzy_substring_score

logger = logging.getLogger(__name__)


class MatchResult(NamedTuple):
    start: int
    end: int
    score: float
    hotword: str


class CorrectionResult(NamedTuple):
    """纠错结果，包含纠错后的文本和匹配的热词列表"""
    text: str                           # 纠错后的文本
    matchs: List[Tuple[str, float]]  # [(热词, 分数), ...]
    similars: List[Tuple[str, float]]  # [(热词, 分数), ...]
    


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

    def _find_matches(self, fast_results: List, input_processed: List[Tuple]) -> List[MatchResult]:
        """精细匹配逻辑：滑动窗口、模糊打分、边界检查"""
        matches = []
        similars = []
        input_len = len(input_processed)

        for hw, score in fast_results:
            # if score < self.threshold: continue
            
            # 获取热词的对比序列 (保持 info 七元组中的前五项：值, 语言, 字始, 字终, 声调)
            hw_phonemes = self.hotwords[hw]
            hw_compare = [p.info[:5] for p in hw_phonemes]
            target_len = len(hw_compare)
            if target_len > input_len: continue

            # 滑动窗口查找
            for i in range(input_len - target_len + 1):
                sub_seg = input_processed[i : i + target_len]
                
                # 策略：要求首音协议（非英文强卡首音）
                if sub_seg[0][1] != 'en' and sub_seg[0][0] != hw_compare[0][0]:
                    continue
                
                # 1. 边界粗筛选
                if not sub_seg[0][2]: continue  # 第一个音素必须是词起始
                
                # 最后一个音素检测
                last_match_idx = i + target_len - 1
                is_end_ok = False
                if sub_seg[-1][3]: 
                    is_end_ok = True
                else:
                    # 容错：如果是中文，允许热词比实际发音序列更短（如果后面跟着声调）
                    next_idx = last_match_idx + 1
                    if next_idx < input_len:
                        next_info = input_processed[next_idx]
                        if next_info[1] == 'zh' and next_info[4] and next_info[3]:
                            is_end_ok = True
                            
                if not is_end_ok: continue

                # 2. 精细相似度计算
                current_score = fuzzy_substring_score(hw_compare, sub_seg)

                # 记录匹配：从 info 七元组 [5], [6] 直接拿位置
                char_start = sub_seg[0][5]
                char_end = sub_seg[-1][6]
                similars.append(MatchResult(char_start, char_end, current_score, hw))
                if current_score >= self.threshold:
                    matches.append(MatchResult(char_start, char_end, current_score, hw))

        # 潜在热词按得分降序排序、过滤、去重
        seen = set()
        similars.sort(key=lambda x: x.score, reverse=True)
        similars = [p for p in similars if p.score >= self.similar_threshold]
        similars = [m for m in similars if not (m.hotword in seen or seen.add(m.hotword))]
        return matches, similars

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
            
        return "".join(result_list), [(m.hotword, m.score) for m in final_matches], all_matched_info

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

        # 2. 检索与匹配
        with self._lock:
            # 粗筛
            fast_results = self.fast_rag.search(input_phonemes, top_k=100)
            # 预处理输入 (转换为全能七元组：值, 语言, 字始, 字终, 是调, 始位, 终位)
            input_processed = [p.info for p in input_phonemes]
            # 精筛
            matches, similars = self._find_matches(fast_results, input_processed)

        # 3. 冲突解决与替换
        new_text, final_hw_info, all_hw_info = self._resolve_and_replace(text, matches)
        similars = [(m.hotword, m.score) for m in similars[:k]]

        return CorrectionResult(text=new_text, matchs=final_hw_info, similars=similars)


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
        if result.matchs:
            print(f"    匹配热词: {result.matchs}")
    
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
            if result.matchs:
                # 只显示前3个匹配的热词，避免输出过长
                displayed = result.matchs[:3]
                if len(result.matchs) > 3:
                    displayed.append(f"...(共{len(result.matchs)}个)")
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
            pc_top = result_pc.matchs[0] if result_pc.matchs else None

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
