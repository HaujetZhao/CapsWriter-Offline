# coding=utf-8
import numpy as np
from typing import Optional, List
from .inference.engine import SenseVoiceInference
from .inference.schema import ASREngineConfig as SenseVoiceConfig

class RecognitionResult:
    """兼容 sherpa-onnx 的识别结果结构"""
    def __init__(self):
        self.text = ""
        self.tokens = []
        self.timestamps = []

class RecognitionStream:
    """兼容 sherpa-onnx 的识别流结构"""
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.audio_data = None
        self.result = RecognitionResult()

    def accept_waveform(self, sample_rate, audio):
        self.sample_rate = sample_rate
        self.audio_data = audio.astype(np.float32)

class SenseVoiceEngine:
    """SenseVoice 推理引擎适配器"""

    def __init__(self, config: SenseVoiceConfig):
        self.config = config
        self.engine = SenseVoiceInference(config)

    def create_stream(self, hotwords: Optional[str] = None):
        """创建识别流"""
        return RecognitionStream()

    def decode_stream(
        self, 
        stream: RecognitionStream, 
        context: Optional[str] = None,
        language: Optional[str] = None,
        itn: bool = True
    ):
        """
        解码识别流
        """
        if stream.audio_data is None:
            return

        # 执行识别
        # lid 参数映射：'auto', 'zh', 'en', 'ja', 'ko', 'yue'
        res = self.engine.recognize(
            stream.audio_data, 
            lid=language or "auto", 
            itn=itn
        )

        # 更新结果
        stream.result.text = res.text
        
        # 将内部 RecognitionResult 转换为 tokens 和 timestamps 以兼容 server_recognize
        stream.result.tokens = [r.text for r in res.results]
        stream.result.timestamps = [r.start for r in res.results]

    def update_hotwords(self, hotwords: List[str]):
        """更新热词"""
        self.engine.update_hotwords(hotwords)

    def cleanup(self):
        """释放资源"""
        pass

