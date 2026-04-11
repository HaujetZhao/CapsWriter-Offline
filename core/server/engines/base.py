# coding: utf-8
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Any
import numpy as np


class EngineCapabilities(Enum):
    """引擎能力声明类型"""
    ASR = auto()            # 基础 ASR 能力
    PUNC = auto()           # 自带标点
    TIMESTAMPS = auto()     # 自带时间戳
    STREAMING = auto()      # 支持真实流式推理
    HOTWORDS = auto()       # 支持动态热词


@dataclass
class RecognitionResult:
    """标准识别结果结构"""
    text: str = ""
    tokens: List[str] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    language: Optional[str] = None
    duration: float = 0.0
    performance: dict = field(default_factory=dict)


class RecognitionStream(ABC):
    """
    标准识别流接口
    有些引擎（如 sherpa-onnx）支持流式，而有些（如基于音频分片的同步引擎）则内部模拟。
    """
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.result = RecognitionResult()

    @abstractmethod
    def accept_waveform(self, sample_rate: int, audio: np.ndarray):
        """塞入音频片"""
        pass


class BaseASREngine(ABC):
    """
    语音识别引擎基类
    
    所有的 ASR 引擎（SenseVoice, Paraformer, Qwen 等）都必须继承此类并实现其接口。
    """

    def __init__(self, config: Any):
        self.config = config

    @property
    @abstractmethod
    def capabilities(self) -> List[EngineCapabilities]:
        """声明引擎具备的能力"""
        pass

    @abstractmethod
    def create_stream(self, hotwords: Optional[str] = None) -> RecognitionStream:
        """创建一个识别流对象"""
        pass

    @abstractmethod
    def decode_stream(
        self, 
        stream: RecognitionStream, 
        context: Optional[str] = None,
        **kwargs
    ):
        """执行推理并更新 stream.result"""
        pass

    def update_hotwords(self, hotwords: List[str]):
        """更新引擎内部的热词表（如果支持）"""
        pass

    @abstractmethod
    def cleanup(self):
        """释放模型资源"""
        pass


class BasePuncEngine(ABC):
    """
    标点引擎基类
    """

    def __init__(self, config: Any):
        self.config = config

    def punctuate(self, text: str) -> str:
        """ 为文本注入或修正标点。默认行为：原样返回。 """
        return text

    def cleanup(self):
        """ 释放资源 """
        pass


class BaseAlignEngine(ABC):
    """
    强制对齐引擎基类
    """

    def __init__(self, config: Any):
        self.config = config

    def align(self, audio: np.ndarray, text: str, **kwargs) -> Any:
        """ 对音频和文本进行强制对齐。默认行为：返回 None。 """
        return None

    def cleanup(self):
        """ 释放资源 """
        pass
