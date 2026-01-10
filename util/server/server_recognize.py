import re
import time
import pickle
from pathlib import Path
from datetime import datetime

import numpy as np

from util.server.server_cosmic import console
from config import ServerConfig as Config
from util.server.server_classes import Task, Result
from util.tools.chinese_itn import chinese_to_num
from util.tools.format_tools import adjust_space
from util.logger import get_logger
from rich import inspect

# 获取日志记录器
logger = get_logger('server')

results = {}


def format_text(text, punc_model):
    if Config.format_spell:
        text = adjust_space(text)       # 调空格
    if punc_model and text:
        text = punc_model.add_punctuation(text)  # 加标点
    if Config.format_num:
        text = chinese_to_num(text)     # 转数字
    if Config.format_spell:
        text = adjust_space(text)       # 调空格
    return text


def merge_by_text(prev_text: str, new_text: str, overlap_chars: int = 20) -> str:
    """
    基于文本重叠进行拼接（不依赖时间戳）
    
    通过在 prev_text 末尾和 new_text 开头寻找最长公共子串来去重拼接。
    
    Args:
        prev_text: 之前累积的文本
        new_text: 新识别的文本
        overlap_chars: 在末尾/开头查找重叠的字符数
        
    Returns:
        合并后的文本
    """
    if not prev_text:
        return new_text
    if not new_text:
        return prev_text
    
    # 取 prev_text 末尾 N 个字符
    tail = prev_text[-overlap_chars:] if len(prev_text) >= overlap_chars else prev_text
    
    # 在 new_text 开头查找匹配（从长到短）
    for match_len in range(min(len(tail), len(new_text)), 0, -1):
        if tail[-match_len:] == new_text[:match_len]:
            return prev_text + new_text[match_len:]
    
    # 未找到重叠，直接拼接
    return prev_text + new_text


def save_error_pickle(stream_result, task_id: str, error: Exception) -> None:
    """
    将出错的 stream.result 保存为 pickle 文件到 log 文件夹
    
    Args:
        stream_result: sherpa-onnx 的识别结果对象
        task_id: 任务ID
        error: 发生的错误
    """
    try:
        log_dir = Path("log")
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = log_dir / f"decode_error_{timestamp}_{task_id[:8]}.pkl"
        
        # 保存相关信息
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
        console.print(f'[red]保存错误 pickle 失败: {save_error}')


def recognize(recognizer, punc_model, task: Task):

    # inspect({key:value for key, value in task.__dict__.items() if not key.startswith('_') and key != 'data'})
    # todo 清空遗存的任务结果

    try:
        # 确保结果容器存在
        if task.task_id not in results:
            results[task.task_id] = Result(task.task_id, task.socket_id, task.source)
            logger.debug(f"创建新任务结果容器，任务ID: {task.task_id}")

        # 取出结果容器
        result = results[task.task_id]

        # 片段预处理
        samples = np.frombuffer(task.data, dtype=np.float32)
        duration = len(samples) / task.samplerate
        result.duration += duration - task.overlap
        if task.is_final:
            result.duration += task.overlap

        logger.debug(f"识别任务 {task.task_id}: 音频时长 {duration:.2f}s, 采样率 {task.samplerate}")

        # 识别片段
        stream = recognizer.create_stream()
        stream.accept_waveform(task.samplerate, samples)
        recognizer.decode_stream(stream)

        # 记录识别时间
        result.time_start = task.time_start
        result.time_submit = task.time_submit
        result.time_complete = time.time()

        # ========== 文本拼接（不依赖时间戳）==========
        # 获取片段的原始文本（用于 text_simple）
        try:
            segment_text = stream.result.text
            # 清理文本：去除 @@ 标记和多余空格
            segment_text = segment_text.replace('@@', '').strip()
            segment_text = re.sub(r'\s+', ' ', segment_text)
            
            # 基于文本重叠进行拼接
            result.text_simple = merge_by_text(result.text_simple, segment_text)
            logger.debug(f"文本拼接完成，当前长度: {len(result.text_simple)}")
            
        except Exception as e:
            logger.warning(f"文本拼接失败: {e}")
            # 文本拼接失败不影响主流程

        # ========== 时间戳拼接（用于字幕生成）==========
        # 先粗去重，依据：字级时间戳
        m = n = len(stream.result.timestamps)
        for i, timestamp in enumerate(stream.result.timestamps, start=0):
            if timestamp > task.overlap / 2:
                m = i
                break
        for i, timestamp in enumerate(stream.result.timestamps, start=1):
            n = i
            if timestamp > duration - task.overlap / 2:
                break
        if not result.timestamps:
            m = 0
        if task.is_final:
            n = len(stream.result.timestamps)

        # 安全处理 tokens，过滤可能的无效 UTF-8 编码
        new_tokens = []
        new_timestamps = []
        try:
            # 先获取切片的 tokens 和 timestamps
            sliced_tokens = stream.result.tokens[m:n]
            sliced_timestamps = stream.result.timestamps[m:n]

            # 再细去重，依据：在端点是否有重复的字
            if result.tokens and result.tokens[-2:] == sliced_tokens[:2]:
                sliced_tokens = sliced_tokens[2:]
                sliced_timestamps = sliced_timestamps[2:]
            elif result.tokens and result.tokens[-1:] == sliced_tokens[:1]:
                sliced_tokens = sliced_tokens[1:]
                sliced_timestamps = sliced_timestamps[1:]

            # 处理 tokens
            for token in sliced_tokens:
                # 确保 token 是有效的字符串
                if isinstance(token, bytes):
                    token = token.decode('utf-8', errors='ignore')
                new_tokens.append(token)

            # 处理 timestamps
            new_timestamps = [t + task.offset for t in sliced_timestamps]

            logger.debug(f"识别得到 {len(new_tokens)} 个 tokens")

        except (UnicodeDecodeError, UnicodeError) as e:
            # 打印调试信息
            console.print(f'\n[red]编码错误: {e}')
            console.print('\n[yellow]完整 stream.result 对象:')
            inspect(stream.result)
            console.print()
            logger.error(f"Token 编码错误，任务ID {task.task_id}: {e}")
            
            # 保存错误数据到 pickle
            save_error_pickle(stream.result, task.task_id, e)
            
            # 出错时使用空列表，避免程序崩溃
            new_tokens = []
            new_timestamps = []

        # 最后与先前的结果合并
        # 如果前一个片段的最后 token 是标点符号，则去掉它
        if result.tokens:
            # 常见的中文和英文标点符号
            punctuation = r'，。！？；：、「」『』（）《》【】[]{},.!?;:"' + "'"
            # 检查最后一个 token 是否是标点
            if result.tokens[-1] in punctuation:
                result.tokens = result.tokens[:-1]
                if result.timestamps:
                    result.timestamps = result.timestamps[:-1]

        result.timestamps += new_timestamps
        result.tokens += new_tokens

        # token 合并为文本
        text = ' '.join(result.tokens).replace('@@ ', '')
        text = re.sub('([^a-zA-Z0-9]) (?![a-zA-Z0-9])', r'\1', text)

        result.text = text

        if not task.is_final:
            logger.debug(f"中间结果，任务ID {task.task_id}: {text[:50]}...")
            return result

        # 调整文本格式
        result.text = format_text(text, punc_model)
        result.text_simple = format_text(result.text_simple, punc_model)

        # 若最后一个片段完成识别，从字典摘取任务
        result = results.pop(task.task_id)
        result.is_final = True

        logger.info(f"识别完成，任务ID {task.task_id}: {result.text[:100]}{'...' if len(result.text) > 100 else ''}")
        logger.debug(f"识别耗时: {result.time_complete - task.time_submit:.3f}s")

        return result

    except Exception as e:
        logger.error(f"识别过程发生错误，任务ID {task.task_id}: {e}", exc_info=True)
        raise
