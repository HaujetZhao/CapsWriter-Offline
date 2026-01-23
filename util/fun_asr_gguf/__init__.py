"""
FunASR-GGUF: 混合 ASR 推理引擎

使用 ONNX Runtime (encoder/CTC) + llama.cpp (GGUF decoder) 进行语音识别

API 兼容 sherpa-onnx，可直接替换使用。
"""

import logging
import sys

# ==================== 日志配置 ====================

def setup_logging(level: int = logging.WARNING):
    """
    配置全局日志

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        配置好的 logger 实例
    """
    # 获取根 logger
    root_logger = logging.getLogger('fun_asr_gguf')
    root_logger.setLevel(logging.WARNING)  # 接收所有级别的日志
    root_logger.handlers.clear()  # 清除已有处理器

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    return root_logger


# 初始化默认日志配置（默认 WARNING 级别，只显示警告和错误）
logger = setup_logging(level=logging.WARNING)


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
