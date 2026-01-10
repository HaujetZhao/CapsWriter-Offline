# coding: utf-8
"""
服务端数据类模块

定义服务端使用的数据类，包括任务（Task）和结果（Result）。
使用 dataclass 提供类型安全和清晰的数据结构。
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Task:
    """
    语音识别任务
    
    封装发送到识别进程的任务数据，包含音频数据和元信息。
    
    Attributes:
        source: 音频来源 ('mic' 或 'file')
        data: 原始音频数据 (float32, 16kHz, mono)
        offset: 当前片段在整段音频中的时间偏移（秒）
        overlap: 片段重叠时间（秒），用于去重
        task_id: 任务唯一标识
        socket_id: WebSocket 连接标识
        is_final: 是否为音频流的最后一个片段
        time_start: 录音/音频开始时间戳
        time_submit: 任务提交时间戳
        samplerate: 采样率，默认 16000 Hz
    """
    source: str
    data: bytes
    offset: float
    overlap: float
    task_id: str
    socket_id: str
    is_final: bool
    time_start: float
    time_submit: float
    samplerate: int = 16000


@dataclass
class Result:
    """
    语音识别结果
    
    封装识别进程返回的结果数据。
    
    Attributes:
        task_id: 任务唯一标识
        socket_id: WebSocket 连接标识
        source: 音频来源 ('mic' 或 'file')
        duration: 已处理的音频总时长（秒）
        time_start: 录音/音频开始时间戳
        time_submit: 片段提交时间戳
        time_complete: 识别完成时间戳
        tokens: 字级 token 列表
        timestamps: 字级时间戳列表（对应 tokens）
        text: 合并后的文本
        is_final: 是否已完成所有片段识别
    """
    task_id: str
    socket_id: str
    source: str
    
    duration: float = 0.0
    time_start: float = 0.0
    time_submit: float = 0.0
    time_complete: float = 0.0
    
    tokens: List[str] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    text: str = ''
    text_simple: str = ''  # 基于文本拼接的结果（不依赖时间戳）
    is_final: bool = False
