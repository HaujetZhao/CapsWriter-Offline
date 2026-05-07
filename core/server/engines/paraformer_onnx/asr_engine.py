# coding: utf-8
import sherpa_onnx
import numpy as np
from typing import Optional, List, Any, Tuple
from dataclasses import dataclass
from ..base import BaseASREngine, RecognitionStream, EngineCapabilities, RecognitionResult
from core import get_logger

logger = get_logger('server')


@dataclass
class ParaformerConfig:
    """Paraformer 引擎配置参数"""
    paraformer: str
    tokens: str
    num_threads: int = 4
    sample_rate: int = 16000
    feature_dim: int = 80
    decoding_method: str = 'greedy_search'
    provider: str = 'cpu'
    debug: bool = False


class ParaformerStream(RecognitionStream):
    """
    Paraformer 识别流包装类
    转发调用至 sherpa_onnx.OfflineStream 并暴露标准结果接口
    """
    def __init__(self, recognizer: sherpa_onnx.OfflineRecognizer, sample_rate: int = 16000, hotwords: Optional[str] = None):
        super().__init__(sample_rate)
        # 实际创建 sherpa-onnx 的流
        self.internal_stream = recognizer.create_stream(hotwords=hotwords)

    def accept_waveform(self, sample_rate: int, audio: np.ndarray):
        self.internal_stream.accept_waveform(sample_rate, audio.astype(np.float32))


class ParaformerEngine(BaseASREngine):
    """
    Paraformer 识别引擎适配器

    声明能力：ASR, TIMESTAMPS
    不支持：PUNC, HOTWORDS (内置)
    """

    @staticmethod
    def _is_punct(ch: str) -> bool:
        return ch in '，。？！、,.?!:；、'

    @staticmethod
    def _post_process_tokens(tokens: List[str], timestamps: List[float]) -> Tuple[List[str], List[float]]:
        """
        后处理：将 BPE 子词合并为单词级 token，与 Qwen3-ASR 格式对齐

        Paraformer 输出的 token 是 BPE 子词级别（以 @@ 标记续接），
        此函数做三件事：
        1. BPE 子词合并为完整单词
        2. 连续单 ASCII 字母合并为一个 token（拼写场景如 a s → as）
        3. 根据语言边界插入空格 token：
           - 英文 ↔ 英文：空格
           - 英文 ↔ 非 ASCII：空格
           - 非 ASCII ↔ 非 ASCII：无空格
           - 标点前后：无空格
        """
        # Phase 1: 合并 BPE 子词 + 合并连续 ASCII 字母
        merged: List[Tuple[str, float, bool]] = []  # (text, ts, is_english)
        bpe_parts: List[str] = []
        bpe_ts: Optional[float] = None
        ascii_buf: List[str] = []
        ascii_ts: Optional[float] = None

        def flush_ascii():
            nonlocal ascii_ts
            if ascii_buf:
                merged.append((''.join(ascii_buf), ascii_ts or 0.0, True))
                ascii_buf.clear()
                ascii_ts = None

        for token, ts in zip(tokens, timestamps):
            if token.endswith('@@'):
                flush_ascii()
                bpe_parts.append(token[:-2])
                if bpe_ts is None:
                    bpe_ts = ts
            else:
                if bpe_parts:
                    flush_ascii()
                    word = ''.join(bpe_parts) + token
                    merged.append((word, bpe_ts or ts, True))
                    bpe_parts.clear()
                    bpe_ts = None
                elif len(token) == 1 and token.isascii() and token.isalpha():
                    if ascii_ts is None:
                        ascii_ts = ts
                    ascii_buf.append(token)
                else:
                    flush_ascii()
                    is_eng = bool(token and token[0].isascii() and token[0].isalpha())
                    merged.append((token, ts, is_eng))

        flush_ascii()
        if bpe_parts:
            merged.append((''.join(bpe_parts), bpe_ts or 0.0, True))

        # Phase 2: 根据语言边界插入空格
        result_tokens: List[str] = []
        result_timestamps: List[float] = []
        for i, (text, ts, is_eng) in enumerate(merged):
            if i > 0:
                prev_text, _, prev_eng = merged[i - 1]
                need_space = False
                if is_eng and prev_eng:
                    need_space = True               # English + English
                elif is_eng and not prev_eng and not ParaformerEngine._is_punct(prev_text):
                    need_space = True               # CJK + English
                elif not is_eng and prev_eng and not ParaformerEngine._is_punct(text):
                    need_space = True               # English + CJK
                if need_space:
                    result_tokens.append(' ')
                    result_timestamps.append(ts)    # 用后一词的时间戳
            result_tokens.append(text)
            result_timestamps.append(ts)

        return result_tokens, result_timestamps

    def __init__(self, config: ParaformerConfig):
        super().__init__(config)
        logger.debug(f"正在初始化 ParaformerEngine，配置: {self.config}")
        
        # 提取参数用于 sherpa-onnx
        params = {
            'paraformer': self.config.paraformer,
            'tokens': self.config.tokens,
            'num_threads': self.config.num_threads,
            'sample_rate': self.config.sample_rate,
            'feature_dim': self.config.feature_dim,
            'decoding_method': self.config.decoding_method,
            'provider': self.config.provider,
            'debug': self.config.debug,
        }
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(**params)

    @property
    def capabilities(self) -> List[EngineCapabilities]:
        """声明具备的能力"""
        return [
            EngineCapabilities.ASR, 
            EngineCapabilities.TIMESTAMPS
        ]

    def create_stream(self, hotwords: Optional[str] = None) -> ParaformerStream:
        """创建包装后的识别流"""
        return ParaformerStream(self.recognizer, sample_rate=self.config.sample_rate, hotwords=hotwords)

    def decode_stream(
        self,
        stream: ParaformerStream,
        context: Optional[str] = None,
        language: Optional[str] = None,
        **kwargs
    ):
        """解码识别流并同步结果"""
        if context:
            logger.debug(f"ParaformerEngine 不支持解码 context，已忽略")
        if language and language != 'auto':
            logger.debug(f"ParaformerEngine 是中文专用模型，语言设置 '{language}' 已忽略")
        
        # 1. 调用内核解码
        self.recognizer.decode_stream(stream.internal_stream)
        
        # 2. 将 sherpa-onnx 的结果同步回标准结果结构
        res = stream.internal_stream.result
        stream.result.text = res.text
        # 后处理 BPE 子词为单词级，空格独立 token
        stream.result.tokens, stream.result.timestamps = self._post_process_tokens(
            list(res.tokens), list(res.timestamps)
        )

    def update_hotwords(self, hotwords: List[str]):
        """Paraformer 暂不支持动态更新热词"""
        pass

    def cleanup(self):
        """释放资源"""
        self.recognizer = None
