# coding: utf-8
import sherpa_onnx
import numpy as np
from typing import Optional, List, Any
from dataclasses import dataclass
from ..base import BaseEngine, RecognitionStream, EngineCapabilities, RecognitionResult
from util import get_logger

logger = get_logger('server')


@dataclass
class ASREngineConfig:
    """Paraformer 引擎配置参数"""
    paraformer: str
    tokens: str
    num_threads: int = 4
    sample_rate: int = 16000
    feature_dim: int = 80
    decoding_method: str = 'greedy_search'
    provider: str = 'cpu'
    debug: bool = False


class ParaformerStream(RecognitionStream):
    """
    Paraformer 识别流包装类
    转发调用至 sherpa_onnx.OfflineStream 并暴露标准结果接口
    """
    def __init__(self, recognizer: sherpa_onnx.OfflineRecognizer, sample_rate: int = 16000, hotwords: Optional[str] = None):
        super().__init__(sample_rate)
        # 实际创建 sherpa-onnx 的流
        self.internal_stream = recognizer.create_stream(hotwords=hotwords)

    def accept_waveform(self, sample_rate: int, audio: np.ndarray):
        self.internal_stream.accept_waveform(sample_rate, audio.astype(np.float32))


class ParaformerEngine(BaseEngine):
    """
    Paraformer 识别引擎适配器
    
    声明能力：ASR, TIMESTAMPS
    不支持：PUNC, HOTWORDS (内置)
    """

    def __init__(self, config: ASREngineConfig):
        super().__init__(config)
        logger.debug(f"正在初始化 ParaformerEngine，配置: {self.config}")
        
        # 提取参数用于 sherpa-onnx
        params = {
            'paraformer': self.config.paraformer,
            'tokens': self.config.tokens,
            'num_threads': self.config.num_threads,
            'sample_rate': self.config.sample_rate,
            'feature_dim': self.config.feature_dim,
            'decoding_method': self.config.decoding_method,
            'provider': self.config.provider,
            'debug': self.config.debug,
        }
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(**params)

    @property
    def capabilities(self) -> List[EngineCapabilities]:
        """声明具备的能力"""
        return [
            EngineCapabilities.ASR, 
            EngineCapabilities.TIMESTAMPS
        ]

    def create_stream(self, hotwords: Optional[str] = None) -> ParaformerStream:
        """创建包装后的识别流"""
        return ParaformerStream(self.recognizer, sample_rate=self.config.sample_rate, hotwords=hotwords)

    def decode_stream(
        self, 
        stream: ParaformerStream, 
        context: Optional[str] = None,
        **kwargs
    ):
        """解码识别流并同步结果"""
        if context:
            logger.debug(f"ParaformerEngine 不支持解码 context，已忽略")
        
        # 1. 调用内核解码
        self.recognizer.decode_stream(stream.internal_stream)
        
        # 2. 将 sherpa-onnx 的结果同步回标准结果结构
        res = stream.internal_stream.result
        stream.result.text = res.text
        stream.result.tokens = list(res.tokens)
        stream.result.timestamps = list(res.timestamps)

    def update_hotwords(self, hotwords: List[str]):
        """Paraformer 暂不支持动态更新热词"""
        pass

    def cleanup(self):
        """释放资源"""
        self.recognizer = None
