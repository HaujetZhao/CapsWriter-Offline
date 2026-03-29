"""
SenseVoice ONNX 数据类型定义

包含用于 SenseVoice 推理的数据类，提供类型安全和清晰的结构。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import numpy as np
from pathlib import Path


# ==================== 识别结果相关 ====================

@dataclass
class RecognitionResult:
    """
    单个识别单元结果 (字符或 Token 块)

    Attributes:
        text: 识别文本 (字符或块)
        start: 起始时间（秒）
        is_hotword: 是否为命中的热词
    """
    text: str
    start: float
    is_hotword: bool = False


@dataclass
class RecognitionStream:
    """
    识别流对象

    用于承载音频数据和识别结果 (兼容风格设计)

    Attributes:
        sample_rate: 音频采样率
        audio_data: 音频数据 (numpy array, float32)
        results: 识别结果列表
    """
    sample_rate: int = 16000
    audio_data: Optional[np.ndarray] = None
    results: List[RecognitionResult] = field(default_factory=list)

    def accept_waveform(self, sample_rate: int, audio: np.ndarray):
        """接受音频数据"""
        self.sample_rate = sample_rate
        # 统一转为 float32
        if audio.dtype != np.float32:
            if audio.dtype == np.int16:
                audio = audio.astype(np.float32) / 32768.0
            else:
                audio = audio.astype(np.float32)
        self.audio_data = audio

    @property
    def text(self) -> str:
        """获取合并后的完整文本"""
        return "".join([r.text for r in self.results])


@dataclass
class Timings:
    """
    各阶段耗时统计（秒）

    Attributes:
        frontend: 特征提取耗时
        encoder: 编码器推理耗时
        decoder: 解码器 (CTC) 推理耗时
        radar: 热词雷达扫描耗时
        integrate: 结果整合耗时
        total: 总耗时
    """
    frontend: float = 0.0
    encoder: float = 0.0
    decoder: float = 0.0
    radar: float = 0.0
    integrate: float = 0.0
    total: float = 0.0


@dataclass
class TranscriptionResult:
    """
    完整的转录结果包装

    Attributes:
        text: 最终识别文本
        results: 详细的 RecognitionResult 列表
        hotwords: 识别到的热词列表
        timings: 耗时统计
    """
    text: str = ""
    results: List[RecognitionResult] = field(default_factory=list)
    hotwords: List[str] = field(default_factory=list)
    timings: Timings = field(default_factory=Timings)


# ==================== 引擎配置相关 ====================

@dataclass
class ASREngineConfig:
    """
    ASR 引擎配置参数

    Attributes:
        encoder_path: 编码器模型路径 (.onnx)
        decoder_path: 解码器模型路径 (.onnx)
        tokenizer_path: 分词器模型路径 (.model)
        onnx_provider: 推理后端 (CPU, CUDA, DML, TensorRT)
        hotwords: 初始热词字符串列表
        top_k: 热词搜索 Top-K 深度
        itn: 是否启用反向文本规范化
        dml_pad_to: DML 填充时长 (秒)
    """
    encoder_path: str
    decoder_path: str
    tokenizer_path: str
    onnx_provider: str = "cpu"
    hotwords: Optional[List[str]] = None
    top_k: int = 10
    itn: bool = True
    dml_pad_to: int = 30


# ==================== 导出列表 ====================

__all__ = [
    'RecognitionResult',
    'RecognitionStream',
    'TranscriptionResult',
    'ASREngineConfig',
    'Timings',
]
