# coding: utf-8
"""
语音识别处理模块

处理音频片段的识别、去重和拼接。支持两种拼接策略：
1. text (简单拼接): 基于文本重叠匹配，不依赖时间戳
2. text_accu (精确拼接): 基于时间戳去重，用于字幕生成
"""

import re
import time

import numpy as np

from util.server.server_cosmic import console
from config_server import ServerConfig as Config
from util.server.server_classes import Task, Result
from util.tools.chinese_itn import chinese_to_num
from util.tools.format_tools import adjust_space
from . import logger
from rich import inspect

# 导入拆分出去的模块
from util.server.text_merge import (
    merge_by_text,
    merge_tokens_by_sequence_matcher,
    process_tokens_safely,
    tokens_to_text,
    remove_trailing_punctuation,
)
from util.server.error_handler import save_error_audio


# 任务结果缓存（按 task_id 索引）
_results = {}


def format_text(text: str, punc_model) -> str:
    """
    格式化识别文本
    
    Args:
        text: 原始识别文本
        punc_model: 标点模型（可为 None）
        
    Returns:
        格式化后的文本
    """
    if text and Config.format_spell:
        text = adjust_space(text)
    if text and punc_model:
        text = punc_model.add_punctuation(text)
    if text and Config.format_num:
        text = chinese_to_num(text)
    return text


def _process_simple_merge(result: Result, stream_result_text: str) -> None:
    """
    处理简单文本拼接（主要输出，用于语音输入）
    
    Args:
        result: 当前结果对象
        stream_result_text: 当前片段的识别文本
    """
    try:
        # 清理文本：去除 @@ 标记和多余空格
        segment_text = stream_result_text.replace('@@', '').strip()
        segment_text = re.sub(r'\s+', ' ', segment_text)
        
        prev_len = len(result.text)
        result.text = merge_by_text(result.text, segment_text)
        added_chars = len(result.text) - prev_len
        
        logger.debug(
            f"简单拼接: +{added_chars} 字符, "
            f"片段={len(segment_text)}, 总={len(result.text)}"
        )
        
    except Exception as e:
        logger.warning(f"简单文本拼接失败: {e}")


def recognize(recognizer, punc_model, task: Task) -> Result:
    """
    识别单个音频片段并更新结果
    
    这是识别流程的主入口，处理以下步骤：
    1. 解码音频并运行识别
    2. 简单文本拼接（text 字段）
    3. 时间戳拼接（text_accu 字段）
    4. 最终格式化（如果是最后一个片段）
    
    Args:
        recognizer: sherpa-onnx 识别器实例
        punc_model: 标点模型（可为 None）
        task: 识别任务
        
    Returns:
        识别结果
    """
    try:
        # 1. 初始化/获取结果容器
        is_first_segment = task.task_id not in _results
        if is_first_segment:
            _results[task.task_id] = Result(task.task_id, task.socket_id, task.source)
            logger.debug(f"新任务: {task.task_id[:8]}...")
        
        result = _results[task.task_id]

        # 2. 解码音频
        samples = np.frombuffer(task.data, dtype=np.float32)
        duration = len(samples) / task.samplerate
        result.duration += duration - task.overlap
        if task.is_final:
            result.duration += task.overlap

        logger.debug(
            f"识别片段: task={task.task_id[:8]}, duration={duration:.2f}s, "
            f"offset={task.offset:.2f}s, is_final={task.is_final}"
        )

        # 3. 执行识别
        stream = recognizer.create_stream()
        stream.accept_waveform(task.samplerate, samples)
        
        t1 = time.time()
        # 尝试带上 context 参数（自定义 FunASREngine 支持）
        # 如果是原生 sherpa-onnx 引擎，不支持 context，会抛出 TypeError，此时回退到普通调用
        try:
            recognizer.decode_stream(stream, context=task.context)
        except TypeError:
            recognizer.decode_stream(stream)

        # 更新时间戳
        result.time_start = task.time_start
        result.time_submit = task.time_submit
        result.time_complete = time.time()

        # 4. 简单文本拼接
        _process_simple_merge(result, stream.result.text)

        # 5. 时间戳拼接（使用 SequenceMatcher 策略）
        try:
            # 安全处理当前片段的 tokens
            new_tokens = process_tokens_safely(stream.result.tokens)
            new_timestamps = list(stream.result.timestamps)
            
            # 使用 SequenceMatcher 进行精确拼接
            result.tokens, result.timestamps = merge_tokens_by_sequence_matcher(
                prev_tokens=result.tokens,
                prev_timestamps=result.timestamps,
                new_tokens=new_tokens,
                new_timestamps=new_timestamps,
                offset=task.offset,
                overlap=task.overlap,
                is_first_segment=is_first_segment
            )
            
            logger.debug(f"时间戳拼接完成: 总 {len(result.tokens)} tokens")

        except (UnicodeDecodeError, UnicodeError) as e:
            save_error_audio(samples, task.task_id, task.samplerate)
            console.print(f'\n[red]编码错误: {e}')

        # 6. 生成 text_accu
        result.text_accu = tokens_to_text(result.tokens)

        # 如果不是最终结果，直接返回
        if not task.is_final:
            logger.debug(f"中间结果: {result.text[:30]}...")
            return result

        # 8. 格式优化
        result.text = format_text(result.text, punc_model)
        result.text_accu = format_text(result.text_accu, punc_model)
        
        # 如果模型不支持时间戳，用简单拼接结果回退
        if not result.tokens and result.text:
            result.text_accu = result.text
            # 生成粗略的字级时间戳（均匀分布）
            chars = list(result.text_accu.replace(' ', ''))
            if chars and result.duration > 0:
                time_per_char = result.duration / len(chars)
                result.tokens = chars
                result.timestamps = [i * time_per_char for i in range(len(chars))]
                logger.warning(f"模型无时间戳，使用粗略估计: {len(chars)} 字符, {result.duration:.2f}s")
        
        result = _results.pop(task.task_id)
        result.is_final = True
        
        process_time = result.time_complete - task.time_submit
        rtf_value = process_time / result.duration if result.duration > 0 else 0
        logger.info(
            f"识别完成: task={task.task_id[:8]}, "
            f"duration={result.duration:.2f}(s), "
            f"process_time={process_time:.3f}(s), "
            f"RTF={rtf_value:.3f}"
        )
        logger.debug(f"最终文本: {result.text[:100]}...")

        return result

    except Exception as e:
        logger.error(f"识别错误: {e}", exc_info=True)
        raise


def clear_results_by_socket_id(socket_id: str) -> None:
    """
    清理指定 socket_id 关联的所有任务结果缓存
    
    当客户端连接断开时调用，防止内存泄漏。
    """
    global _results
    tasks_to_remove = [
        task_id for task_id, result in _results.items() 
        if result.socket_id == socket_id
    ]
    for task_id in tasks_to_remove:
        _results.pop(task_id, None)
    
    if tasks_to_remove:
        logger.debug(f"已清理断开连接相关的缓存: socket_id={socket_id}, 任务数={len(tasks_to_remove)}")
