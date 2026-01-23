"""
FunASR-GGUF Prompt 构建工具
"""

from typing import List, Optional, Tuple
import numpy as np
from . import nano_llama

class PromptBuilder:
    """负责构建 LLM 的 Prompt Embeddings"""
    
    def __init__(self, vocab: any, embedding_table: np.ndarray):
        self.vocab = vocab
        self.embedding_table = embedding_table

    def build_prompt(
        self,
        hotwords: List[str] = None,
        language: Optional[str] = None,
        context: Optional[str] = None
    ) -> Tuple[np.ndarray, np.ndarray, int, int, str]:
        """
        构建 Prompt Embeddings
        
        Returns:
            (prefix_embd, suffix_embd, n_prefix, n_suffix, prefix_prompt_text)
        """
        # 构建 Prompt
        prefix_prompt = "<|im_start|>system\nYou are a helpful assistant.<|im_end|>\n<|im_start|>user\n"

        if hotwords or context:
            if context:
                prefix_prompt += f"请结合上下文信息，更加准确地完成语音转写任务。\n\n\n"
                prefix_prompt += f"**上下文信息：**{context}\n\n\n"

            if hotwords:
                hotwords_str = ", ".join(hotwords)
                prefix_prompt += f"热词列表：[{hotwords_str}]\n"

        if not language:
            prefix_prompt += "语音转写："
        else:
            prefix_prompt += f"语音转写成{language}："

        suffix_prompt = "<|im_end|>\n<|im_start|>assistant\n"

        # 转换为 embeddings
        prefix_tokens = nano_llama.text_to_tokens(self.vocab, prefix_prompt)
        suffix_tokens = nano_llama.text_to_tokens(self.vocab, suffix_prompt)

        prefix_embd = self.embedding_table[prefix_tokens].astype(np.float32)
        suffix_embd = self.embedding_table[suffix_tokens].astype(np.float32)

        return prefix_embd, suffix_embd, len(prefix_tokens), len(suffix_tokens), prefix_prompt
