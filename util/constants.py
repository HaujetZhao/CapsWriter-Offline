# coding: utf-8
"""
内部常量定义模块

集中管理音频格式等内部实现常量。
注意：用户可配置的选项应放在根目录的 config.py 中。
"""


class AudioFormat:
    """音频格式常量"""
    SAMPLE_RATE: int = 16000           # 采样率 (Hz)
    BYTES_PER_SAMPLE: int = 4          # 每个采样点的字节数 (float32)
    CHANNELS: int = 1                   # 声道数 (单声道)
    
    # 计算属性
    BYTES_PER_SECOND: int = SAMPLE_RATE * BYTES_PER_SAMPLE * CHANNELS  # 64000
    
    @classmethod
    def seconds_to_bytes(cls, seconds: float) -> int:
        """将秒数转换为字节数"""
        return int(seconds * cls.BYTES_PER_SECOND)
    
    @classmethod
    def bytes_to_seconds(cls, byte_count: int) -> float:
        """将字节数转换为秒数"""
        return byte_count / cls.BYTES_PER_SECOND


class Punctuation:
    """标点符号集合"""
    # 常见的中文和英文标点符号
    ALL = '，。！？；：、「」『』（）《》【】[]{},.!?;:"\''


class TextMerge:
    """文本拼接配置（服务端内部使用）"""
    OVERLAP_CHARS: int = 20            # 文本拼接时查找重叠的字符数
    ERROR_TOLERANCE: int = 1           # 容错字符数（允许匹配中有N个错字）
