import numpy as np

def normalizer(audio, target_value=8192.0):
    """音频归一化处理"""
    audio = audio.astype(np.float32)
    rms = np.sqrt(np.mean((audio * audio), dtype=np.float32), dtype=np.float32)
    audio *= (target_value / (rms + 1e-7))
    np.clip(audio, -32768.0, 32767.0, out=audio)
    return audio.astype(np.int16)

def load_audio(audio_path, sample_rate=16000, use_normalizer=True, start_second=None, duration=None):
    """加载音频文件并转换为 16kHz PCM，支持按需加载指定片段"""
    from pydub import AudioSegment
    
    # 使用 pydub 的 start_second 和 duration 参数来减少解码量（如果环境支持）
    # 如果环境中的 pydub 不支持这些参数，它们会被忽略或报错，这里通过 kwargs 传递更稳健
    load_kwargs = {}
    if start_second is not None: load_kwargs['start_second'] = start_second
    if duration is not None: load_kwargs['duration'] = duration

    audio_segment = AudioSegment.from_file(audio_path, **load_kwargs)
    
    audio = np.array(
        audio_segment
        .set_channels(1)
        .set_frame_rate(sample_rate)
        .get_array_of_samples(),
        dtype=np.int16
    )
    
    if use_normalizer:
        audio = normalizer(audio, 8192.0)
    
    return audio
