"""
LLM 热词检索 (RAG)

基于音素的热词检索和提示生成
"""

from pathlib import Path
from typing import List, Tuple
from threading import Lock

from .llm_hotword_rag import LLMHotwordRAG


class HotwordsRAG:
    """热词检索器"""

    def __init__(self, hotwords_file: str = 'hot-llm.txt'):
        self.rag = LLMHotwordRAG(hotwords_file, verbose=False)
        self._lock = Lock()

    def load_hotwords(self):
        """加载热词列表"""
        with self._lock:
            self.rag.load_hotwords()

    def search(self, text: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        从热词中搜索相关词汇

        Returns:
            [(hotword, score), ...] 按分数降序排列
        """
        with self._lock:
            return self.rag.search(text, top_k=top_k, threshold=0.4)

    def format_prompt(self, text: str) -> str:
        """
        生成热词提示

        Returns:
            格式化的提示字符串，如果没有相关热词则返回空字符串
        """
        hotwords = self.search(text, top_k=5)

        # DEBUG: 打印匹配到的热词详情
        print(f"\n[LLM 热词匹配] 输入文本: {text}")
        if hotwords:
            print(f"[LLM 热词匹配] 匹配到 {len(hotwords)} 个热词:")
            for i, (hotword, score) in enumerate(hotwords, 1):
                print(f"  {i}. {hotword} (得分: {score:.3f})")
        else:
            print("[LLM 热词匹配] 未匹配到热词")

        prompt = self.rag.format_hotwords_prompt(hotwords)

        # DEBUG: 打印生成的 prompt
        print(f"[LLM 热词匹配] 生成的 Prompt:\n{prompt if prompt else '(空)'}\n")

        return prompt
