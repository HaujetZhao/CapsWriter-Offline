import time
import ctypes
import numpy as np
from typing import List, Tuple, Optional, Dict, Any

from .. import nano_llama
from ..nano_ctc import decode_ctc, align_timestamps
from ..nano_onnx import encode_audio
from ..utils import vprint
from ..nano_dataclass import DecodeResult, Timings, RecognitionStream
from ..display import DisplayReporter
from .model_manager import ModelManager

class CTCDecoder:
    """负责 CTC 推理和热词匹配"""
    def __init__(self, models: ModelManager):
        self.models = models

    def decode(self, enc_output: np.ndarray, enable_ctc: bool, max_hotwords: int) -> Tuple[List, List[str]]:
        if not enable_ctc or self.models.ctc_sess is None:
            return [], []

        ctc_logits = self.models.ctc_sess.run(None, {"enc_output": enc_output})[0]
        ctc_text, ctc_results = decode_ctc(ctc_logits, self.models.ctc_id2token)

        hotwords = []
        if self.models.corrector and self.models.corrector.hotwords and ctc_text:
            res = self.models.corrector.correct(ctc_text, k=max_hotwords)
            candidates = set()
            for _, hw, _ in res.matchs: candidates.add(hw)
            for _, hw, _ in res.similars: candidates.add(hw)
            hotwords = list(candidates)
            
        return ctc_results, hotwords

class LLMDecoder:
    """负责 LLM 推理循环"""
    def __init__(self, models: ModelManager):
        self.models = models
        self.stop_tokens = [151643, 151645]

    def decode(
        self,
        full_embd: np.ndarray,
        n_input_tokens: int,
        n_predict: int,
        stream_output: bool = False,
        reporter: Optional[DisplayReporter] = None
    ) -> Tuple[str, int, float, float]:
        
        t_inject_start = time.perf_counter()
        
        # 1. Inject
        mem = nano_llama.llama_get_memory(self.models.ctx)
        nano_llama.llama_memory_clear(mem, True)
        
        batch_embd = nano_llama.llama_batch_init(n_input_tokens, full_embd.shape[1], 1)
        batch_embd.n_tokens = n_input_tokens
        batch_embd.token = ctypes.cast(None, ctypes.POINTER(nano_llama.llama_token))
        
        if not full_embd.flags['C_CONTIGUOUS']:
            full_embd = np.ascontiguousarray(full_embd)
        ctypes.memmove(batch_embd.embd, full_embd.ctypes.data, full_embd.nbytes)

        for k in range(n_input_tokens):
            batch_embd.pos[k] = k
            batch_embd.n_seq_id[k] = 1
            batch_embd.seq_id[k][0] = 0
            batch_embd.logits[k] = 1 if k == n_input_tokens - 1 else 0

        ret = nano_llama.llama_decode(self.models.ctx, batch_embd)
        nano_llama.llama_batch_free(batch_embd)
        if ret != 0: raise RuntimeError(f"Decode failed (ret={ret})")
        
        t_inject = time.perf_counter() - t_inject_start

        # 2. Generation Loop
        t_gen_start = time.perf_counter()
        vocab_size = nano_llama.llama_vocab_n_tokens(self.models.vocab)
        batch_text = nano_llama.llama_batch_init(1, 0, 1)
        batch_text.n_tokens = 1

        generated_text = ""
        current_pos = n_input_tokens
        decoder_utf8 = nano_llama.ByteDecoder()
        tokens_generated = 0

        for _ in range(n_predict):
            logits_ptr = nano_llama.llama_get_logits(self.models.ctx)
            logits_arr = np.ctypeslib.as_array(logits_ptr, shape=(vocab_size,))
            token_id = int(np.argmax(logits_arr))

            if token_id == self.models.eos_token or token_id in self.stop_tokens:
                break

            raw_bytes = nano_llama.token_to_bytes(self.models.vocab, token_id)
            text_piece = decoder_utf8.decode(raw_bytes)
            generated_text += text_piece
            tokens_generated += 1

            if stream_output:
                if reporter: reporter.stream(text_piece)
                else: print(text_piece, end="", flush=True)

            batch_text.token[0] = token_id
            batch_text.pos[0] = current_pos
            batch_text.n_seq_id[0] = 1
            batch_text.seq_id[0][0] = 0
            batch_text.logits[0] = 1

            if nano_llama.llama_decode(self.models.ctx, batch_text) != 0: break
            current_pos += 1

        remaining = decoder_utf8.flush()
        generated_text += remaining
        if stream_output and remaining:
            if reporter: reporter.stream(remaining)
            else: print(remaining, end="", flush=True)

        nano_llama.llama_batch_free(batch_text)
        t_gen = time.perf_counter() - t_gen_start
        
        return generated_text, tokens_generated, t_inject, t_gen

class StreamDecoder:
    """协调完整流程的解码器"""
    def __init__(self, models: ModelManager):
        self.models = models
        self.ctc_decoder = CTCDecoder(models)
        self.llm_decoder = LLMDecoder(models)

    def decode_stream(
        self,
        stream: RecognitionStream,
        language: Optional[str] = None,
        context: Optional[str] = None,
        verbose: bool = False,
        reporter: Optional[DisplayReporter] = None
    ) -> DecodeResult:
        
        timings = Timings()
        
        # 1. Encode
        if reporter: reporter.print("\n[2] 音频编码...")
        t_s = time.perf_counter()
        audio_embd, enc_output = encode_audio(stream.audio_data, self.models.encoder_sess)
        timings.encode = time.perf_counter() - t_s
        if reporter: reporter.print(f"    耗时: {timings.encode*1000:.2f}ms")

        # 2. CTC
        if reporter: reporter.print("\n[3] CTC 解码...")
        t_s = time.perf_counter()
        ctc_results, hotwords = self.ctc_decoder.decode(
            enc_output, 
            self.models.config.enable_ctc, 
            self.models.config.max_hotwords
        )
        timings.ctc = time.perf_counter() - t_s
        
        if verbose and ctc_results:
            ctc_text = "".join([r.text for r in ctc_results])
            if reporter:
                reporter.print(f"    CTC: {ctc_text}")
                if hotwords: reporter.print(f"    热词: {hotwords}")
        if reporter: reporter.print(f"    耗时: {timings.ctc*1000:.2f}ms")

        # 3. Prompt
        if reporter: reporter.print("\n[4] 准备 Prompt...")
        t_s = time.perf_counter()
        p_embd, s_embd, n_p, n_s, p_text = self.models.prompt_builder.build_prompt(hotwords, language, context)
        timings.prepare = time.perf_counter() - t_s
        
        if verbose and reporter:
            reporter.print("-" * 15 + " Prefix Prompt " + "-" * 15 + "\n" + p_text + "\n" + "-" * 40)
        if reporter:
            reporter.print(f"    Prefix: {n_p} tokens")
            reporter.print(f"    Suffix: {n_s} tokens")

        # 4. LLM
        if reporter:
            reporter.print("\n[5] LLM 解码...")
            reporter.print("=" * 70)
        
        full_embd = np.concatenate([p_embd, audio_embd.astype(np.float32), s_embd], axis=0)
        text, n_gen, t_inj, t_gen = self.llm_decoder.decode(
            full_embd, full_embd.shape[0], self.models.config.n_predict, 
            stream_output=verbose, reporter=reporter
        )
        text = text.strip()
        timings.inject = t_inj
        timings.llm_generate = t_gen
        
        if reporter: reporter.print("\n" + "=" * 70)

        # 5. Align
        if reporter: reporter.print("\n[6] 时间戳对齐")
        t_s = time.perf_counter()
        aligned = None
        timestamps = []
        tokens = []
        if ctc_results:
            aligned = align_timestamps(ctc_results, text)
            if aligned:
                tokens = [seg['char'] for seg in aligned]
                timestamps = [seg['start'] for seg in aligned]
        timings.align = time.perf_counter() - t_s
        
        if reporter and aligned:
            reporter.print(f"    对齐耗时: {timings.align*1000:.2f}ms")
            preview = " ".join([f"{r['char']}({r['start']:.2f}s)" for r in aligned[:10]])
            if len(aligned) > 10: preview += " ..."
            reporter.print(f"    结果预览: {preview}")

        # Set stream result
        stream.set_result(text=text, timestamps=timestamps, tokens=tokens)
        
        return DecodeResult(
            text=text, ctc_results=ctc_results, aligned=aligned,
            audio_embd=audio_embd, n_prefix=n_p, n_suffix=n_s,
            n_gen=n_gen, timings=timings, hotwords=hotwords
        )
