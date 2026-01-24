# coding: utf-8
"""
精确 RAG 检索模块 (Accurate RAG)

基于模糊音权重的精确热词检索，支持前后鼻音、平翘舌、鼻边音等相似音素匹配。
适用于两阶段检索的第二阶段（精确计算）。

特点：
1. 使用 get_phoneme_cost 支持模糊音权重 (相似音素代价 0.5)
2. 使用 find_best_match 返回精确分数和位置信息
3. 适合作为 FastRAG 粗筛后的精确计算
"""

from typing import List, Tuple, Dict
from . import logger


from .algo_calc import find_best_match
from .algo_phoneme import get_phoneme_info, Phoneme



class AccuRAG:
    """
    精确 RAG 检索器 (含模糊音权重)

    使用场景：
    1. 作为两阶段检索的第二阶段
    2. 小规模热词 (< 1000) 直接使用
    3. 需要高精度匹配的场景
    """

    def __init__(self, threshold: float = 0.6):
        """
        初始化精确检索器

        Args:
            threshold: 相似度阈值 (0-1)，越高越严格
        """
        self.threshold = threshold
        self.hotwords: Dict[str, List[Phoneme]] = {}  # {hotword: phoneme_seq}

    def update_hotwords(self, hotwords: Dict[str, List[Phoneme]]) -> int:
        """
        更新热词列表

        Args:
            hotwords: {热词原文: 音素序列}

        Returns:
            加载的热词数量
        """
        self.hotwords = hotwords
        logger.debug(f"AccuRAG 已更新 {len(hotwords)} 个热词")
        return len(hotwords)

    def search(self, input_phonemes: List[Phoneme],
               candidate_hws: List[str] = None,
               top_k: int = 10,
               apply_threshold: bool = True) -> List[Tuple[str, float, int, int]]:
        """
        精确检索相关热词

        Args:
            input_phonemes: 输入音素序列（带语言属性）
            candidate_hws: 候选热词列表（如果提供，只在这些候选中检索）
            top_k: 返回前 K 个结果
            apply_threshold: 是否应用阈值过滤（True=只返回超过阈值的，False=返回所有候选）

        Returns:
            [(热词, 分数, start_idx, end_idx), ...]
            按分数降序排列
        """
        if not input_phonemes or not self.hotwords:
            return []

        # 确定检索范围
        search_targets = candidate_hws if candidate_hws else self.hotwords.keys()

        matches = []
        for hw in search_targets:
            if hw not in self.hotwords:
                continue

            hw_phonemes = self.hotwords[hw]

            # 长度预过滤
            if len(hw_phonemes) > len(input_phonemes) + 3:
                continue

            # 使用 find_best_match 进行精确计算（含模糊音权重）
            score, start_idx, end_idx = find_best_match(input_phonemes, hw_phonemes)

            # 根据参数决定是否应用阈值
            if not apply_threshold or score >= self.threshold:
                matches.append((hw, score, start_idx, end_idx))

        # 按分数降序排序
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:top_k]

    def search_from_text(self, text: str,
                        candidate_hws: List[str] = None,
                        top_k: int = 10) -> List[Tuple[str, float, int, int]]:
        """
        从文本直接检索（自动提取音素）

        Args:
            text: 输入文本
            candidate_hws: 候选热词列表
            top_k: 返回前 K 个结果

        Returns:
            [(热词, 分数, start_idx, end_idx), ...]
        """
        input_phonemes, _ = get_phoneme_info(text)
        if not input_phonemes:
            return []

        return self.search(input_phonemes, candidate_hws, top_k)


if __name__ == "__main__":
    import sys
    import io

    # Setup UTF-8 output for Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    import logging
    logging.basicConfig(level=logging.DEBUG)

    print("\n--- AccuRAG 测试 ---")

    # 构建测试热词
    from .algo_phoneme import get_phoneme_seq

    test_hotwords = {
        "撒贝宁": get_phoneme_seq("撒贝宁"),
        "康辉": get_phoneme_seq("康辉"),
        "东方财富": get_phoneme_seq("东方财富"),
        "科大讯飞": get_phoneme_seq("科大讯飞"),
        "乐清": get_phoneme_seq("乐清"),
    }

    rag = AccuRAG(threshold=0.6)
    rag.update_hotwords(test_hotwords)

    print("\n=== 精确检索测试 ===")
    test_cases = [
        "撒贝你主持节目",      # 撒贝宁 (前后鼻音相似)
        "康灰是央视主持人",    # 康辉 (h/ui 不完全匹配)
        "东方菜富股票",        # 东方财富 (c/ch 相似)
        "科大迅飞语音",        # 科大讯飞 (x/x 完全匹配)
        "在月清这个地方",       # 乐清 ( Yue/Qing -> 月清)
    ]

    for text in test_cases:
        results = rag.search_from_text(text)
        print(f"  '{text}'")
        if results:
            for hw, score, start, end in results[:3]:
                print(f"    -> {hw} (分数: {score:.2f}, 位置: {start}-{end})")
        else:
            print("    -> 无匹配")

    print("\n=== 两阶段检索演示 ===")
    # 模拟 FastRAG 粗筛结果
    input_text = "康灰是央视主持人"
    input_phonemes, _ = get_phoneme_info(input_text)

    # 假设 FastRAG 粗筛返回这些候选
    candidates = ["康辉", "撒贝宁", "科大讯飞", "东方财富"]

    print(f"输入: {input_text}")
    print(f"FastRAG 粗筛候选: {candidates}")

    # 第二阶段：精确计算
    results = rag.search(input_phonemes, candidate_hws=candidates)
    print(f"AccuRAG 精确结果: {results}")
