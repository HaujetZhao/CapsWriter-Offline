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

            # 阶段2: 轻量级定位与替换 (替代原先重型的 AccuRAG)
            # 策略：直接在输入音素流中寻找候选热词的音素子序列
            
            # 1. 预计算候选热词的音素
            candidate_phonemes_map = {}
            for hw, score in fast_results:
                if score >= self.threshold: # 只处理分数够高的
                    # 这里为了快，直接从 self.fast_rag.index 里取（需要 FastRAG 暴露接口或者自己存一份）
                    # 简单起见，这里重新获取一次音素（会有一点点开销，但比 AccuRAG 小得多）
                    phons, _ = get_phoneme_info(hw)
                    candidate_phonemes_map[hw] = (phons, score)

            # 2. 在原文本音素中匹配
            # 改进：支持模糊定位 (Fuzzy Positioning)
            input_len = len(input_phonemes)
            
            # 预处理：去除输入音素的声调，用于快速模糊匹配
            input_phons_no_tone = []
            for p in input_phonemes:
                val = p.value
                # 如果是纯声调(1-5)，直接忽略
                if val.isdigit():
                    continue
                # 如果是带声调的拼音(hao3)，去除声调
                if val and val[-1].isdigit():
                     input_phons_no_tone.append(val[:-1])
                else:
                     input_phons_no_tone.append(val)
            
            for hw, (hw_phons, score) in candidate_phonemes_map.items():
                hw_len = len(hw_phons)
                # hw_phons 也包含声调 Phoneme，所以去声调后的长度会变短
                # 我们先去声调再比较长度
                
                hw_phons_no_tone = []
                for p in hw_phons:
                    val = p.value
                    if val.isdigit():
                        continue
                    if val and val[-1].isdigit():
                        hw_phons_no_tone.append(val[:-1])
                    else:
                        hw_phons_no_tone.append(val)
                
                
                # 重新计算长度
                curr_hw_len = len(hw_phons_no_tone)
                curr_input_len = len(input_phons_no_tone)
                
                if curr_hw_len > curr_input_len:
                    continue

                # 滑窗匹配 (使用去声调后的列表)
                for i in range(curr_input_len - curr_hw_len + 1):
                    # 快速检查首尾（无声调）
                    if input_phons_no_tone[i] != hw_phons_no_tone[0]: continue
                    
                    # 检查片段
                    sub_segment = input_phons_no_tone[i : i+curr_hw_len]
                    
                    # 1. 无声调完全匹配
                    if sub_segment == hw_phons_no_tone:
                        # 找到位置了！
                        # 难点：input_phons_no_tone 的索引 i 对应原来 char_indices 的哪里？
                        # 因为我们跳过了声调，所以索引不再一一对应。
                        
                        # 这种简化方案导致了索引映射丢失！
                        # 我们必须保留原始列表的结构，或者建立映射。
                        
                        # 方案B：不去掉声调 Phoneme，而是把它的 value 置为空，或者在比较时跳过。
                        # 但为了代码简单，我们重新做一个带索引的列表
                        pass

            # === 修正方案：保留索引映射 ===
            # 构建一个 list of (phoneme_val_no_tone, lang, original_index)
            input_processed = []
            for idx, p in enumerate(input_phonemes):
                val = p.value
                if val.isdigit(): continue # 跳过声调
                
                clean_val = val[:-1] if (val and val[-1].isdigit()) else val
                input_processed.append((clean_val, p.lang, idx))
            
            # 对热词也做同样处理
            
            for hw, (hw_phons, score) in candidate_phonemes_map.items():
                hw_mid = []
                for p in hw_phons:
                    val = p.value
                    if val.isdigit(): continue
                    clean_val = val[:-1] if (val and val[-1].isdigit()) else val
                    hw_mid.append((clean_val, p.lang))
                
                if not hw_mid: continue
                
                target_len = len(hw_mid)
                input_len_p = len(input_processed)
                
                if target_len > input_len_p: continue
                
                for i in range(input_len_p - target_len + 1):
                     # 首尾检查 (值和语言都要匹配)
                     input_start = input_processed[i]
                     hw_start = hw_mid[0]
                     
                     if input_start[0] != hw_start[0]: continue # 值不等
                     if input_start[1] != hw_start[1]: continue # 语言不等
                     
                     # 提取片段
                     sub_seg = input_processed[i : i+target_len]
                     
                     matched = False
                     
                     # 1. 完全匹配 (检查值和语言)
                     # 快速比较整个列表的(val, lang)
                     sub_mid = [(x[0], x[1]) for x in sub_seg]
                     if sub_mid == hw_mid:
                         matched = True
                     
                     # 2. 模糊匹配
                     elif score >= self.similar_threshold: # 高分才允许误差
                         diff = 0
                         for k in range(target_len):
                             # 只有当 语言一致 且 值不一致 时，才算 1 个差异
                             # 如果语言都不同，直接视为严重错误，禁止匹配 (或者算大分值)
                             # 这里为严格起见，语言不同直接判死刑
                             if sub_seg[k][1] != hw_mid[k][1]:
                                 diff = 999
                                 break
                                 
                             if sub_seg[k][0] != hw_mid[k][0]:
                                 diff += 1
                                 if diff > 2: break
                                 
                         if diff <= 2 and diff <= target_len * 0.3:
                             matched = True
                     
                     if matched:
                         # 边界检查：热词匹配必须在词的边界上
                         orig_start_phon_idx = input_processed[i][2]
                         orig_end_phon_idx = input_processed[i + target_len - 1][2]
                         
                         start_p = input_phonemes[orig_start_phon_idx]
                         end_p = input_phonemes[orig_end_phon_idx]
                         
                         # 严格边界检查：
                         if not start_p.is_word_start:
                             matched = False
                         elif not end_p.is_word_end:
                              # 特殊情况：对于中文，字尾可能是声调音素
                              # 如果当前音素不是结尾，但下一个音素是声调且是结尾，则也算通过
                              next_idx = orig_end_phon_idx + 1
                              if next_idx < len(input_phonemes):
                                  next_p = input_phonemes[next_idx]
                                  if next_p.lang == 'zh' and next_p.value.isdigit() and next_p.is_word_end:
                                      pass # 通过
                                  else:
                                      matched = False
                              else:
                                  matched = False
                     
                     if matched:
                         # 映射回原始字符索引
                         orig_start_phon_idx = input_processed[i][2]
                         orig_end_phon_idx = input_processed[i + target_len - 1][2]
                         
                         # 拿到字符索引
                         char_start = char_indices[orig_start_phon_idx][0]
                         # 结束字符索引是最后一个音素对应的结束索引
                         char_end = char_indices[orig_end_phon_idx][1]
                         
                         match = MatchResult(char_start, char_end, score, hw)
                         matches.append(match)
                         all_matches.append(match)
                         


        # 3. 解决重叠匹配
        # 策略：分数优先，其次长度优先
        # 去重：同一个位置可能匹配了多次，保留分数最高的
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

        if not final_matches:
            return CorrectionResult(text=text, matched_hotwords=[(m.hotword, m.score) for m in all_matches])

        # 4. 执行替换 (从后往前，避免索引偏移)
        # 按开始位置倒序
        final_matches.sort(key=lambda x: x.start, reverse=True)
        
        corrected_text = list(text)
        for m in final_matches:
            corrected_text[m.start : m.end] = list(m.hotword)
            
        return CorrectionResult(text="".join(corrected_text), matched_hotwords=[(m.hotword, m.score) for m in final_matches])

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
