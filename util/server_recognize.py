import re
import time

import numpy as np 

from util.server_cosmic import console, Cosmic
from util.server_classes import Task, Result
from util.chinese_itn import chinese_to_num
from util.format_tools import adjust_space
from rich import inspect


results = {}


def recognize(recognizer, punc_model, task: Task):

    # inspect({key:value for key, value in task.__dict__.items() if not key.startswith('_') and key != 'data'})
    # todo 清空遗存的任务结果

    # 确保结果容器存在
    if task.task_id not in results:
        results[task.task_id] = Result(task.task_id, task.socket_id)

    # 取出结果容器
    result = results[task.task_id]

    # 片段预处理
    samples = np.frombuffer(task.data, dtype=np.float32)
    duration = len(samples) / task.samplerate
    result.duration += duration

    # 识别片段
    stream = recognizer.create_stream()
    stream.accept_waveform(task.samplerate, samples)
    recognizer.decode_stream(stream)

    # 记录识别时间
    result.time_start = task.time_start
    result.time_submit = task.time_submit
    result.time_complete = time.time()

    # 先粗去重
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

    # 再细去重
    if result.tokens and result.tokens[-2:] == stream.result.tokens[m:n][:2]:
        m += 2
    elif result.tokens and result.tokens[-1:] == stream.result.tokens[m:n][:1]:
        m += 1

    # 最后与先前的结果合并
    result.timestamps += [t + task.offset for t in stream.result.timestamps[m:n]]
    result.tokens += [token for token in stream.result.tokens[m:n]]

    # token 合并为文本
    text = ' '.join(result.tokens).replace('@@ ', '')
    text = re.sub('([^a-zA-Z0-9]) (?![a-zA-Z0-9])', r'\1', text)

    # 调整文本格式
    text = adjust_space(text)       # 调空格
    if punc_model:
        text = punc_model(text)[0]  # 加标点
    text = chinese_to_num(text)     # 转数字
    text = adjust_space(text)       # 调空格

    result.text = text

    if not task.is_final:
        return result

    # 若最后一个片段完成识别，从字典摘取任务
    result = results.pop(task.task_id)
    result.is_final = True

    return result
