# coding: utf-8
"""
LLM 纠错历史 RAG

检索用户自定义的纠错历史 (错句 => 正句)，作为 LLM 的背景知识。
"""

import threading
import time
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import logging

# Updated imports
from .algo_phoneme import get_phoneme_info
from .algo_calc import find_best_match

logger = logging.getLogger(__name__)

# 纠错历史文件路径
RECTIFY_FILE = Path('hot-llm-rectify.txt')


class LLMRectifyRAG:
    """
    LLM 纠错历史检索器
    
    加载 'hot-llm-rectify.txt'，通过 RAG 检索相似的“错句”，
    返回对应的“正句”作为 Prompt 上下文。
    """
    
    def __init__(self, rectfy_file: str = 'hot-llm-rectify.txt', threshold: float = 0.6):
        """
        初始化
        
        Args:
            rectfy_file: 纠错历史文件路径
            threshold: 相似度阈值
        """
        self.rectfy_file = Path(rectfy_file)
        self.threshold = threshold
        self.history: Dict[str, str] = {}   # {wrong_text: right_text}
        self.phoneme_index: Dict[str, List[str]] = {} # {wrong_text: phoneme_seq}
        self._lock = threading.Lock()
        
        self.load_history()
        
    def load_history(self):
        """加载纠错历史"""
        if not self.rectfy_file.exists():
            with open(self.rectfy_file, 'w', encoding='utf-8') as f:
                f.write('# 在此文件放置纠错历史，格式：错句 => 正句\n# 例如：\n# 原锯子 => 原句子\n')
            return

        try:
            with open(self.rectfy_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            new_history = {}
            new_index = {}
            
            start_time = time.time()
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                parts = line.split('=>')
                if len(parts) != 2:
                    parts = line.split('->') # 兼容 ->
                    if len(parts) != 2:
                        continue
                        
                wrong = parts[0].strip()
                right = parts[1].strip()
                
                if wrong and right:
                    new_history[wrong] = right
                    # 预计算音素
                    phonemes, _ = get_phoneme_info(wrong)
                    if phonemes:
                        new_index[wrong] = phonemes
            
            with self._lock:
                self.history = new_history
                self.phoneme_index = new_index
                
            count = len(new_history)
            if count > 0:
                logger.debug(f"已加载 {count} 条纠错历史，耗时 {time.time() - start_time:.3f}s")
                logger.info(f"已载入 {count} 条 LLM 纠错历史")
                
        except Exception as e:
            logger.error(f"加载纠错历史失败: {e}")

    def search(self, text: str, top_k: int = 5) -> List[Tuple[str, str, float]]:
        """
        检索相关的纠错历史
        
        Args:
            text: 输入文本
            top_k: 最大结果数
            
        Returns:
            [(wrong, right, score), ...]
        """
        if not text or not self.history:
            return []
            
        input_phonemes, _ = get_phoneme_info(text)
        if not input_phonemes:
            return []
            
        matches = []
        
        with self._lock:
            # 复制引用
            current_index = self.phoneme_index.items()
            
        for wrong, wrong_phonemes in current_index:
            # 优化：长度过滤
            if len(wrong_phonemes) > len(input_phonemes) + 5: # 允许历史片段比输入稍长一点点? 不，通常输入是一大段话
                 pass 
            
            # 这里是反过来的：我们在长文本(input)中找短文本(history key)
            # find_best_match(main_seq=input, sub_seq=history_key)
            
            score, _, _ = find_best_match(input_phonemes, wrong_phonemes)
            
            if score >= self.threshold:
                right = self.history[wrong]
                matches.append((wrong, right, score))
                
        # 排序
        matches.sort(key=lambda x: x[2], reverse=True)
        
        return matches[:top_k]

    def format_prompt(self, text: str) -> str:
        """
        生成提示词
        
        Args:
            text: 输入文本
            
        Returns:
            包含纠错历史的提示词段落 (Markdown)，无匹配则返回空字符串
        """
        results = self.search(text)
        if not results:
            return ""
            
        lines = ["纠错历史（参考）："]
        for wrong, right, score in results:
            lines.append(f"- {wrong} => {right}")
            
        return "\n".join(lines)


if __name__ == "__main__":
    # from util.logger import setup_logger
    # setup_logger('client')
    logging.basicConfig(level=logging.DEBUG)
    
    print("\n--- LLMRectifyRAG 测试 ---")
    
    # 创建临时文件
    test_file = Path("test_rectify.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("原锯子 => 原句子\n甚么鬼 => 什么鬼\n")
        
    try:
        rag = LLMRectifyRAG(str(test_file))
        
        print("\nSearching '这个原锯子写错了':")
        res = rag.search("这个原锯子写错了")
        print(res)
        
        print("\nPrompt:")
        print(rag.format_prompt("这个原锯子写错了"))
        
    finally:
        if test_file.exists():
            test_file.unlink()

