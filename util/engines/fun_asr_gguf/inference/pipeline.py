import time
import re
import ctypes
import numpy as np
from typing import List, Tuple, Optional, Dict, Any

from . import logger
from . import llama
from .ctc_decoder import CTCDecoder
from .utils import vprint, timer
from .schema import DecodeResult, Timings, RecognitionStream, LLMDecodeResult
from .display import DisplayReporter
from .models import Models
from .ctc_aligner import CTCAligner
from .llm_decoder import LLMDecoder

# 全局静默 Reporter，用于默认参数，避免重复创建线程
_SILENT_REPORTER = DisplayReporter(verbose=False)

class InferencePipeline:
    """ASR 核心指挥者 (Conductor)：负责调度音频编码、CTC 解码、Prompt 构建及 LLM 推理等细粒度组件"""
    def __init__(self, models: Models):
        self.models = models
        self.llm_decoder = LLMDecoder(models)

    def create_stream(self) -> RecognitionStream:
        """创建识别流"""
        return RecognitionStream(sample_rate=self.models.config.sample_rate)

    def decode_stream(
        self,
        stream: RecognitionStream,
        language: Optional[str] = None,
        context: Optional[str] = None,
        verbose: bool = True,
        reporter: Optional[DisplayReporter] = None,
        temperature: float = 0.3,
        top_p: float = 1.0,
        top_k: int = 50,
        timestamp_offset: float = -0.24
    ) -> DecodeResult:
        
        reporter = reporter or _SILENT_REPORTER
        timings = Timings()

        # 0. 检查原始音频数据长度，空音频防御
        if len(stream.audio_data) < 1600:
            return DecodeResult(text="", timings=timings)
        
        # 1. Encode
        reporter.print("\n[2] 音频编码...")
        (audio_embd, enc_output), timings.encode = timer(self.models.encoder.encode, stream.audio_data)
        reporter.print(f"    耗时: {timings.encode*1000:.2f}ms")

        # 2. CTC Decoding
        reporter.print("\n[3] CTC 解码...")
        (ctc_results, hotwords, ctc_times), timings.ctc = timer(
            self.models.ctc_decoder.decode,
            enc_output, 
            self.models.config.enable_ctc, 
            self.models.config.max_hotwords, 
            top_k = self.models.config.ctc_topk
        )
        reporter.print(f"    CTC: {''.join([r.text for r in ctc_results])}")
        reporter.print(f"    热词: {hotwords}")
        t_detail = " | ".join([f"{k}:{v*1000:.1f}ms" for k, v in ctc_times.items() if v > 0])
        reporter.print(f"    耗时: {timings.ctc*1000:.2f}ms ({t_detail})")

        # 3. Prompt Builder
        reporter.print("\n[4] 准备 Prompt...")
        (p_embd, s_embd, n_p, n_s, p_text), timings.prepare = timer(
            self.models.prompt_builder.build_prompt, hotwords, language, context
        )
        if reporter.verbose and reporter.skip_technical is False:
            reporter.print("-" * 15 + " Prefix Prompt " + "-" * 15 + "\n" + p_text + "\n" + "-" * 40)
        reporter.print(f"    Prefix: {n_p} tokens")
        reporter.print(f"    Suffix: {n_s} tokens")

        # 4. LLM Decoding Loop
        reporter.print("\n[5] LLM 解码...")
        reporter.print("=" * 70)
        full_embd = np.concatenate([p_embd, audio_embd.astype(np.float32), s_embd], axis=0)
        n_input_tokens = full_embd.shape[0]

        # 5. LLM 解码循环：若熔断则加温重试（最多重试 3 次）
        llm_res = None
        current_temp = temperature
        for retry_idx in range(4):
            llm_res = self.llm_decoder.decode(
                full_embd, n_input_tokens, self.models.config.n_predict, 
                stream_output=verbose, reporter=reporter,
                temperature=current_temp, top_p=top_p, top_k=top_k
            )
            if not llm_res.is_aborted: break
            llm_res.text += "====解码有误，强制熔断===="
            current_temp += 0.3
            print(f"\n\n[!] 解码有误，熔断重试 (温度设为 {current_temp:.1f}, retry: {retry_idx})\n")
        text = llm_res.text.strip()
        timings.inject = llm_res.t_inject
        timings.llm_generate = llm_res.t_gen
        
        if reporter: reporter.print("\n" + "=" * 70)

        # 6. Timestamp Alignment
        reporter.print("\n[6] 时间戳对齐")
        aligned, timings.align = timer(CTCAligner.align, ctc_results, text, timestamp_offset=timestamp_offset)
        tokens = [seg[0] for seg in aligned]
        timestamps = [seg[1] for seg in aligned]

        reporter.print(f"    对齐耗时: {timings.align*1000:.2f}ms")
        preview = " ".join([f"{r[0]}({r[1]:.2f}s)" for r in aligned[:10]])
        if len(aligned) > 10: preview += " ..."
        reporter.print(f"    结果预览: {preview}")

        # Set stream result
        stream.set_result(text=text, timestamps=timestamps, tokens=tokens)
        
        return DecodeResult(
            text=text, ctc_results=ctc_results, aligned=aligned,
            audio_embd=audio_embd, n_prefix=n_p, n_suffix=n_s,
            n_gen=llm_res.n_gen, timings=timings, hotwords=hotwords,
            is_aborted=llm_res.is_aborted
        )


