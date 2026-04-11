# coding: utf-8
from typing import Any
from ..base import BasePuncEngine


class CTTransformerPuncEngine(BasePuncEngine):
    """
    基于 CT-Transformer 的标点补全引擎 (使用 sherpa-onnx 实现)
    """

    def __init__(self, model_path: str):
        super().__init__(model_path)
        self.model_path = model_path
        self.engine = None
        self._initialize()

    def _initialize(self):
        """延迟初始化内核"""
        import sherpa_onnx
        punc_cfg = sherpa_onnx.OfflinePunctuationConfig(
            model=sherpa_onnx.OfflinePunctuationModelConfig(
                ct_transformer=self.model_path
            ),
        )
        self.engine = sherpa_onnx.OfflinePunctuation(punc_cfg)

    def punctuate(self, text: str) -> str:
        """为文本注入标点"""
        if not self.engine or not text:
            return text
        try:
            return self.engine.add_punctuation(text)
        except Exception:
            return text

    def cleanup(self):
        """释放资源"""
        self.engine = None
