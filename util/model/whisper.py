import numpy as np
if not hasattr(np, 'complex'):
    np.complex = complex
import librosa
import torch
import whisper
import signal
from platform import system
from queue import Queue
import soundfile as sf
from config import ServerConfig as Config, ParaformerArgs, ModelPaths
from util.empty_working_set import empty_current_working_set
from util.server_cosmic import console
from util.server_recognize import results, format_text, recognize

import re
import time
import numpy as np
from util.server_classes import Task, Result

# 关闭 jieba 的 debug
def disable_jieba_debug():
    import jieba
    import logging
    jieba.setLogLevel(logging.INFO)


def init_recognizer_with_whisper(queue_in: Queue, queue_out: Queue, sockets_id):
    # Ctrl-C 退出
    signal.signal(signal.SIGINT, lambda signum, frame: exit())

    # 导入模块
    with console.status("载入模块中…", spinner="bouncingBall", spinner_style="yellow"):
        disable_jieba_debug()
    console.print('[green4]模块加载完成', end='\n\n')

    # 载入Whisper模型
    console.print('[yellow]Whisper语音模型载入中', end='\r')
    t1 = time.time()

    # 加载Whisper模型，支持不同大小的模型（tiny, base, small, medium, large）
    ss = "cuda" if torch.cuda.is_available() else "cpu"
    import sherpa_onnx
    from funasr_onnx import CT_Transformer
    disable_jieba_debug()
    recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
        **{key: value for key, value in ParaformerArgs.__dict__.items() if not key.startswith('_')}
    )

    # 载入标点模型
    punc_model = None
    if Config.format_punc:
        punc_model = CT_Transformer(ModelPaths.punc_model_dir, quantize=True)
    console.print(f'[green4]Whisper语音模型载入完成  use {ss}', end='\n\n')

    console.print(f'模型加载耗时 {time.time() - t1 :.2f}s', end='\n\n')

    # 清空物理内存工作集
    if system() == 'Windows':
        empty_current_working_set()

    queue_out.put(True)  # 通知主进程加载完了

    while True:
        # 从队列中获取任务消息
        # 阻塞最多1秒，便于中断退出
        try:
            task = queue_in.get(timeout=1)
        except:
            continue

        if task.socket_id not in sockets_id:    # 检查任务所属的连接是否存活
            continue

        result = recognize(recognizer, punc_model, task)   # 执行识别
        queue_out.put(result)


def recognize_with_whisper(recognizer, punc_model, task: Task):
    # 检查结果容器是否存在
    if task.task_id not in results:
        results[task.task_id] = Result(task.task_id, task.socket_id, task.source)

    # 获取结果容器
    result = results[task.task_id]

    # 处理音频片段
    samples = np.frombuffer(task.data, dtype=np.float32)
    duration = len(samples) / task.samplerate
    result.duration += duration - task.overlap
    if task.is_final:
        result.duration += task.overlap

    # 执行语音转录
    audio_path = "temp_audio.wav"  # 暂时将片段保存为音频文件
    save_audio(samples, task.samplerate, audio_path)

    # 使用 Whisper 进行语音转录
    result_text = transcribe_with_whisper(recognizer, audio_path)
    result.text = result_text

    # 更新时间戳
    result.time_start = task.time_start
    result.time_submit = task.time_submit
    result.time_complete = time.time()

    # 如果不是最终任务，直接返回
    if not task.is_final:
        return result

    # 标记任务为最终任务
    result.is_final = True

    # 从结果字典中摘取任务
    result = results.pop(task.task_id)

    return result


def save_audio(samples_float32, orig_samplerate, file_path, target_samplerate=16000, channels=1):
    """
    采样流保存为任意格式音频，默认重采样16kHz，转单声道
    file_path 后缀决定格式（wav, flac, mp3等）
    """
    # 多声道转单声道（取第一个声道）
    if samples_float32.ndim > 1:
        samples_float32 = samples_float32[:, 0]

    # 重采样
    if orig_samplerate != target_samplerate:
        samples_float32 = librosa.resample(samples_float32, orig_sr=orig_samplerate, target_sr=target_samplerate)

    # 限幅
    samples_float32 = np.clip(samples_float32, -1.0, 1.0)

    # 保存音频，subtype='PCM_16' 表示16-bit编码，支持 wav、flac 等
    sf.write(file_path, samples_float32, target_samplerate, subtype='PCM_16')


def transcribe_with_whisper(model, audio_path):
    """
    使用 Whisper 模型进行音频转录
    """
    # 进行转录
    result = model.transcribe(audio_path, language="zh")
    print(result)
    # 获取转录文本
    transcribed_text = result['text']

    return transcribed_text
