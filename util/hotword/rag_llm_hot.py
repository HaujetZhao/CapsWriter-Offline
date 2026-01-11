# coding: utf-8
"""
LLM 热词 RAG 检索

基于音素的热词检索，支持中英文混合匹配：
- 中文：音素级匹配（声母+韵母+声调）
- 英文：字符级匹配

使用 FastRAG 进行高性能检索。
"""

from pathlib import Path
from typing import List, Tuple, Optional
from threading import Lock

from util.hotword.algo_phoneme import get_phoneme_seq
from util.hotword.rag_fast import FastRAG
from util.logger import get_logger

logger = get_logger('client')


class LLMHotwordRAG:
    """LLM 热词检索器"""

    def __init__(self, hotwords_file: str = 'hot_llm.txt', threshold: float = 0.6, verbose: bool = False):
        """
        初始化热词检索器
        
        Args:
            hotwords_file: 热词文件路径
            threshold: 默认相似度阈值
            verbose: 是否打印调试信息
        """
        self.hotwords_file = Path(hotwords_file)
        self.default_threshold = threshold
        self.verbose = verbose
        self.hotwords = []
        
        # 使用 FastRAG (Numba 加速的 DP 算法)
        self.rag = FastRAG(threshold=threshold)
        
        self.load_hotwords()

    def load_hotwords(self):
        """加载热词列表"""
        if not self.hotwords_file.exists():
            logger.debug(f"热词文件不存在: {self.hotwords_file}")
            return

        try:
            with open(self.hotwords_file, 'r', encoding='utf-8') as f:
                lines = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.strip().startswith('#')
                ]

            self.hotwords = lines
            logger.info(f"已加载 {len(self.hotwords)} 个热词，构建检索索引...")

            if self.hotwords:
                import time
                start = time.time()
                
                # 构建热词映射 {word: phonemes}
                hotword_map = {}
                for hw in self.hotwords:
                    phonemes = get_phoneme_seq(hw)
                    if phonemes:
                        hotword_map[hw] = phonemes
                
                # 添加到 RAG
                self.rag.add_hotwords(hotword_map)
                
                logger.info(f"索引构建完成，耗时 {time.time() - start:.3f} 秒")

        except Exception as e:
            logger.error(f"热词加载失败: {e}")

    def search(
        self, 
        text: str, 
        top_k: int = 10, 
        threshold: float = None,
        precomputed_results: List[Tuple[str, float]] = None
    ) -> List[Tuple[str, float]]:
        """
        检索相关热词
        
        Args:
            text: 输入文本
            top_k: 返回前 K 个结果
            threshold: 相似度阈值，None 则使用默认值
            precomputed_results: 预计算的检索结果（来自 corrector_phoneme）
                                 如果提供，则直接使用，不再重新检索
        
        Returns:
            [(hotword, score), ...] 按分数降序排列
        """
        # 如果有预计算结果，直接使用
        if precomputed_results is not None:
            # 过滤阈值
            th = threshold if threshold is not None else self.default_threshold
            filtered = [(hw, score) for hw, score in precomputed_results if score >= th]
            filtered.sort(key=lambda x: x[1], reverse=True)
            
            if filtered and self.verbose:
                logger.debug(f"使用预计算结果: {[(hw, f'{s:.2f}') for hw, s in filtered[:top_k]]}")
            
            return filtered[:top_k]
        
        # 否则自行检索
        if not self.hotwords:
            return []
            
        text_seq = get_phoneme_seq(text)
        if not text_seq:
            return []

        th = threshold if threshold is not None else self.default_threshold
        result = self.rag.search(text_seq, top_k=top_k)
        
        # 过滤阈值
        result = [(hw, score) for hw, score in result if score >= th]

        if result and self.verbose:
            logger.debug(f"热词匹配: {text} -> {[(hw, f'{s:.2f}') for hw, s in result]}")

        return result

    def format_hotwords_prompt(self, hotwords: List[Tuple[str, float]]) -> str:
        """
        将检索结果格式化为 prompt

        Args:
            hotwords: [(hotword, score), ...]

        Returns:
            格式化的提示字符串
        """
        if not hotwords:
            return ""

        # 提取热词（只保留词，不保留分数）
        hotword_list = [hw for hw, _ in hotwords]
        return f"热词列表：[{', '.join(hotword_list)}]"



if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    print("\n--- LLMHotwordRAG 测试 ---")
    
    # 创建临时热词文件
    test_file = Path("test_hot_llm.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("""# 英文热词
Python
CapsWriter
Microsoft
Claude
iPhone
7-Zip

# 中文热词
撒贝宁
康辉
东方财富
科大讯飞
""")
        
    try:
        rag = LLMHotwordRAG(str(test_file), threshold=0.5)
        
        print("\n=== 英文测试 ===")
        test_cases_en = [
            "I use pythn for coding",
            "you can use caps riter to type",
            "download micro soft office",
            "let cloud do these things",
            "compress with 7 zip",
        ]
        for text in test_cases_en:
            res = rag.search(text)
            print(f"  '{text}'")
            print(f"    -> {res}")
        
        print("\n=== 中文测试 ===")
        test_cases_zh = [
            "撒贝你主持春晚",
            "康灰是央视主持人",
            "东方菜富股票涨了",
            "科大迅飞做语音识别",
        ]
        for text in test_cases_zh:
            res = rag.search(text)
            print(f"  '{text}'")
            print(f"    -> {res}")
        
        print("\n=== 完整 Prompt 示例 ===")
        result = rag.search("我用caps riter写科大迅飞的pythn代码")
        print(rag.format_hotwords_prompt(result))
        
    finally:
        if test_file.exists():
            test_file.unlink()
