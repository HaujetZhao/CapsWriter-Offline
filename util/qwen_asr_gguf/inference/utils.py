# coding=utf-8
import numpy as np
from typing import List, Optional

SUPPORTED_LANGUAGES: List[str] = [
    "Chinese",
    "English",
    "Cantonese",
    "Arabic",
    "German",
    "French",
    "Spanish",
    "Portuguese",
    "Indonesian",
    "Italian",
    "Korean",
    "Russian",
    "Thai",
    "Vietnamese",
    "Japanese",
    "Turkish",
    "Hindi",
    "Malay",
    "Dutch",
    "Swedish",
    "Danish",
    "Finnish",
    "Polish",
    "Czech",
    "Filipino",
    "Persian",
    "Greek",
    "Romanian",
    "Hungarian",
    "Macedonian"
]

def normalize_language_name(language: str) -> str:
    """
    将语言名称归一化为 Qwen3-ASR 使用的标准格式：
    首字母大写，其余小写（例如 'cHINese' -> 'Chinese'）。
    """
    if language is None:
        raise ValueError("language is None")
    s = str(language).strip()
    if not s:
        raise ValueError("language is empty")
    return s[:1].upper() + s[1:].lower()

def validate_language(language: str) -> None:
    """
    验证语言是否在支持列表中。
    """
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {language}. Supported: {SUPPORTED_LANGUAGES}")

def load_audio(audio_path, sample_rate=16000, start_second=None, duration=None):
    """加载音频文件并转换为 16kHz PCM，支持按需加载指定片段"""
    from pydub import AudioSegment
    
    # 使用 pydub 的参数来减少解码量（如果可能）
    load_kwargs = {
        "frame_rate": sample_rate, 
        "channels": 1
    }
    if start_second is not None: load_kwargs['start_second'] = start_second
    if duration: load_kwargs['duration'] = duration

    audio_segment = AudioSegment.from_file(audio_path, **load_kwargs)

    bit_depth = audio_segment.sample_width * 8
    max_val = float(1 << (bit_depth - 1))
    
    audio = np.array(
        audio_segment
        .set_channels(1)
        .set_frame_rate(sample_rate)
        .get_array_of_samples(),
    ) / max_val

    return audio.astype(np.float32)
