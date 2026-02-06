"""
ASR 推理引擎入口点 (Facade)

本模块现在作为外观类工作，将复杂的推理流程委托给 core/ 目录下的专业组件。
保持了与旧版 API 的完全兼容。
"""

import os
from typing import Optional

from .nano_dataclass import ASREngineConfig, TranscriptionResult, RecognitionStream, DecodeResult
from .core.model_manager import ModelManager
from .core.orchestrator import TranscriptionOrchestrator

class FunASREngine:
    """FunASR 推理引擎 (Facade 模式)"""

    def __init__(
        self,
        encoder_onnx_path: str,
        ctc_onnx_path: str,
        decoder_gguf_path: str,
        tokens_path: str,
        hotwords_path: str = None,
        enable_ctc: bool = True,
        n_predict: int = 512,
        n_threads: int = None,
        similar_threshold: float = 0.6,
        max_hotwords: int = 10,
        dml_enable: bool = True,
        vulkan_enable: bool = True,
        vulkan_force_fp32: bool = False,
    ):
        # 封装配置
        self.config = ASREngineConfig(
            encoder_onnx_path=encoder_onnx_path,
            ctc_onnx_path=ctc_onnx_path,
            decoder_gguf_path=decoder_gguf_path,
            tokens_path=tokens_path,
            hotwords_path=hotwords_path,
            enable_ctc=enable_ctc,
            n_predict=n_predict,
            n_threads=n_threads,
            similar_threshold=similar_threshold,
            max_hotwords=max_hotwords,
            dml_enable=dml_enable,
            vulkan_enable=vulkan_enable,
            vulkan_force_fp32=vulkan_force_fp32
        )

        # 初始化组件
        self.models = ModelManager(self.config)
        self.orchestrator = TranscriptionOrchestrator(self.models)
        self.sample_rate = self.config.sample_rate

    def initialize(self, verbose: bool = True) -> bool:
        """初始化模型资源"""
        return self.models.initialize(verbose=verbose)

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
        """转录音频文件 (委托给 Orchestrator)"""
        return self.orchestrator.transcribe(
            audio_path=audio_path,
            language=language,
            context=context,
            verbose=verbose,
            segment_size=segment_size,
            overlap=overlap,
            start_second=start_second,
            duration=duration,
            srt=srt,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k
        )

    def create_stream(self, hotwords: Optional[str] = None) -> RecognitionStream:
        """创建识别流（兼容 sherpa-onnx API）"""
        # 注意：此处 hotwords 参数在当前设计中通过 corrector 处理，stream 主要携带音频数据
        return RecognitionStream(sample_rate=self.sample_rate)

    def decode_stream(
        self,
        stream: RecognitionStream,
        language: Optional[str] = None,
        context: Optional[str] = None,
        verbose: bool = True,
        reporter = None,
        temperature: float = 0.3,
        top_p: float = 1.0,
        top_k: int = 50
    ) -> DecodeResult:
        """解码识别流 (委托给 Orchestrator 内置的 Decoder)"""
        return self.orchestrator.decoder.decode_stream(
            stream, language, context, verbose, reporter,
            temperature=temperature, top_p=top_p, top_k=top_k
        )

    def cleanup(self):
        """释放资源"""
        self.models.cleanup()


def create_asr_engine(
    encoder_onnx_path: str,
    ctc_onnx_path: str,
    decoder_gguf_path: str,
    tokens_path: str,
    hotwords_path: str = None,
    enable_ctc: bool = True,
    n_predict: int = 512,
    n_threads: int = None,
    similar_threshold: float = 0.6,
    max_hotwords: int = 10,
    dml_enable: bool = True,
    vulkan_enable: bool = True,
    vulkan_force_fp32: bool = False,
    verbose: bool = True,
) -> FunASREngine:
    """创建并初始化 ASR 引擎的快捷入口"""
    engine = FunASREngine(
        encoder_onnx_path=encoder_onnx_path,
        ctc_onnx_path=ctc_onnx_path,
        decoder_gguf_path=decoder_gguf_path,
        tokens_path=tokens_path,
        hotwords_path=hotwords_path,
        enable_ctc=enable_ctc,
        n_predict=n_predict,
        n_threads=n_threads,
        similar_threshold=similar_threshold,
        max_hotwords=max_hotwords,
        dml_enable=dml_enable,
        vulkan_enable=vulkan_enable,
        vulkan_force_fp32=vulkan_force_fp32,
    )
    if not engine.initialize(verbose=verbose):
        raise RuntimeError("Failed to initialize ASR engine")
    return engine

