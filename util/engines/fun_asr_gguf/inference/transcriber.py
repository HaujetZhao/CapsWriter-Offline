import os
import time
from typing import Optional, List, Dict, Any

from .schema import TranscriptionResult, RecognitionStream
from .audio import load_audio
from .text_merge import merge_transcription_results
from .display import DisplayReporter
from .srt_utils import generate_srt_file
from .utils import timer


class AudioTranscriber:
    """音频转录器：负责长短音频文件的分段、流式处理以及结果合并"""
    def __init__(self, pipeline, sample_rate: int = 16000):
        self.pipeline = pipeline
        self.sample_rate = sample_rate

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
        srt: bool = False,
        temperature: float = 0.4,
        top_p: float = 1.0,
        top_k: int = 50
    ) -> TranscriptionResult:
        result = TranscriptionResult()
        
        reporter = DisplayReporter(verbose=verbose)
        try:
            self._print_header(reporter, audio_path)

            reporter.print("\n[1] 加载音频...")
            audio, result.timings.load_audio = timer(
                load_audio,
                audio_path, 
                self.sample_rate, 
                start_second=start_second, 
                duration=duration
            )
            
            audio_duration = len(audio) / self.sample_rate
            reporter.print(f"    音频长度: {audio_duration:.2f}s")
            if start_second: reporter.print(f"    起始偏移: {start_second:.2f}s")

            base_offset = start_second if start_second else 0.0

            _, result.timings.total = timer(
                self._process_audio, audio, result, language, context, verbose, segment_size, overlap, reporter,
                base_offset, temperature=temperature, top_p=top_p, top_k=top_k
            )

            self._print_stats(reporter, result)

            # 3. Export SRT
            if srt and result.segments:
                srt_path = os.path.splitext(audio_path)[0] + ".srt"
                generate_srt_file(result.segments, srt_path)
                reporter.print(f"✓ 字幕已导出至: {os.path.basename(srt_path)}", force=True)

            if result.text:
                reporter.print("\n" + "-"*30 + " 完整转录文本 " + "-"*30, force=True)
                reporter.print(result.text, force=True)
                reporter.print("-" * 74 + "\n", force=True)

            return result

        except Exception as e:
            reporter.print(f"\n✗ 转录失败: {e}", force=True)
            raise
        
        finally:
            reporter.stop()

    def _process_audio(self, audio, result, language, context, verbose, segment_size, overlap, reporter, base_offset,
                       temperature=0.8, top_p=1.0, top_k=50):
        audio_duration = len(audio) / self.sample_rate
        
        segments_info = list(self._generate_segments(audio_duration, segment_size, overlap))
        is_multi = len(segments_info) > 1

        if is_multi:
            reporter.print(f"    检测到长音频，开启分段识别模式...", force=True)
            reporter.skip_technical = True

        segment_results = []

        for idx, (s_s, e_s) in enumerate(segments_info):
            if is_multi:
                reporter.set_segment(idx + 1, len(segments_info))
                reporter.print(f"\n--- 处理分段 [{s_s:.1f}s - {e_s:.1f}s] ---", force=True)
            
            chunk = audio[int(s_s * self.sample_rate):int(e_s * self.sample_rate)]
            stream = RecognitionStream()
            stream.accept_waveform(self.sample_rate, chunk)
            
            # 单段保持用户传入的 verbose 设定，多段统一在分段内部进行 detailed logging
            d_res = self.pipeline.decode_stream(stream, language, context, verbose if not is_multi else True, reporter,
                                               temperature=temperature, top_p=top_p, top_k=top_k)
            
            segment_results.append({
                'text': d_res.text,
                'segments': d_res.aligned,
                'duration': e_s - s_s,
                'hotwords': d_res.hotwords,
                'ctc_text': "".join([r.text for r in d_res.ctc_results]) if d_res.ctc_results else ""
            })
            
            # Accumulate timings
            result.timings += d_res.timings

        # 结果收尾与合并
        if len(segments_info) > 1:
            reporter.set_segment(0, 0)
            reporter.skip_technical = False
        
        # 统一的单分段与多分段合并逻辑
        offsets = [s[0] + base_offset for s in segments_info]
        full_text, full_segs = merge_transcription_results(segment_results, offsets, overlap)
        result.text = full_text
        result.segments = full_segs
        
        all_h = set()
        all_ctc = []
        for r in segment_results:
            all_h.update(r['hotwords'])
            if r['ctc_text']: all_ctc.append(r['ctc_text'])
        result.hotwords = list(all_h)
        result.ctc_text = "".join(all_ctc)

    def _generate_segments(self, duration: float, segment_size: float, overlap: float):
        """生成音频切片的起止时间产生器"""
        if duration <= segment_size + 2.0:
            yield (0.0, duration)
            return

        step = segment_size - overlap
        curr = 0.0
        while curr < duration:
            end = min(curr + segment_size, duration)
            yield (curr, end)
            if end >= duration: break
            curr += step

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
