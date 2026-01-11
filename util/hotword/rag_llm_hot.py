# coding: utf-8
"""
LLM 热词 RAG 检索

基于音素的热词检索，参考 FunASR 的 phoneme_tokenizer 实现
"""

from pathlib import Path
from typing import List, Tuple, Optional
from threading import Lock
import logging

# Updated imports
from .algo_phoneme import get_phoneme_seq
from .algo_calc import fuzzy_substring_distance

logger = logging.getLogger(__name__)


class LLMHotwordRAG:
    """LLM 热词检索器"""

    def __init__(self, hotwords_file: str = 'hot_llm.txt', verbose: bool = False):
        """
        初始化热词检索器

        Args:
            hotwords_file: 热词文件路径
            verbose: 是否打印初始化信息
        """
        self.hotwords_file = Path(hotwords_file)
        self.verbose = verbose
        self.hotwords = []
        self.hotword_phonemes = {}

        self.load_hotwords()

    def load_hotwords(self):
        """加载热词列表"""
        if not self.hotwords_file.exists():
            logger.debug(f"热词文件不存在: {self.hotwords_file}")
            return

        try:
            with open(self.hotwords_file, 'r', encoding='utf-8') as f:
                # 读取非空行、非注释行
                lines = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.strip().startswith('#')
                ]

            self.hotwords = lines
            logger.debug(f"已加载 {len(self.hotwords)} 个热词")

            # 预计算音素序列
            if self.hotwords:
                import time
                start = time.time()

                self.hotword_phonemes = {}
                for hw in self.hotwords:
                    if hw:
                        self.hotword_phonemes[hw] = get_phoneme_seq(hw)

                logger.debug(f"预计算音素完成，耗时 {time.time() - start:.2f} 秒")

        except Exception as e:
            logger.error(f"热词加载失败: {e}")

    def search(self, text: str, top_k: int = 10, threshold: float = 0.4) -> List[Tuple[str, float]]:
        """
        检索相关热词

        Args:
            text: 输入文本
            top_k: 返回前 K 个结果
            threshold: 相似度阈值 (0-1)

        Returns:
            [(hotword, score), ...] 按分数降序排列
        """
        if not self.hotwords:
            logger.debug("热词列表为空")
            return []

        text_seq = get_phoneme_seq(text)
        if not text_seq:
            logger.debug("文本音素序列为空")
            return []

        logger.debug(f"热词检索: 输入='{text}', 音素={text_seq}, 热词数={len(self.hotwords)}")

        scored_hotwords = []

        for hw, hw_seq in self.hotword_phonemes.items():
            if not hw_seq:
                continue

            # 计算编辑距离
            min_dist = fuzzy_substring_distance(text_seq, hw_seq)
            denom = len(hw_seq) if len(hw_seq) > 0 else 1
            score = 1.0 - (min_dist / denom)

            if score >= threshold:
                scored_hotwords.append((hw, round(score, 3)))

        # 按分数降序排序
        scored_hotwords.sort(key=lambda x: x[1], reverse=True)
        result = scored_hotwords[:top_k]

        if result:
            logger.debug(f"热词匹配结果: {[(hw, f'{s:.3f}') for hw, s in result]}")
        else:
            logger.debug(f"未匹配到热词（阈值={threshold}）")

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
    # Setup logging to console
    logging.basicConfig(level=logging.DEBUG)
    
    print("\n--- LLMHotwordRAG 测试 ---")
    
    # 创建临时热词文件
    test_file = Path("test_hot_llm.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("# comment\nPython\nJava\nC++\nCapsWriter\n")
        
    try:
        rag = LLMHotwordRAG(str(test_file))
        
        # Test search
        print("\nSearching 'Pythn':")
        res = rag.search("Pythn")
        print(res)
        
        print("\nSearching 'CapsRiter':")
        res = rag.search("CapsRiter")
        print(res)
        
        # Test format
        print("\nPrompt:")
        print(rag.format_hotwords_prompt(res))
        
    finally:
        if test_file.exists():
            test_file.unlink()


