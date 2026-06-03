# coding: utf-8
"""
RapidFuzz 全局批量加速版 FastRAG (掩码剥离版)

与 rag_fast.py 接口一致（FastRAG 类），利用 rapidfuzz.process.extract
在 C++ 层一次性对所有热词进行滑动匹配，彻底干掉倒排索引、锚点扫描以及 Python 层的匹配循环。
并在匹配成功的候选上使用掩码剥离机制支持多位置匹配召回。
"""
from typing import List, Dict, Tuple
import time
from . import logger

from .algo_phoneme import Phoneme
from .rag_fast import PhonemeEncoder
import rapidfuzz.fuzz as _fuzz
import rapidfuzz.distance.OSA as _OSA
import rapidfuzz.process as _process


class FastRAG:
    """
    RapidFuzz 全局批量加速版 RAG 检索器
    """

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold
        self.encoder = PhonemeEncoder()
        # {(hw, tuple_codes): codes}
        self.hotwords: Dict[Tuple[str, Tuple[int, ...]], List[int]] = {}
        self.hotword_count = 0

    def add_hotwords(self, hotwords: Dict[str, List[List[Phoneme]]]):
        """批量添加热词"""
        for hw, phoneme_lists in hotwords.items():
            for phonemes in phoneme_lists:
                if phonemes:
                    phoneme_strs = [p.value for p in phonemes]
                    codes = self.encoder.encode_sequence(phoneme_strs)
                    self.hotwords[(hw, tuple(codes))] = codes
                    self.hotword_count += 1

    def search(self, input_phonemes: List[Phoneme], top_k: int = 0) -> List[Tuple[str, float, int]]:
        """检索相关热词（top_k <= 0 时不限制，返回全部）"""
        if not input_phonemes or not self.hotwords:
            return []

        t_start = time.perf_counter()
        phoneme_strs = [p.value for p in input_phonemes]
        input_list = self.encoder.encode_sequence(phoneme_strs)
        pr_cutoff = self.threshold * 100

        t_step1_start = time.perf_counter()
        # 一次性调用 C++ 批量匹配，过滤 99.9% 绝不可能匹配的候选词
        matches = _process.extract(
            input_list,
            self.hotwords,
            scorer=_fuzz.partial_ratio,
            score_cutoff=pr_cutoff,
            limit=None
        )
        t_step1_end = time.perf_counter()
        step1_ms = (t_step1_end - t_step1_start) * 1000

        t_step2_start = time.perf_counter()
        results = []
        for match_val, score, key in matches:
            hw, hw_tuple = key
            hw_list = list(hw_tuple)
            hw_len = len(hw_list)
            osa_cutoff = int(hw_len * (1 - self.threshold))

            # 拷贝一份输入用于剥离匹配区间，支持多处匹配
            remaining_input = list(input_list)
            
            while True:
                # 寻找全局上的精确对齐
                alignment = _fuzz.partial_ratio_alignment(
                    remaining_input, hw_list, score_cutoff=pr_cutoff
                )
                if alignment is None:
                    break

                # 避免重复提取：若当前最佳对齐范围与已掩码的部分重合，则停止
                if any(remaining_input[idx] == -1 for idx in range(alignment.src_start, alignment.src_end)):
                    break

                aligned = input_list[alignment.src_start:alignment.src_end]
                dist = _OSA.distance(
                    aligned, hw_list, score_cutoff=osa_cutoff
                )
                
                if dist <= osa_cutoff:
                    score = 1.0 - (dist / hw_len)
                    end_pos = alignment.src_start + hw_len
                    results.append((hw, round(score, 3), end_pos))

                # 掩码匹配过的区间（置为 -1，不影响后续索引计算）
                for idx in range(alignment.src_start, alignment.src_end):
                    remaining_input[idx] = -1

        # 对 (hw, end_pos) 去重，保留最高分
        final = {}
        for hw, score, end_pos in results:
            key = (hw, end_pos)
            if key not in final or score > final[key][0]:
                final[key] = (score, end_pos)

        results = [(hw, score, end_pos) for (hw, _), (score, end_pos) in final.items()]
        results.sort(key=lambda x: x[1], reverse=True)
        t_step2_end = time.perf_counter()
        step2_ms = (t_step2_end - t_step2_start) * 1000
        
        # 输出每次检索各阶段的时间细节，便于协调分析
        logger.debug(
            f"FastRAG_batch.search - "
            f"第一步(extract 粗筛) 耗时: {step1_ms:.2f}ms, 候选数: {len(matches)} | "
            f"第二步(对齐+掩码) 耗时: {step2_ms:.2f}ms, 最终匹配数: {len(results)}"
        )

        return results if top_k <= 0 else results[:top_k]


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    import random
    from .algo_phoneme import get_phoneme_seq
    import logging

    logging.basicConfig(level=logging.INFO)

    print(f"\n=== RapidFuzz 全局批量加速 RAG 测试 (Batch版) ===")

    chinese_chars = '的一是不了在人有我他这个们中来上大为和国地到以说时要就出会可也你对生能而子那得于着下自之年过发后作里如等'

    print("\n生成 10000 个热词...")
    hotwords = {}
    for i in range(10000):
        length = random.randint(2, 4)
        word = ''.join(random.choice(chinese_chars) for _ in range(length))
        phonemes = get_phoneme_seq(word)
        hotwords[word] = [phonemes]

    print("构建索引...")
    start = time.time()
    rag = FastRAG(threshold=0.6)
    rag.add_hotwords(hotwords)
    print(f"  索引构建耗时: {time.time() - start:.3f}s")

    input_text = ''.join(random.choice(chinese_chars) for _ in range(100))
    input_phonemes = get_phoneme_seq(input_text)
    print(f"\n输入: {input_text[:50]}... ({len(input_text)}字, {len(input_phonemes)}音素)")

    print("\n测试检索性能...")
    start = time.time()
    results = rag.search(input_phonemes, top_k=10)
    elapsed = time.time() - start

    print(f"  检索耗时: {elapsed*1000:.1f}ms")
    print(f"  热词总数: {rag.hotword_count}")
    print(f"  结果: {results[:5]}")
