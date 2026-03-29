import numpy as np

def load_audio(audio_path, sample_rate=16000, use_normalizer=True, start_second=None, duration=None):
    """加载音频文件并转换为 16kHz PCM，支持按需加载指定片段"""
    from pydub import AudioSegment
    
    # 使用 pydub 的 start_second 和 duration 参数来减少解码量（如果环境支持）
    # 如果环境中的 pydub 不支持这些参数，它们会被忽略或报错，这里通过 kwargs 传递更稳健
    load_kwargs = {
        "frame_rate": sample_rate, 
        "channels": 1
    }
    if start_second: load_kwargs['start_second'] = start_second
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

    
    
    return audio

