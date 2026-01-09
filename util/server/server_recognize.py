import re
import time

import numpy as np 

from util.server.server_cosmic import console
from config import ServerConfig as Config
from util.server.server_classes import Task, Result
from util.tools.chinese_itn import chinese_to_num
from util.tools.format_tools import adjust_space
from rich import inspect


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


def recognize(recognizer, punc_model, task: Task):

    # inspect({key:value for key, value in task.__dict__.items() if not key.startswith('_') and key != 'data'})
    # todo 清空遗存的任务结果

    # 确保结果容器存在
    if task.task_id not in results:
        results[task.task_id] = Result(task.task_id, task.socket_id, task.source)

    # 取出结果容器
    result = results[task.task_id]

    # 片段预处理
    samples = np.frombuffer(task.data, dtype=np.float32)
    duration = len(samples) / task.samplerate
    result.duration += duration - task.overlap
    if task.is_final:
        result.duration += task.overlap

    # 识别片段
    stream = recognizer.create_stream()
    stream.accept_waveform(task.samplerate, samples)
    recognizer.decode_stream(stream)

    # 记录识别时间
    result.time_start = task.time_start
    result.time_submit = task.time_submit
    result.time_complete = time.time()

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

    except (UnicodeDecodeError, UnicodeError) as e:
        # 打印调试信息
        console.print(f'\n[red]编码错误: {e}')
        console.print('\n[yellow]完整 stream.result 对象:')
        inspect(stream.result)
        console.print()
        # 出错时使用空列表，避免程序崩溃
        new_tokens = []
        new_timestamps = []

    # 最后与先前的结果合并
    # 如果前一个片段的最后 token 是标点符号，则去掉它
    if result.tokens:
        # 常见的中文和英文标点符号
        punctuation = '，。！？；：、、「」『』（）《》【》[]{}\',.!?;:"\''
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
        return result

    # 调整文本格式
    result.text = format_text(text, punc_model)

    # 若最后一个片段完成识别，从字典摘取任务
    result = results.pop(task.task_id)
    result.is_final = True

    return result
