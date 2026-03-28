"""
FunASR-GGUF: 混合 ASR 推理引擎

使用 ONNX Runtime (encoder/CTC) + llama.cpp (GGUF decoder) 进行语音识别

API 兼容 sherpa-onnx，可直接替换使用。
"""

import logging
import sys
import os

# 获取项目根目录 (适配打包环境)
if getattr(sys, 'frozen', False):
    # 打包环境：sys.executable 位于 dist/Project/ 根目录
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    # 源码环境：__file__ 位于 root/qwen_asr_gguf/__init__.py
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

default_log_file = os.path.join(ROOT_DIR, "logs", "latest.log")

def setup_logging(level: int = logging.WARNING, log_file: str = default_log_file):
    """
    配置全局日志

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件名

    Returns:
        配置好的 logger 实例
    """
    # 获取根 logger
    root_logger = logging.getLogger('qwen_asr_gguf')
    root_logger.setLevel(level)  # 接收所有级别的日志
    root_logger.handlers.clear()  # 清除已有处理器


    # 文件处理器
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level) # 文件通常记录更详细的信息
        file_formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    return root_logger


# 统一使用通过 util 获取的 'server' logger
try:
    from util import get_logger
    logger = get_logger('server')
except ImportError:
    logger = setup_logging(level=logging.INFO)


from .asr_engine import (
    QwenASREngine,
    create_asr_engine,
)

from .inference.schema import (
    ASREngineConfig,
)

__all__ = [
    'logger',
    'setup_logging',
    'QwenASREngine',
    'create_asr_engine',
    'ASREngineConfig',
]

