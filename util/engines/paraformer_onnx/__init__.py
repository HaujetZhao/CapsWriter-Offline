import sherpa_onnx
from util import get_logger
from typing import Optional

logger = get_logger('server')

class ParaformerEngine:
    """
    Paraformer 识别引擎包装类
    封装 sherpa_onnx.OfflineRecognizer，支持 API 自定义
    """

    def __init__(self, **kwargs):
        """
        初始化 Paraformer 引擎
        
        Args:
            **kwargs: 传递给 sherpa_onnx.OfflineRecognizer.from_paraformer 的参数
        """
        logger.debug(f"正在初始化 ParaformerEngine，参数: {kwargs}")
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(**kwargs)

    def create_stream(self, hotwords: Optional[str] = None):
        """
        创建识别流
        
        Args:
            hotwords: 热词（目前原生 sherpa-onnx 在 stream 级别支持有限）
        """
        return self.recognizer.create_stream(hotwords=hotwords)

    def decode_stream(self, stream, context: Optional[str] = None):
        """
        解码识别流
        
        Args:
            stream: 识别流对象
            context: 上下文（若支持）
        """
        # 注意：原生 sherpa-onnx OfflineRecognizer.decode_stream 不支持 context 参数
        # 这里预留接口，如果未来需要自定义处理逻辑可以在此实现
        if context:
            logger.debug(f"ParaformerEngine 收到 context: {context}，当前原生引擎暂不支持该参数，已忽略")
        
        return self.recognizer.decode_stream(stream)

    def __getattr__(self, name):
        """转发其它属性调用至原始 recognizer"""
        return getattr(self.recognizer, name)


def create_asr_engine(**kwargs):
    """
    创建 Paraformer-ONNX 识别引擎实例
    """
    return ParaformerEngine(**kwargs)
