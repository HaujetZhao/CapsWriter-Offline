"""
FunASR-GGUF: 混合 ASR 推理引擎

使用 ONNX Runtime (encoder/CTC) + llama.cpp (GGUF decoder) 进行语音识别

API 兼容 sherpa-onnx，可直接替换使用。
"""

import sys
from util import get_logger

# 统一使用通过 util 获取的 'server' logger
logger = get_logger('server')


# ==================== 导入主要组件 ====================

from .asr_engine import (
    FunASREngine,
    create_asr_engine,
)
from .nano_dataclass import (
    RecognitionResult,
    RecognitionStream,
    TranscriptionResult,
    DecodeResult,
    Timings,
    ASREngineConfig,
    Statistics,
)

__all__ = [
    # 日志配置
    'logger',
    'setup_logging',

    # 引擎
    'FunASREngine',
    'create_asr_engine',

    # 结果类型
    'RecognitionResult',
    'RecognitionStream',
    'TranscriptionResult',
    'DecodeResult',

    # 配置和统计
    'Timings',
    'ASREngineConfig',
    'Statistics',
]
