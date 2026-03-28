import os
import time
from typing import Optional, List, Dict, Any

from .schema import ASREngineConfig, TranscriptionResult, RecognitionStream, DecodeResult, Statistics
from .models import Models
from .pipeline import InferencePipeline
from .transcriber import AudioTranscriber

class FunASREngine:
    """FunASR 推理引擎外观类 (Facade)"""

    def __init__(self, config: ASREngineConfig):
        # 封装配置
        self.config = config

        # 初始化底层组件
        self.models = Models(self.config)

        # 直接委派核心方法
        self.pipeline = InferencePipeline(self.models)
        self.create_stream = self.pipeline.create_stream
        self.decode_stream = self.pipeline.decode_stream
        
        # 实例化负责文件转录的业务类
        self.transcriber = AudioTranscriber(self.pipeline, self.config.sample_rate)
        self.transcribe = self.transcriber.transcribe


    def update_hotwords(self, hotwords: List[str]):
        """更新热词（由父库调用）"""
        self.models.ctc_decoder.update_hotwords(hotwords)

    def cleanup(self):
        """释放资源"""
        self.models.cleanup()
