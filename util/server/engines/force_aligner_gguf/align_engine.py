# coding=utf-8
import numpy as np
from typing import List, Optional

from .inference.aligner import QwenForcedAligner as InternalAligner
from .inference.schema import AlignerConfig, ForcedAlignResult

class QwenForceAligner:
    """
    Qwen-Force-Aligner 适配器
    
    负责包装底层的强制对齐逻辑，将识别出的文本与原始音频进行对齐，
    补全精确的时间戳信息。
    """

    def __init__(self, config: AlignerConfig):
        """
        初始化对齐引擎
        
        Args:
            config: AlignerConfig 实例，包含模型路径和权重配置
        """
        self.config = config
        self.engine = InternalAligner(config)

    def align(
        self, 
        audio: np.ndarray, 
        text: str, 
        language: str = "Chinese",
        offset_sec: float = 0.0
    ) -> ForcedAlignResult:
        """
        执行强制对齐
        
        Args:
            audio: 原始音频数据 (float32, 16kHz)
            text: ASR 识别出的文本内容
            language: 文本语种
            offset_sec: 时间偏移量（用于叠加当前分片的起始时间）
            
        Returns:
            ForcedAlignResult 包含 items (分词级时间戳) 和性能统计
        """
        if not text:
            return None
            
        return self.engine.align(
            audio=audio, 
            text=text, 
            language=language, 
            offset_sec=offset_sec
        )

    def cleanup(self):
        """释放资源"""
        if hasattr(self.engine, 'ctx'):
            del self.engine.ctx
        if hasattr(self.engine, 'model'):
            del self.engine.model
