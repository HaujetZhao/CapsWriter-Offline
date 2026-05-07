# coding=utf-8
import numpy as np
from typing import List, Optional

from .inference.aligner import QwenForcedAligner as InternalAligner
from .inference.schema import AlignerConfig, ForcedAlignResult
from ..base import BaseAlignEngine
from ..language import get_language, ENGINE_ALIGNER


class QwenForceAligner(BaseAlignEngine):
    """
    Qwen-Force-Aligner 适配器
    
    负责包装底层的强制对齐逻辑，将识别出的文本与原始音频进行对齐，
    补全精确的时间戳信息。
    """

    def __init__(self, config: AlignerConfig):
        super().__init__(config)
        self.engine = InternalAligner(config)

    def align(
        self,
        audio: np.ndarray,
        text: str,
        language: Optional[str] = None,
        offset_sec: float = 0.0,
        **kwargs
    ) -> ForcedAlignResult:
        """
        执行强制对齐
        """
        if not text:
            return None

        # 语言映射：统一代码 → Aligner 英文明称，默认中文
        mapped = get_language(ENGINE_ALIGNER, language) if language else None

        return self.engine.align(
            audio=audio,
            text=text,
            language=mapped or "Chinese",
            offset_sec=offset_sec
        )

    def cleanup(self):
        """释放资源"""
        if hasattr(self.engine, 'ctx'):
            del self.engine.ctx
        if hasattr(self.engine, 'model'):
            del self.engine.model
        self.engine = None
