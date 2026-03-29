# coding: utf-8
"""
语音识别处理模块

处理音频片段的识别、去重和拼接。支持两种拼接策略：
1. text (简单拼接): 基于文本重叠匹配，不依赖时间戳
2. text_accu (精确拼接): 基于时间戳去重，用于字幕生成
"""

import re
import time



from util.server.context import Context, console
from util.server.schema import Task, Result
from util.server.formatter import TextFormatter
from util.server.audio import process_audio_task
from . import logger
from rich import inspect

# 导入拆分后的算法子包
from util.server.merger import (
    merge_by_text,
    merge_tokens_by_sequence_matcher,
    process_tokens_safely,
    tokens_to_text,
    remove_trailing_punctuation,
)









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


def recognize(recognizer, punc_model, task: Task, aligner=None) -> Result:
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
        # 1. 初始化/获取识别会话
        is_first_segment = task.task_id not in Context.sessions
        session = Context.get_session(task.task_id, task.socket_id, task.source)
        result = session.result
        
        if is_first_segment:
            logger.debug(f"新任务: {task.task_id[:8]}...")

        # 2. 预处理音频并更新时长
        samples = process_audio_task(task, result)
        duration = len(samples) / task.samplerate

        logger.debug(
            f"识别片段: task={task.task_id[:8]}, duration={duration:.2f}s, "
            f"offset={task.offset:.2f}s, is_final={task.is_final}"
        )

        # 3. 执行识别
        stream = recognizer.create_stream()
        stream.accept_waveform(task.samplerate, samples)
        
        t1 = time.time()
        # 执行解码
        recognizer.decode_stream(stream, context=task.context)

        # 更新时间戳
        result.time_start = task.time_start
        result.time_submit = task.time_submit
        result.time_complete = time.time()

        # 4. 简单文本拼接
        _process_simple_merge(result, stream.result.text)

        # 4.5 强制对齐补全时间戳 (针对像 Qwen 这样默认不带时间戳的模型)
        if aligner and stream.result.text:
            try:
                # 执行对齐 (samples 是当前片段的音频)
                align_res = aligner.align(
                    audio=samples, 
                    text=stream.result.text, 
                    offset_sec=0.0 # 这里传 0，因为后续 merge_tokens 会处理 task.offset
                )
                if align_res and align_res.items:
                    stream.result.tokens = [it.text for it in align_res.items]
                    stream.result.timestamps = [it.start_time for it in align_res.items]
                    logger.debug(f"Force Aligner 补全成功: {len(stream.result.tokens)} tokens")
            except Exception as e:
                logger.warning(f"Force Aligner 对齐失败: {e}")

        # 5. 时间戳拼接（使用 SequenceMatcher 策略）
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


        # 6. 生成 text_accu
        result.text_accu = tokens_to_text(result.tokens)

        # 如果不是最终结果，直接返回
        if not task.is_final:
            logger.debug(f"中间结果: {result.text[:30]}...")
            return result

        # 8. 格式优化
        formatter = TextFormatter(punc_model)
        result.text = formatter.format(result.text)
        result.text_accu = formatter.format(result.text_accu)
        
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
        
        if task.is_final:
            Context.sessions.pop(task.task_id, None)
        
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
    """清理指定 socket_id 关联的所有任务结果缓存"""
    count = Context.clear_sessions_by_socket_id(socket_id)
    if count > 0:
        logger.debug(f"已清理断开连接相关的缓存: socket_id={socket_id}, 任务数={count}")
