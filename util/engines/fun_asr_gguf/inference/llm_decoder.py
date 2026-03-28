import time
import re
import ctypes
import numpy as np
from typing import Optional

from . import llama
from .schema import LLMDecodeResult
from .display import DisplayReporter

class LLMDecoder:
    """组件：负责 LLM 推理循环与熔断机制"""
    def __init__(self, models):
        self.models = models
        self.stop_tokens = [151643, 151645]

    def decode(
        self,
        full_embd: np.ndarray,
        n_input_tokens: int,
        n_predict: int,
        stream_output: bool = False,
        reporter: Optional[DisplayReporter] = None,
        temperature: float = 0.3,
        top_p: float = 1.0,
        top_k: int = 50
    ) -> LLMDecodeResult:
        res = LLMDecodeResult()
        t_inject_start = time.perf_counter()
        
        # 1. Inject (Context & Embeddings)
        self.models.ctx.clear_kv_cache()
        batch_embd = llama.LlamaBatch(n_input_tokens, full_embd.shape[1], 1)
        batch_embd.set_embd(full_embd)
        batch_embd.struct.token = ctypes.cast(None, ctypes.POINTER(llama.llama_token))
        
        if self.models.ctx.decode(batch_embd) != 0: 
            raise RuntimeError("Decode failed")
            
        res.t_inject = time.perf_counter() - t_inject_start

        # 2. Generation Loop
        t_gen_start = time.perf_counter()
        asr_decoder = llama.ASRStreamDecoder(self.models.vocab, reporter if stream_output else None)
        seed = int(np.random.randint(0, 2**31 - 1))
        
        with llama.LlamaSampler(temperature=temperature, top_k=top_k, top_p=top_p, seed=seed) as smpl:
            for _ in range(n_predict):
                token_id = smpl.sample(self.models.ctx, -1)
                
                if self.models.ctx.decode_token(token_id) != 0: 
                    break
                    
                if token_id == self.models.eos_token or token_id in self.stop_tokens: 
                    break
                
                asr_decoder.push(token_id)
                
                # 熔断性检查
                if len(asr_decoder.tokens) >= 30:
                    # 长期重复熔断
                    if len(set(asr_decoder.tokens[-30:])) <= 3:
                        res.is_aborted = True
                        break
                    # 30个token无标点熔断
                    if len(asr_decoder.tokens) == 30 and not re.search(r'[，。？！、；：,\.?!;:]', asr_decoder.generated_text):
                        res.is_aborted = True
                        break
        
        asr_decoder.flush()
        res.text = asr_decoder.generated_text
        res.n_gen = asr_decoder.tokens_generated
        res.t_gen = time.perf_counter() - t_gen_start
        
        return res
