from threading import Lock
from typing import List, Tuple
from util.hotword.rag_llm_hot import LLMHotwordRAG
from util.logger import get_logger

logger = get_logger('client')

class HotwordsRAG:
    """热词检索器 - LLMHotwordRAG 的高层封装"""

    def __init__(self, hotwords_file: str = 'hot-llm.txt'):
        from util.llm.llm_constants import RAGConstants
        self._rag = LLMHotwordRAG(hotwords_file, verbose=False)
        self._constants = RAGConstants
        self._lock = Lock()

    def load_hotwords(self):
        """加载热词列表"""
        with self._lock:
            self._rag.load_hotwords()

    def search(self, text: str, top_k: int = None) -> List[Tuple[str, float]]:
        """
        从热词中搜索相关词汇

        Args:
            text: 输入文本
            top_k: 返回前 k 个热词，默认使用配置值

        Returns:
            [(hotword, score), ...] 按分数降序排列
        """
        if top_k is None:
            top_k = self._constants.DEFAULT_TOP_K

        with self._lock:
            return self._rag.search(text, top_k=top_k, threshold=self._constants.DEFAULT_THRESHOLD)

    def format_prompt(self, text: str) -> str:
        """
        生成热词提示

        Args:
            text: 输入文本

        Returns:
            格式化的提示字符串，如果没有相关热词则返回空字符串
        """
        hotwords = self.search(text)

        logger.debug(f"热词匹配 - 输入: '{text}'")
        if hotwords:
            logger.debug(f"热词匹配 - 命中 {len(hotwords)} 个: {[hw for hw, _ in hotwords]}")

        prompt = self._rag.format_hotwords_prompt(hotwords)
        return prompt
