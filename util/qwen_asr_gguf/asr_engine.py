# coding=utf-8
import os
import numpy as np
from typing import Optional, List

from .inference.asr import QwenASREngine as QwenInternalEngine
from .inference.schema import ASREngineConfig as QwenConfig, MsgType, StreamingMessage

class RecognitionResult:
    """兼容 sherpa-onnx 的识别结果结构"""
    def __init__(self):
        self.text = ""
        self.tokens = []
        self.timestamps = []

class RecognitionStream:
    """兼容 sherpa-onnx 的识别流结构"""
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.audio_data = None
        self.result = RecognitionResult()

    def accept_waveform(self, sample_rate, audio):
        self.sample_rate = sample_rate
        self.audio_data = audio.astype(np.float32)

class QwenASREngine:
    """Qwen-ASR 推理引擎适配器，实现与 FunASREngine 类似的接口"""

    def __init__(self, config: QwenConfig):
        self.config = config
        self.engine = QwenInternalEngine(config)

    def create_stream(self, hotwords: Optional[str] = None):
        """创建识别流"""
        return RecognitionStream()

    def decode_stream(
        self, 
        stream: RecognitionStream, 
        context: Optional[str] = None,
        language: Optional[str] = None,
        temperature: float = 0.4
    ):
        """
        解码识别流
        
        Args:
            stream: 包含音频数据的流对象
            context: 上下文参考文本（之前的识别结果）
            language: 目标语言
            temperature: 解码温度
        """
        if stream.audio_data is None:
            return

        sr = 16000
        audio_data = stream.audio_data
        
        # 如果长度超过了最大限制，则截断
        max_samples = int(self.config.chunk_size * sr)
        if len(audio_data) > max_samples:
            audio_data = audio_data[:max_samples]

        # 1. 提交编码任务（同步调用）
        audio_embd, enc_time = self.engine.encoder.encode(audio_data)
        
        # 3. 构造 Prompt 并解码
        # context 在 Qwen _build_prompt_embd 中被放入 System Prompt 区域
        full_embd = self.engine._build_prompt_embd(
            audio_embd=audio_embd,
            prefix_text="", # 这里的 prefix_text 是 Assistant 已说的内容，流式分段时通常为空或使用 context
            context=context,
            language=language
        )

        # 4. 执行解码
        # rollback_num=5 是为了输出稳定性
        res = self.engine._safe_decode(
            full_embd, 
            prefix_text="", 
            rollback_num=5, 
            is_last_chunk=True, 
            temperature=temperature, 
            streaming=False
        )

        # 5. 更新结果
        stream.result.text = res.text
        # Qwen 纯 ASR 模式下暂不支持 token 级时间戳，由 server_recognize 自动补齐

    def cleanup(self):
        """释放资源"""
        self.engine.shutdown()


def create_asr_engine(
    model_dir: str,
    encoder_frontend_fn: str,
    encoder_backend_fn: str,
    llm_fn: str,
    use_dml: bool = False,
    n_ctx: int = 2048,
    chunk_size: float = 40.0,
    pad_to: int = 30, 
    verbose: bool = True,
    **kwargs
) -> QwenASREngine:
    """创建并初始化 Qwen ASR 引擎的快捷入口"""

    config = QwenConfig(
        model_dir=model_dir,
        encoder_frontend_fn=encoder_frontend_fn,
        encoder_backend_fn=encoder_backend_fn,
        llm_fn=llm_fn,
        use_dml=use_dml,
        n_ctx=n_ctx,
        chunk_size=chunk_size,
        pad_to = pad_to, 
        verbose=verbose,
        enable_aligner=False # 强制关闭对齐以符合需求
    )

    engine = QwenASREngine(config)
    return engine
