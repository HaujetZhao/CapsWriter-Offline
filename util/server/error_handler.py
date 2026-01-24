# coding: utf-8
"""
错误处理模块

提供识别过程中的错误处理和调试数据保存功能。
"""

import pickle
from pathlib import Path
from datetime import datetime

from util.server.server_cosmic import console
from . import logger



def save_error_audio(samples, task_id: str, samplerate: int) -> None:
    """
    将识别出错时的原始音频 samples 保存为 pkl 文件到 logs 文件夹
    
    用于调试解码失败时的原始音频。
    
    Args:
        samples: 原始音频数据 (numpy array)
        task_id: 任务ID
        samplerate: 采样率
    """
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = log_dir / f"decode_error_audio_{timestamp}_{samplerate}Hz_{task_id[:8]}.pkl"
        
        with open(filename, 'wb') as f:
            pickle.dump(samples, f)
        
        logger.info(f"已保存错误现场音频到: {filename}")
        console.print(f'[yellow]已保存错误现场音频到: {filename}')
        
    except Exception as save_error:
        logger.error(f"保存错误音频失败: {save_error}", exc_info=True)
        console.print(f'[yellow]保存错误音频失败: {save_error}')
