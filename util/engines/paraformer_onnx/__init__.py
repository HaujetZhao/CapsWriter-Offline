import sherpa_onnx
from util import get_logger
from typing import Optional, List
from dataclasses import dataclass

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

class ParaformerEngine:
    """
    Paraformer 识别引擎包装类
    封装 sherpa_onnx.OfflineRecognizer，支持 API 自定义
    """

    def __init__(self, config: ASREngineConfig):
        """
        初始化 Paraformer 引擎
        
        Args:
            config: ASREngineConfig 配置对象
        """
        self.config = config
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

    def create_stream(self, hotwords: Optional[str] = None):
        """创建识别流"""
        return self.recognizer.create_stream(hotwords=hotwords)

    def decode_stream(self, stream, context: Optional[str] = None):
        """解码识别流"""
        if context:
            logger.debug(f"ParaformerEngine 收到 context: {context}，当前暂不支持，已忽略")
        return self.recognizer.decode_stream(stream)

    def update_hotwords(self, hotwords: List[str]):
        """更新热词（Paraformer 暂不支持通过此接口动态更新，仅为 API 兼容）"""
        pass

    def __getattr__(self, name):
        """转发其它属性调用至原始 recognizer"""
        return getattr(self.recognizer, name)


def create_asr_engine(**kwargs):
    """
    [兼容性接口] 创建 Paraformer-ONNX 识别引擎实例
    建议直接使用 ParaformerEngine(ASREngineConfig(**kwargs))
    """
    config = ASREngineConfig(**kwargs)
    return ParaformerEngine(config)
