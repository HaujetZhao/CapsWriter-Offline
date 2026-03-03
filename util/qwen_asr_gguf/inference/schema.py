# coding=utf-8
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Optional
import numpy as np

class MsgType(Enum):
    CMD_ENCODE = auto()   # 主进程 -> Encoder: 编码请求
    CMD_ALIGN = auto()    # 主进程 -> Aligner: 对齐请求
    CMD_STOP = auto()     # 主进程 -> Worker: 停止请求
    MSG_EMBD = auto()     # Worker -> 主进程: 返回特征 (Encoder)
    MSG_ALIGN = auto()    # Worker -> 主进程: 返回对齐结果 (Aligner)
    MSG_READY = auto()    # Worker -> 主进程: 就绪信号
    MSG_DONE = auto()     # Worker -> 主进程: 已退出信号
    MSG_ERROR = auto()    # Worker -> 主进程: 错误信号

@dataclass
class StreamingMessage:
    """音频编码/对齐进程通用通信协议"""
    msg_type: MsgType
    data: Any = None         # 存放音频 chunk 或 embedding/align 结果
    text: Optional[str] = None # 用于对齐的文本
    offset_sec: float = 0.0  # 对齐的时间轴偏移
    language: Optional[str] = None # 语言
    is_last: bool = False    # 标记是否为最后一段音频
    encode_time: float = 0.0 # 耗时统计

@dataclass
class DecodeResult:
    """LLM 解码内核输出标准化"""
    text: str = ""           # 包含前缀的完整文本
    new_text: str = ""       # 本次增量生成的文本
    stable_tokens: List[int] = field(default_factory=list)
    t_prefill: float = 0.0   # 预填充耗时 (ms)
    t_generate: float = 0.0  # 生成耗时 (ms)
    n_prefill: int = 0       # 预填充 token 数
    n_generate: int = 0      # 生成 token 数
    is_aborted: bool = False # 是否因重复或其他原因熔断中断

@dataclass(frozen=True)
class ForcedAlignItem:
    """单个词/字符的对齐结果"""
    text: str
    start_time: float        # 单位：秒
    end_time: float          # 单位：秒

@dataclass
class ForcedAlignResult:
    """对齐结果标准化集合 (官方结构化输出格式)"""
    items: List[ForcedAlignItem]
    performance: Optional[dict] = None

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx: int) -> ForcedAlignItem:
        return self.items[idx]

@dataclass
class AlignerConfig:
    """对齐引擎配置"""
    model_dir: str
    # 拆分为 Frontend 和 Backend
    encoder_frontend_fn: str = "qwen3_aligner_encoder_frontend.int4.onnx"
    encoder_backend_fn: str = "qwen3_aligner_encoder_backend.int4.onnx"
    
    llm_fn: str = "qwen3_aligner_llm.q4_k.gguf" 
    use_dml: bool = False
    n_ctx: int = 2048       # 对于 Aligner Decoder，每秒音频+文字，约占 30 个 token

@dataclass
class ASREngineConfig:
    """ASR 识别引擎配置"""
    model_dir: str
    # 拆分为 Frontend 和 Backend
    encoder_frontend_fn: str = "qwen3_asr_encoder_frontend.int4.onnx"
    encoder_backend_fn: str = "qwen3_asr_encoder_backend.int4.onnx"
    
    llm_fn: str = "qwen3_asr_llm.q4_k.gguf"
    use_dml: bool = False
    n_ctx: int = 2048           # 对于 ASR Decoder，每秒音频+文字，约占 20 个 token
    chunk_size: float = 40.0    # 每个片段 40s，对应 800 个 token
    memory_num: int = 1         # 记忆一个片段，转录一个片段，对应 1600 个 token
    verbose: bool = True
    enable_aligner: bool = False
    align_config: Optional[AlignerConfig] = None

    def __post_init__(self):
        if self.align_config is None:
            self.align_config = AlignerConfig(
                model_dir=self.model_dir,
                use_dml=self.use_dml
            )

@dataclass
class TranscribeResult:
    """ASR 转录结果 (含可选的对齐信息)"""
    text: str
    alignment: Optional[ForcedAlignResult] = None
    performance: Optional[dict] = None
