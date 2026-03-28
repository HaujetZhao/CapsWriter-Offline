import sherpa_onnx
from util import get_logger
from typing import Optional, List
from dataclasses import dataclass

logger = get_logger('server')

@dataclass
class ASREngineConfig:
    """SenseVoice 引擎配置参数"""
    model: str
    tokens: str
    use_itn: bool = True
    language: str = 'zh'
    num_threads: int = 4
    provider: str = 'cpu'
    debug: bool = False

class SenseVoiceEngine:
    """
    SenseVoice 识别引擎包装类
    封装 sherpa_onnx.OfflineRecognizer，支持 API 自定义
    """

    def __init__(self, config: ASREngineConfig):
        """
        初始化 SenseVoice 引擎
        
        Args:
            config: ASREngineConfig 配置对象
        """
        self.config = config
        logger.debug(f"正在初始化 SenseVoiceEngine，配置: {self.config}")
        
        # 提取参数用于 sherpa-onnx
        params = {
            'model': self.config.model,
            'tokens': self.config.tokens,
            'use_itn': self.config.use_itn,
            'language': self.config.language,
            'num_threads': self.config.num_threads,
            'provider': self.config.provider,
            'debug': self.config.debug,
        }
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(**params)

    def create_stream(self, hotwords: Optional[str] = None):
        """创建识别流"""
        return self.recognizer.create_stream(hotwords=hotwords)

    def decode_stream(self, stream, context: Optional[str] = None):
        """解码识别流"""
        if context:
            logger.debug(f"SenseVoiceEngine 收到 context: {context}，当前暂不支持，已忽略")
        return self.recognizer.decode_stream(stream)

    def update_hotwords(self, hotwords: List[str]):
        """更新热词（SenseVoice 暂不支持动态更新，仅为 API 兼容）"""
        pass

    def __getattr__(self, name):
        """转发其它属性调用至原始 recognizer"""
        return getattr(self.recognizer, name)


def create_asr_engine(**kwargs):
    """
    [兼容性接口] 创建 SenseVoice-ONNX 识别引擎实例
    建议直接使用 SenseVoiceEngine(ASREngineConfig(**kwargs))
    """
    config = ASREngineConfig(**kwargs)
    return SenseVoiceEngine(config)
