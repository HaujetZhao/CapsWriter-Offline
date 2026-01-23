import os
import time
import numpy as np
from typing import Optional, List

from ..nano_audio import load_audio
from ..text_merge import merge_transcription_results
from ..srt_utils import generate_srt_file
from ..display import DisplayReporter
from ..nano_dataclass import TranscriptionResult, Statistics, RecognitionStream
from .model_manager import ModelManager
from .decoder import StreamDecoder

class TranscriptionOrchestrator:
    """负责高层转录任务的编排"""
    def __init__(self, models: ModelManager):
        self.models = models
        self.decoder = StreamDecoder(models)

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        context: Optional[str] = None,
        verbose: bool = True,
        segment_size: float = 60.0,
        overlap: float = 2.0,
        start_second: Optional[float] = None,
        duration: Optional[float] = None,
        srt: bool = False
    ) -> TranscriptionResult:
        
        result = TranscriptionResult()
        
        with DisplayReporter(verbose=verbose) as reporter:
            try:
                t_start = time.perf_counter()
                self._print_header(reporter, audio_path)

                # 1. Load Audio
                reporter.print("\n[1] 加载音频...")
                audio = load_audio(
                    audio_path, 
                    self.models.config.sample_rate, 
                    start_second=start_second, 
                    duration=duration
                )
                
                audio_duration = len(audio) / self.models.config.sample_rate
                reporter.print(f"    音频长度: {audio_duration:.2f}s")
                if start_second:
                    reporter.print(f"    起始偏移: {start_second:.2f}s")

                base_offset = start_second if start_second else 0.0

                # 2. Strategy Selection
                if audio_duration <= segment_size + 2.0:
                    self._transcribe_short(audio, result, language, context, verbose, reporter, base_offset)
                else:
                    self._transcribe_long(audio, result, language, context, verbose, segment_size, overlap, reporter, base_offset)

                result.timings.total = time.perf_counter() - t_start
                self._print_stats(reporter, result)

                # 3. Export SRT
                if srt and result.segments:
                    srt_path = os.path.splitext(audio_path)[0] + ".srt"
                    generate_srt_file(result.segments, srt_path)
                    reporter.print(f"✓ 字幕已导出至: {os.path.basename(srt_path)}", force=True)

                # 4. Final Text
                if result.text:
                    reporter.print("\n" + "-"*30 + " 完整转录文本 " + "-"*30, force=True)
                    reporter.print(result.text, force=True)
                    reporter.print("-" * 74 + "\n", force=True)

                return result

            except Exception as e:
                reporter.print(f"\n✗ 转录失败: {e}", force=True)
                raise

    def _transcribe_short(self, audio, result, language, context, verbose, reporter, base_offset):
        stream = RecognitionStream()
        stream.accept_waveform(self.models.config.sample_rate, audio)
        
        d_res = self.decoder.decode_stream(stream, language, context, verbose, reporter)
        
        # Sync stats
        for field in ['encode', 'ctc', 'prepare', 'inject', 'llm_generate', 'align']:
            setattr(result.timings, field, getattr(d_res.timings, field))
        
        result.text = d_res.text
        result.segments = []
        for seg in (d_res.aligned or []):
            result.segments.append({'char': seg['char'], 'start': seg['start'] + base_offset})
        
        result.hotwords = d_res.hotwords
        if d_res.ctc_results:
            result.ctc_text = "".join([r.text for r in d_res.ctc_results])

        if verbose:
            self._print_performance_stats(reporter, d_res, audio, result.timings.inject, result.timings.llm_generate)

    def _transcribe_long(self, audio, result, language, context, verbose, segment_size, overlap, reporter, base_offset):
        reporter.print(f"    检测到长音频，开启分段识别模式...", force=True)
        reporter.skip_technical = True
        
        audio_duration = len(audio) / self.models.config.sample_rate
        segments_info = []
        step = segment_size - overlap
        curr = 0.0
        while curr < audio_duration:
            end = min(curr + segment_size, audio_duration)
            segments_info.append((curr, end))
            if end >= audio_duration: break
            curr += step

        segment_results = []
        for idx, (s_s, e_s) in enumerate(segments_info):
            reporter.set_segment(idx + 1, len(segments_info))
            reporter.print(f"\n--- 处理分段 [{s_s:.1f}s - {e_s:.1f}s] ---", force=True)
            
            chunk = audio[int(s_s * self.models.config.sample_rate):int(e_s * self.models.config.sample_rate)]
            stream = RecognitionStream()
            stream.accept_waveform(self.models.config.sample_rate, chunk)
            
            # Sub-segment always uses verbose=True for tokens, but reporter will filter tech logs
            d_res = self.decoder.decode_stream(stream, language, context, True, reporter)
            
            segment_results.append({
                'text': d_res.text,
                'segments': d_res.aligned,
                'duration': e_s - s_s,
                'hotwords': d_res.hotwords,
                'ctc_text': "".join([r.text for r in d_res.ctc_results]) if d_res.ctc_results else ""
            })
            
            # Accumulate timings
            result.timings.encode += d_res.timings.encode
            result.timings.ctc += d_res.timings.ctc
            result.timings.prepare += d_res.timings.prepare
            result.timings.inject += d_res.timings.inject
            result.timings.llm_generate += d_res.timings.llm_generate
            result.timings.align += d_res.timings.align

        reporter.set_segment(0, 0)
        reporter.skip_technical = False
        
        # Merge
        offsets = [s[0] + base_offset for s in segments_info]
        full_text, full_segs = merge_transcription_results(segment_results, offsets, overlap)
        result.text = full_text
        result.segments = full_segs
        
        # Global hotwords/ctc
        all_h = set()
        all_ctc = []
        for r in segment_results:
            all_h.update(r['hotwords'])
            if r['ctc_text']: all_ctc.append(r['ctc_text'])
        result.hotwords = list(all_h)
        result.ctc_text = "".join(all_ctc)

    def _print_header(self, reporter, audio_path):
        line = "=" * 70
        reporter.print(f"\n{line}", force=True)
        reporter.print(f"处理音频: {os.path.basename(audio_path)}", force=True)
        reporter.print(f"{line}", force=True)

    def _print_stats(self, reporter, result):
        reporter.print(f"\n[转录耗时]")
        reporter.print(f"  - 音频编码： {result.timings.encode*1000:5.0f}ms")
        reporter.print(f"  - CTC解码：  {result.timings.ctc*1000:5.0f}ms")
        reporter.print(f"  - LLM读取：  {result.timings.inject*1000:5.0f}ms")
        reporter.print(f"  - LLM生成：  {result.timings.llm_generate*1000:5.0f}ms")
        reporter.print(f"  - 总耗时：   {result.timings.total:5.2f}s\n")

    def _print_performance_stats(self, reporter, d_res, audio, t_inject, t_llm):
        stats = Statistics(
            audio_duration=len(audio)/self.models.config.sample_rate,
            n_input_tokens=d_res.audio_embd.shape[0] + d_res.n_prefix + d_res.n_suffix,
            n_prefix_tokens=d_res.n_prefix,
            n_audio_tokens=d_res.audio_embd.shape[0],
            n_suffix_tokens=d_res.n_suffix,
            n_generated_tokens=d_res.n_gen,
        )
        if t_inject > 0: stats.tps_in = stats.n_input_tokens / t_inject
        if t_llm > 0: stats.tps_out = d_res.n_gen / t_llm
        reporter.print(f"\n[统计]\n{stats}")
