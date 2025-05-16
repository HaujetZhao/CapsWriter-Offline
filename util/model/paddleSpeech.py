import numpy as np
if not hasattr(np, 'complex'):
    np.complex = complex
import paddle
from paddlespeech.cli.asr import ASRExecutor
import time
from platform import system
from config import ServerConfig as Config
from util.empty_working_set import empty_current_working_set
from util.server_init_recognizer import disable_jieba_debug
from util.server_recognize import results
from multiprocessing import Queue
import signal
from util.server_cosmic import console


def init_recognizer_with_paddlespeech(queue_in: Queue, queue_out: Queue, sockets_id):
    # Ctrl-C 退出
    signal.signal(signal.SIGINT, lambda signum, frame: exit())

    # 导入模型
    with console.status("载入模型中…", spinner="bouncingBall", spinner_style="yellow"):
        disable_jieba_debug()
    console.print('[green4]模块加载完成', end='\n\n')

    # 准备 ASR 模型（PaddleSpeech 默认模型）
    console.print('[yellow]PaddleSpeech 语音模型载入中', end='\r')
    t1 = time.time()
    asr = ASRExecutor()
    console.print(f'[green4]PaddleSpeech 语音模型载入完成', end='\n\n')

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

        if task.socket_id not in sockets_id:  # 检查任务所属的连接是否存活
            continue

        # 执行PaddleSpeech语音识别
        audio_path = "temp_audio.wav"  # 暂时将片段保存为音频文件
        save_audio_to_file(task.data, task.samplerate, audio_path)

        # 使用 PaddleSpeech 进行语音转录
        result_text = transcribe_with_paddlespeech(asr, audio_path)
        result = results.get(task.task_id, None)
        if result:
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


def save_audio_to_file(samples, samplerate, file_path):
    """
    将音频片段保存为文件，用于传递给 PaddleSpeech 进行转录
    """
    import wave

    # 将音频片段保存为 WAV 文件
    with wave.open(file_path, 'wb') as f:
        f.setnchannels(1)  # 单声道
        f.setsampwidth(2)  # 16 位宽度
        f.setframerate(samplerate)
        f.writeframes(samples.tobytes())


def transcribe_with_paddlespeech(asr, audio_path):
    """
    使用 PaddleSpeech 模型进行音频转录
    """
    # 使用 PaddleSpeech 进行语音转录
    result = asr(subspeech_file=audio_path)

    # 获取转录文本
    transcribed_text = result['text']

    return transcribed_text
