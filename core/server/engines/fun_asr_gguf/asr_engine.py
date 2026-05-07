# coding: utf-8
import os
import time
from typing import Optional, List, Dict, Any

from .inference.schema import ASREngineConfig, TranscriptionResult, RecognitionResult as InternalResult, DecodeResult, Statistics
from .inference.models import Models
from .inference.pipeline import InferencePipeline
from .inference.transcriber import AudioTranscriber
from ..base import BaseASREngine, RecognitionStream, EngineCapabilities, RecognitionResult
from ..language import get_language, ENGINE_FUN_ASR_NANO


class FunASRStream(RecognitionStream):
    """
    FunASR-Nano 识别流适配器
    桥接内部的音频输入与标准的 RecognitionResult
    """
    def __init__(self, pipeline: InferencePipeline, sample_rate: int = 16000, hotwords: Optional[str] = None):
        super().__init__(sample_rate)
        self.internal_stream = pipeline.create_stream()

    def accept_waveform(self, sample_rate: int, audio: Any):
        # 内部 stream 已经实现了兼容性 accept_waveform
        self.internal_stream.accept_waveform(sample_rate, audio)


class FunASREngine(BaseASREngine):
    """
    FunASR 推理引擎适配器
    
    具备的全能模型能力：ASR, TIMESTAMPS, HOTWORDS, PUNC
    """

    def __init__(self, config: ASREngineConfig):
        super().__init__(config)
        # 初始化底层组件 (迁移自原本的 Facade)
        self.models = Models(self.config)
        self.pipeline = InferencePipeline(self.models)

    @property
    def capabilities(self) -> List[EngineCapabilities]:
        """声明 nano 引擎的全能属性"""
        return [
            EngineCapabilities.ASR, 
            EngineCapabilities.TIMESTAMPS, 
            EngineCapabilities.HOTWORDS, 
            EngineCapabilities.PUNC
        ]

    def create_stream(self, hotwords: Optional[str] = None) -> FunASRStream:
        """创建包装后的识别流"""
        return FunASRStream(self.pipeline, sample_rate=self.config.sample_rate, hotwords=hotwords)

    def decode_stream(
        self,
        stream: FunASRStream,
        context: Optional[str] = None,
        language: Optional[str] = None,
        **kwargs
    ):
        """解码识别流并同步结果"""
        # 语言映射：统一代码 → FunASR 中文文本
        mapped_lang = get_language(ENGINE_FUN_ASR_NANO, language) if language else None
        self.pipeline.decode_stream(stream.internal_stream, context=context, language=mapped_lang)
        
        # 2. 同步结果到标准 RecognitionResult
        res = stream.internal_stream.result
        stream.result.text = res.text
        stream.result.tokens = list(res.tokens)
        stream.result.timestamps = list(res.timestamps)

    def update_hotwords(self, hotwords: List[str]):
        """更新热词（透传至模型层）"""
        self.models.ctc_decoder.update_hotwords(hotwords)

    def cleanup(self):
        """释放资源"""
        self.models.cleanup()
