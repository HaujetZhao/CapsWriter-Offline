"""
FunASR-GGUF 数据类型定义

包含所有用于 ASR 推理的数据类，使用 dataclass 提供类型安全和清晰的结构。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import numpy as np


# ==================== 识别结果相关 ====================

@dataclass
class RecognitionResult:
    """
    语音识别结果（兼容 sherpa-onnx API）

    Attributes:
        text: 识别文本
        timestamps: 字符级时间戳（秒）
        tokens: 字符/词元列表
    """
    text: str = ""
    timestamps: List[float] = field(default_factory=list)
    tokens: List[str] = field(default_factory=list)


@dataclass
class RecognitionStream:
    """
    识别流对象（兼容 sherpa-onnx API）

    用于承载音频数据和识别结果

    Attributes:
        sample_rate: 音频采样率
        audio_data: 音频数据 (numpy array, float32)
        _result: 内部识别结果
    """
    sample_rate: int = 16000
    audio_data: Optional[np.ndarray] = None
    _result: Optional[RecognitionResult] = field(default=None, init=False, repr=False)

    def accept_waveform(self, sample_rate: int, audio: np.ndarray):
        """
        接受音频数据（兼容 sherpa-onnx API）

        Args:
            sample_rate: 采样率
            audio: 音频数据 (numpy array, float32)
        """
        self.sample_rate = sample_rate
        self.audio_data = audio.astype(np.float32)

    @property
    def result(self) -> RecognitionResult:
        """获取识别结果（兼容 sherpa-onnx API）"""
        if self._result is None:
            self._result = RecognitionResult()
        return self._result

    def set_result(self, text: str, timestamps: List[float] = None, tokens: List[str] = None):
        """设置识别结果（内部使用）"""
        self._result = RecognitionResult(
            text=text,
            timestamps=timestamps or [],
            tokens=tokens or []
        )


@dataclass
class Timings:
    """
    各阶段耗时统计（秒）

    Attributes:
        encode: 音频编码耗时
        ctc: CTC 解码耗时
        prepare: Prompt 准备耗时
        inject: LLM embeddings 注入耗时
        llm_generate: LLM 文本生成耗时
        align: 时间戳对齐耗时
        total: 总耗时
    """
    encode: float = 0.0
    ctc: float = 0.0
    prepare: float = 0.0
    inject: float = 0.0
    llm_generate: float = 0.0
    align: float = 0.0
    total: float = 0.0


@dataclass
class TranscriptionResult:
    """
    完整的转录结果

    Attributes:
        text: 识别文本
        segments: 带时间戳的分段列表
        ctc_text: CTC 识别结果
        hotwords: 检测到的热词列表
        timings: 各阶段耗时统计
    """
    text: str = ""
    segments: List[Dict[str, Any]] = field(default_factory=list)
    ctc_text: str = ""
    hotwords: List[str] = field(default_factory=list)
    timings: Timings = field(default_factory=Timings)


# ==================== 引擎配置相关 ====================

@dataclass
class ASREngineConfig:
    """
    ASR 引擎配置参数

    Attributes:
        encoder_onnx_path: Encoder ONNX 模型路径
        ctc_onnx_path: CTC ONNX 模型路径
        decoder_gguf_path: Decoder GGUF 模型路径
        tokens_path: Tokens 文件路径
        hotwords_path: 热词文件路径（可选）
        enable_ctc: 是否启用 CTC
        n_predict: 最大生成 token 数
        n_threads: 线程数（None 表示自动）
        n_threads_batch: 批处理线程数（None 表示自动）
        n_ubatch: llama.cpp 内部物理 batch 大小
        similar_threshold: 热词相似度阈值
        max_hotwords: 召回并发送给 LLM 的最大热词数
        sample_rate: 音频采样率
    """
    encoder_onnx_path: str
    ctc_onnx_path: str
    decoder_gguf_path: str
    tokens_path: str
    hotwords_path: Optional[str] = None
    enable_ctc: bool = True
    n_predict: int = 512
    n_threads: Optional[int] = None
    n_threads_batch: Optional[int] = None
    n_ubatch: int = 512
    similar_threshold: float = 0.6
    max_hotwords: int = 10
    sample_rate: int = 16000
    dml_enable: bool = True
    vulkan_enable: bool = True
    vulkan_force_fp32: bool = False


# ==================== CTC 结果相关 ====================

@dataclass
class CTCResult:
    """
    CTC 解码结果

    Attributes:
        text: 识别的字符/词
        start: 起始时间（秒）
        end: 结束时间（秒）
        score: 置信度分数
    """
    text: str
    start: float
    end: float
    score: float = 1.0


# ==================== 统计信息相关 ====================

@dataclass
class Statistics:
    """
    推理统计信息

    Attributes:
        audio_duration: 音频时长（秒）
        n_input_tokens: 输入 token 数
        n_prefix_tokens: Prefix token 数
        n_audio_tokens: Audio embedding token 数
        n_suffix_tokens: Suffix token 数
        n_generated_tokens: 生成 token 数
        tps_in: 输入 tokens/s
        tps_out: 输出 tokens/s
    """
    audio_duration: float = 0.0
    n_input_tokens: int = 0
    n_prefix_tokens: int = 0
    n_audio_tokens: int = 0
    n_suffix_tokens: int = 0
    n_generated_tokens: int = 0
    tps_in: float = 0.0
    tps_out: float = 0.0

    def __str__(self) -> str:
        """格式化输出统计信息"""
        return (
            f"  音频长度: {self.audio_duration:6.2f}s\n"
            f"  Decoder输入: {self.tps_in:6.0f} tokens/s "
            f"(总: {self.n_input_tokens}, prefix:{self.n_prefix_tokens}, "
            f"audio:{self.n_audio_tokens}, suffix:{self.n_suffix_tokens})\n"
            f"  Decoder输出: {self.tps_out:6.0f} tokens/s (总: {self.n_generated_tokens})"
        )


@dataclass
class DecodeResult:
    """
    解码结果（内部使用，用于 decode_stream 返回完整结果）

    Attributes:
        text: 识别文本
        ctc_results: CTC 解码结果列表
        aligned: 时间戳对齐结果
        audio_embd: 音频 embeddings
        n_prefix: Prefix token 数
        n_suffix: Suffix token 数
        n_gen: 生成 token 数
        timings: 各阶段耗时
        hotwords: 热词列表
    """
    text: str = ""
    ctc_results: List = field(default_factory=list)
    aligned: List[Dict[str, Any]] = field(default_factory=list)
    audio_embd: Optional[np.ndarray] = None
    n_prefix: int = 0
    n_suffix: int = 0
    n_gen: int = 0
    timings: Timings = field(default_factory=Timings)
    hotwords: List[str] = field(default_factory=list)


# ==================== 导出列表 ====================

__all__ = [
    # 识别结果
    'RecognitionResult',
    'RecognitionStream',
    'TranscriptionResult',
    'DecodeResult',

    # 配置
    'ASREngineConfig',

    # 计时
    'Timings',

    # CTC
    'CTCResult',

    # 统计
    'Statistics',
]
