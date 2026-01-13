# coding: utf-8
"""
错误处理模块

提供识别过程中的错误处理和调试数据保存功能。
"""

import pickle
from pathlib import Path
from datetime import datetime

from util.server.server_cosmic import console
from util.logger import get_logger

logger = get_logger('server')


def save_error_pickle(stream_result, task_id: str, error: Exception) -> None:
    """
    将出错的 stream.result 保存为 pickle 文件到 logs 文件夹
    
    用于调试 UTF-8 解码错误等问题。
    
    Args:
        stream_result: sherpa-onnx 的识别结果对象
        task_id: 任务ID
        error: 发生的错误
    """
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = log_dir / f"decode_error_{timestamp}_{task_id[:8]}.pkl"
        
        error_data = {
            'task_id': task_id,
            'error': str(error),
            'error_type': type(error).__name__,
            'stream_result': stream_result,
            'timestamp': timestamp,
        }
        
        with open(filename, 'wb') as f:
            pickle.dump(error_data, f)
        
        logger.info(f"已保存错误数据到: {filename}")
        console.print(f'[yellow]已保存错误数据到: {filename}')
        
    except Exception as save_error:
        logger.error(f"保存错误 pickle 失败: {save_error}", exc_info=True)
        console.print(f'[yellow]保存错误 pickle 失败: {save_error}')
