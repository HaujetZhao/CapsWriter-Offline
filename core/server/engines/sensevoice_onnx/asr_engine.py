# coding=utf-8
import numpy as np
from typing import Optional, List
from .inference.engine import SenseVoiceInference
from .inference.schema import ASREngineConfig as SenseVoiceConfig
from ..base import BaseASREngine, RecognitionStream, EngineCapabilities, RecognitionResult
from ..language import get_language, ENGINE_SENSEVOICE


class SenseVoiceStream(RecognitionStream):
    """SenseVoice 识别流结构"""
    def __init__(self, sample_rate=16000):
        super().__init__(sample_rate)
        self.audio_data = None

    def accept_waveform(self, sample_rate, audio):
        self.sample_rate = sample_rate
        self.audio_data = audio.astype(np.float32)


class SenseVoiceEngine(BaseASREngine):
    """SenseVoice 推理引擎适配器"""

    def __init__(self, config: SenseVoiceConfig):
        super().__init__(config)
        self.engine = SenseVoiceInference(config)

    @property
    def capabilities(self) -> List[EngineCapabilities]:
        """声明 SenseVoice 具备的能力集"""
        return [
            EngineCapabilities.ASR, 
            EngineCapabilities.PUNC, 
            EngineCapabilities.HOTWORDS,
            EngineCapabilities.TIMESTAMPS
        ]

    def create_stream(self, hotwords: Optional[str] = None) -> SenseVoiceStream:
        """创建识别流"""
        return SenseVoiceStream()

    def decode_stream(
        self, 
        stream: SenseVoiceStream, 
        context: Optional[str] = None,
        language: Optional[str] = None,
        itn: bool = True,
        **kwargs
    ):
        """
        解码识别流
        """
        if stream.audio_data is None:
            return

        # 语言映射：统一代码 → SenseVoice lid ('auto', 'zh', 'en', 'ja', 'ko', 'yue')
        lid = get_language(ENGINE_SENSEVOICE, language) if language else None
        res = self.engine.recognize(
            stream.audio_data,
            lid=lid or "auto",
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

