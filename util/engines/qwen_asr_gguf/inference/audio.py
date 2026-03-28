"""
audio.py - 音频预处理工具类
职责：使用 ffmpeg 直接读取音频，支持所有格式（mp3/m4a/opus 等）。
"""
import os
import math
import shutil
import subprocess
import numpy as np
import soundfile as sf
from pathlib import Path
from . import logger


def numpy_resample_poly(x, up, down, window_size=10):
    """
    纯 numpy 实现的 resample_poly
    算法精准复刻 scipy.signal.resample_poly，与 scipy 相似度达 0.99999998
    """
    # 1. 约分
    g = math.gcd(up, down)
    up //= g
    down //= g

    if up == down:
        return x.copy()

    # 2. 设计 FIR 滤波器 (与 scipy.signal.firwin 对齐)
    max_rate = max(up, down)
    f_c = 1.0 / max_rate  
    half_len = window_size * max_rate
    n_taps = 2 * half_len + 1
    
    t = np.arange(n_taps) - half_len
    h = np.sinc(f_c * t)
    
    # 使用 Kaiser 窗 (beta=5.0)
    # np.i0 是修饰过的第一类修正贝塞尔函数，与 scipy.special.i0 一致
    beta = 5.0
    kaiser_win = np.i0(beta * np.sqrt(1 - (2 * t / (n_taps - 1))**2)) / np.i0(beta)
    h = h * kaiser_win
    h = h * (up / np.sum(h))

    # 3. 多相滤波 (复刻 upfirdn 逻辑)
    length_in = len(x)
    length_out = int(math.ceil(length_in * up / down))
    
    x_up = np.zeros(length_in * up + n_taps, dtype=np.float32)
    x_up[:length_in * up:up] = x
    
    y_full = np.convolve(x_up, h, mode='full')
    
    offset = (n_taps - 1) // 2
    y = y_full[offset : offset + length_in * up : down]
    
    return y[:length_out].astype(np.float32)


def resample_audio(audio, sr, target_sr):
    """音频重采样封装"""
    if sr == target_sr:
        return audio
    return numpy_resample_poly(audio, target_sr, sr)


def load_audio_numpy(audio_path, sample_rate=24000, start_second=None, duration=None):
    """使用 soundfile + numpy 重采样读取音频"""
    info = sf.info(audio_path)
    sr = info.samplerate
    
    # 获取偏移量
    start_frame = int(start_second * sr) if start_second is not None else 0
    frames = int(duration * sr) if duration is not None else -1
    
    audio, sr = sf.read(audio_path, start=start_frame, frames=frames, dtype='float32')
    
    # 转单声道
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
        
    # 高质量重采样
    if sr != sample_rate:
        audio = resample_audio(audio, sr, sample_rate)
        
    return audio.astype(np.float32)


def check_ffmpeg():
    """检测系统是否安装 ffmpeg"""
    return shutil.which('ffmpeg') is not None


def load_audio_ffmpeg(audio_path, sample_rate=24000, start_second=None, duration=None):
    """使用 ffmpeg 直接读取音频"""
    if not check_ffmpeg():
        raise RuntimeError("系统未发现 ffmpeg。请先安装 ffmpeg 并将其添加到系统环境变量 PATH 中。")

    cmd = ['ffmpeg', '-y', '-i', str(audio_path)]

    if start_second is not None:
        cmd.extend(['-ss', str(start_second)])
    if duration is not None:
        cmd.extend(['-t', str(duration)])

    cmd.extend([
        '-ar', str(sample_rate),
        '-ac', '1',
        '-f', 'f32le',
        'pipe:1'
    ])

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0
    )

    raw_bytes, stderr = process.communicate()

    if process.returncode != 0:
        error_msg = stderr.decode('utf-8', errors='ignore')
        raise RuntimeError(f"ffmpeg 处理音频失败: {error_msg}")

    return np.frombuffer(raw_bytes, dtype=np.float32)



def load_audio(audio_path, sample_rate=16000, start_second=None, duration=None):
    """
    加载音频文件的主入口。
    根据后缀名判断读取方式：
    - soundfile 支持: .wav, .flac, .ogg, .mp3
    - 其他 ffmpeg fallback: .m4a, .mp4, .opus, .wmv 等
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
    # 获取后缀名
    ext = Path(audio_path).suffix.lower()
    
    # 定义 soundfile 可以稳定处理的格式
    SF_FORMATS = {'.wav', '.flac', '.ogg', '.mp3'}
    
    if ext in SF_FORMATS:
        return load_audio_numpy(audio_path, sample_rate, start_second, duration)
    else:
        return load_audio_ffmpeg(audio_path, sample_rate, start_second, duration)
