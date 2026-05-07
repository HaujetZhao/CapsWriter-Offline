# coding: utf-8
"""
音频预处理模块

负责将原始音轨数据 (bytes) 转换为模型可用的采样数组 (numpy.float32)，
并处理时长累加等与信号处理相关的逻辑。
"""

import numpy as np
from typing import Optional
from core.server.schema import Task, Result


def process_audio_task(task: Task, result: Result) -> Optional[np.ndarray]:
    """
    处理音频片段任务并更新结果中的时长信息
    
    Args:
        task: 识别任务对象
        result: 识别结果对象
        
    Returns:
        samples: 转换后的 numpy 数组 (float32)，空音频时返回 None
    """
    # 1. 转换字节流为 float32 采样数组
    samples = np.frombuffer(task.data, dtype=np.float32)

    # 空音频防御：少于 1600 采样点（约 0.1s @16kHz）直接跳过
    if len(samples) < 1600:
        return None

    # 2. 计算此片段的时长贡献（秒）
    # 公式：片段时长 - 重叠部分。如果是最终片段，重叠部分也计入总时长。
    duration = len(samples) / task.samplerate
    
    # 更新累积时长
    result.duration += duration - task.overlap
    if task.is_final:
        result.duration += task.overlap
        
    return samples
