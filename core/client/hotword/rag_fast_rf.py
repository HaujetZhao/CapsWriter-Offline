# coding: utf-8
"""
RapidFuzz 加速版 FastRAG

与 rag_fast.py 接口一致（FastRAG 类），用 rapidfuzz C++ 后端替换纯 Python DP，
用 partial_ratio_alignment 定位 + OSA 打分，在 10000 热词 × 300 音素场景下从 ~2800ms 降至 ~240ms。

行为对比：
  - search() 返回格式相同: List[Tuple[str, float, int]] = (热词, 分数, end_pos)
  - end_pos 来自 partial_ratio_alignment 的精确对齐位置
"""
from typing import List, Dict, Tuple
from collections import defaultdict
import time
from . import logger

from .algo_phoneme import Phoneme
from .rag_fast import PhonemeIndex, HAS_NUMBA
import rapidfuzz.fuzz as _fuzz
import rapidfuzz.distance.OSA as _OSA


class FastRAG:
    """
    RapidFuzz 加速版 RAG 检索器

    接口与 rag_fast.FastRAG 完全一致，可替换使用。
    只改 _score_candidates → rapidfuzz C++ 实现。
    """

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold
        self.index = PhonemeIndex()
        self.hotword_count = 0

    def add_hotwords(self, hotwords: Dict[str, List[List[Phoneme]]]):
        """批量添加热词"""
        for hw, phoneme_lists in hotwords.items():
            for phonemes in phoneme_lists:
                if phonemes:
                    self.index.add(hw, phonemes)
                    self.hotword_count += 1

    def search(self, input_phonemes: List[Phoneme], top_k: int = 0) -> List[Tuple[str, float, int]]:
        """检索相关热词（top_k <= 0 时不限制，返回全部）"""
        if not input_phonemes:
            return []

        t0 = time.perf_counter()
        input_codes = self.index.encode_input(input_phonemes)
        candidates = self.index.get_candidates(input_codes)
        t1 = time.perf_counter()
        logger.debug(f"FastRAG_rf.get_candidates: {(t1-t0)*1000:.0f}ms, {len(candidates)} 候选")

        results = self._score_candidates(input_codes, candidates)
        t2 = time.perf_counter()
        logger.debug(f"FastRAG_rf._score_candidates: {(t2-t1)*1000:.0f}ms, {len(results)} 命中")

        results.sort(key=lambda x: x[1], reverse=True)
        logger.debug(f"FastRAG_rf.search 总计: {(time.perf_counter()-t2)*1000:.0f}ms")
        return results if top_k <= 0 else results[:top_k]

    def _score_candidates(
        self, input_list: List[int],
        candidates: List[Tuple[str, List[int], List[int]]]
    ) -> List[Tuple[str, float, int]]:
        """
        partial_ratio_alignment 定位 + OSA 打分

        两步都在 C++ 中完成（无 Python 内层循环）：
          1. partial_ratio_alignment 在窗口中找到最佳对齐位置（Indel 粗筛）
          2. OSA 精确计算对齐片段的编辑距离（含交换操作）
        """
        results = []
        input_len = len(input_list)
        pr_cutoff = self.threshold * 100

        for hw, hw_list, anchors in candidates:
            hw_len = len(hw_list)
            osa_cutoff = int(hw_len * (1 - self.threshold))

            # 锚点去重：相近的合并
            if len(anchors) > 1:
                deduped = [anchors[0]]
                for a in anchors[1:]:
                    if a - deduped[-1] > 2:
                        deduped.append(a)
                anchors = deduped

            for anchor in anchors:
                scan_start = max(0, anchor - 2)
                scan_end = min(input_len, anchor + hw_len + 3)
                local_input = input_list[scan_start:scan_end]
                local_len = len(local_input)

                if local_len < hw_len:
                    continue

                # Step 1: C++ 内部滑动窗口找到最佳对齐位置
                #          partial_ratio_alignment 用 Indel 粗筛
                alignment = _fuzz.partial_ratio_alignment(
                    local_input, hw_list, score_cutoff=pr_cutoff
                )
                if alignment is None:
                    continue

                # Step 2: 提取对齐片段，用 OSA 精确打分（含交换操作）
                aligned = local_input[alignment.src_start:alignment.src_end]
                dist = _OSA.distance(
                    aligned, hw_list, score_cutoff=osa_cutoff
                )
                if dist > osa_cutoff:
                    continue

                score = 1.0 - (dist / hw_len)
                # 精确结束位置（来自 partial_ratio_alignment 的 src_start）
                end_pos = scan_start + alignment.src_start + hw_len
                results.append((hw, round(score, 3), end_pos))

        # 对 (hw, end_pos) 去重，保留最高分
        final = {}
        for hw, score, end_pos in results:
            key = (hw, end_pos)
            if key not in final or score > final[key][0]:
                final[key] = (score, end_pos)

        return [(hw, score, end_pos) for (hw, _), (score, end_pos) in final.items()]


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    import random
    from .algo_phoneme import get_phoneme_seq
    import logging

    logging.basicConfig(level=logging.INFO)

    print(f"\n=== RapidFuzz 加速 RAG 测试 ===")
    print(f"Numba 可用: {HAS_NUMBA}")

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
    print(f"  候选数量: {len(rag.index.get_candidates(rag.index.encode_input(input_phonemes)))}")
    print(f"  结果: {results[:5]}")
