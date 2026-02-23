import sys
import os
import ctypes
import codecs
import struct
import time
import numpy as np
import gguf
from gguf.constants import GGML_QUANT_SIZES, GGMLQuantizationType
from typing import List, Union
from pathlib import Path
from os.path import relpath
from typing import Union
from . import logger

# =========================================================================
# Configuration
# =========================================================================
# QUIET_LOGS = True 时，不打印任何日志。但现在我们路由到 logger。
QUIET_LOGS = False
_log_callback_ref = None

# =========================================================================
# Type Definitions
# =========================================================================

llama_token = ctypes.c_int32
llama_pos = ctypes.c_int32
llama_seq_id = ctypes.c_int32

class llama_model_params(ctypes.Structure):
    _fields_ = [
        ("devices", ctypes.POINTER(ctypes.c_void_p)),
        ("tensor_buft_overrides", ctypes.POINTER(ctypes.c_void_p)),
        ("n_gpu_layers", ctypes.c_int32),
        ("split_mode", ctypes.c_int32),
        ("main_gpu", ctypes.c_int32),
        ("tensor_split", ctypes.POINTER(ctypes.c_float)),
        ("progress_callback", ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_float, ctypes.c_void_p)),
        ("progress_callback_user_data", ctypes.c_void_p),
        ("kv_overrides", ctypes.POINTER(ctypes.c_void_p)),
        ("vocab_only", ctypes.c_bool),
        ("use_mmap", ctypes.c_bool),
        ("use_direct_io", ctypes.c_bool),
        ("use_mlock", ctypes.c_bool),
        ("check_tensors", ctypes.c_bool),
        ("use_extra_bufts", ctypes.c_bool),
        ("no_host", ctypes.c_bool),
        ("no_alloc", ctypes.c_bool),
    ]

class llama_context_params(ctypes.Structure):
    _fields_ = [
        ("n_ctx", ctypes.c_uint32),
        ("n_batch", ctypes.c_uint32),
        ("n_ubatch", ctypes.c_uint32),
        ("n_seq_max", ctypes.c_uint32),
        ("n_threads", ctypes.c_int32),
        ("n_threads_batch", ctypes.c_int32),
        ("rope_scaling_type", ctypes.c_int32),
        ("pooling_type", ctypes.c_int32),
        ("attention_type", ctypes.c_int32),
        ("flash_attn_type", ctypes.c_int32),
        ("rope_freq_base", ctypes.c_float),
        ("rope_freq_scale", ctypes.c_float),
        ("yarn_ext_factor", ctypes.c_float),
        ("yarn_attn_factor", ctypes.c_float),
        ("yarn_beta_fast", ctypes.c_float),
        ("yarn_beta_slow", ctypes.c_float),
        ("yarn_orig_ctx", ctypes.c_uint32),
        ("defrag_thold", ctypes.c_float),
        ("cb_eval", ctypes.c_void_p),
        ("cb_eval_user_data", ctypes.c_void_p),
        ("type_k", ctypes.c_int32),
        ("type_v", ctypes.c_int32),
        ("abort_callback", ctypes.c_void_p),
        ("abort_callback_data", ctypes.c_void_p),
        ("embeddings", ctypes.c_bool),
        ("offload_kqv", ctypes.c_bool),
        ("no_perf", ctypes.c_bool),
        ("op_offload", ctypes.c_bool),
        ("swa_full", ctypes.c_bool),
        ("kv_unified", ctypes.c_bool),
        ("samplers", ctypes.POINTER(ctypes.c_void_p)),
        ("n_samplers", ctypes.c_size_t),
    ]

class llama_sampler_chain_params(ctypes.Structure):
    _fields_ = [
        ("no_perf", ctypes.c_bool),
    ]

class llama_logit_bias(ctypes.Structure):
    _fields_ = [
        ("token", llama_token),
        ("bias", ctypes.c_float),
    ]

class llama_batch(ctypes.Structure):
    _fields_ = [
        ("n_tokens", ctypes.c_int32),
        ("token", ctypes.POINTER(llama_token)),
        ("embd", ctypes.POINTER(ctypes.c_float)),
        ("pos", ctypes.POINTER(llama_pos)),
        ("n_seq_id", ctypes.POINTER(ctypes.c_int32)),
        ("seq_id", ctypes.POINTER(ctypes.POINTER(llama_seq_id))),
        ("logits", ctypes.POINTER(ctypes.c_int8)),
    ]

# =========================================================================
# Llama Library Bindings
# =========================================================================

# Global library references
llama = None
ggml = None
ggml_base = None

# Global function pointers
llama_log_set = None
llama_backend_init = None
llama_backend_free = None
llama_model_default_params = None
llama_model_load_from_file = None
llama_model_free = None
llama_model_get_vocab = None
llama_context_default_params = None
llama_init_from_model = None
llama_free = None
llama_batch_init = None
llama_batch_free = None
llama_decode = None
llama_get_logits = None
llama_get_logits_ith = None
llama_get_embeddings = None
llama_tokenize = None
llama_vocab_n_tokens = None
llama_vocab_eos = None
llama_token_to_piece = None
llama_get_memory = None
llama_memory_clear = None
llama_model_n_embd = None

# Sampler
llama_sampler_chain_default_params = None
llama_sampler_chain_init = None
llama_sampler_chain_add = None
llama_sampler_init_greedy = None
llama_sampler_init_dist = None
llama_sampler_init_temp = None
llama_sampler_init_top_k = None
llama_sampler_init_top_p = None
llama_sampler_sample = None
llama_sampler_free = None

def init_llama_lib():
    """初始化 llama.cpp 库，支持跨平台加载"""
    global llama, ggml, ggml_base
    global llama_log_set, llama_backend_init, llama_backend_free
    global llama_model_default_params, llama_model_load_from_file, llama_model_free, llama_model_get_vocab
    global llama_context_default_params, llama_init_from_model, llama_free
    global llama_batch_init, llama_batch_free, llama_batch_get_one
    global llama_decode, llama_get_logits, llama_get_logits_ith, llama_get_embeddings, llama_tokenize
    global llama_get_memory, llama_memory_clear, llama_model_n_embd
    global llama_vocab_n_tokens, llama_vocab_eos, llama_token_to_piece
    global llama_sampler_chain_default_params, llama_sampler_chain_init, llama_sampler_chain_add
    global llama_sampler_init_greedy, llama_sampler_init_dist, llama_sampler_init_temp
    global llama_sampler_init_top_k, llama_sampler_init_top_p, llama_sampler_sample, llama_sampler_free
    global llama_sampler_init_logit_bias
    global _log_callback_ref

    if llama is not None:
        return

    # 获取库文件所在目录 (模块目录下的 bin)
    lib_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")

    # DLL 命名处理
    if sys.platform == "win32":
        GGML_DLL = "ggml.dll"
        GGML_BASE_DLL = "ggml-base.dll"
        LLAMA_DLL = "llama.dll"
    elif sys.platform == "darwin":
        GGML_DLL = "libggml.dylib"
        GGML_BASE_DLL = "libggml-base.dylib"
        LLAMA_DLL = "libllama.dylib"
    else:
        GGML_DLL = "libggml.so"
        GGML_BASE_DLL = "libggml-base.so"
        LLAMA_DLL = "libllama.so"

    ggml = ctypes.CDLL(os.path.join(lib_dir, GGML_DLL))
    ggml_base = ctypes.CDLL(os.path.join(lib_dir, GGML_BASE_DLL))
    llama = ctypes.CDLL(os.path.join(lib_dir, LLAMA_DLL))

    # 设置日志回调
    LOG_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p)
    llama_log_set = llama.llama_log_set
    llama_log_set.argtypes = [LOG_CALLBACK, ctypes.c_void_p]
    llama_log_set.restype = None
    
    # 默认开启日志路由
    configure_logging(quiet=QUIET_LOGS)

    # 加载后端
    ggml_backend_load_all = ggml.ggml_backend_load_all
    ggml_backend_load_all.argtypes = []
    ggml_backend_load_all.restype = None
    ggml_backend_load_all()

    llama_backend_init = llama.llama_backend_init
    llama_backend_init.argtypes = []
    llama_backend_init.restype = None
    llama_backend_init()

    # 绑定其他函数
    llama_backend_free = llama.llama_backend_free
    llama_backend_free.argtypes = []
    llama_backend_free.restype = None

    llama_model_default_params = llama.llama_model_default_params
    llama_model_default_params.argtypes = []
    llama_model_default_params.restype = llama_model_params

    llama_model_load_from_file = llama.llama_model_load_from_file
    llama_model_load_from_file.argtypes = [ctypes.c_char_p, llama_model_params]
    llama_model_load_from_file.restype = ctypes.c_void_p

    llama_model_free = llama.llama_model_free
    llama_model_free.argtypes = [ctypes.c_void_p]
    llama_model_free.restype = None

    llama_model_get_vocab = llama.llama_model_get_vocab
    llama_model_get_vocab.argtypes = [ctypes.c_void_p]
    llama_model_get_vocab.restype = ctypes.c_void_p

    llama_model_n_embd = llama.llama_model_n_embd
    llama_model_n_embd.argtypes = [ctypes.c_void_p]
    llama_model_n_embd.restype = ctypes.c_int32

    # Context
    llama_context_default_params = llama.llama_context_default_params
    llama_context_default_params.argtypes = []
    llama_context_default_params.restype = llama_context_params

    llama_init_from_model = llama.llama_init_from_model
    llama_init_from_model.argtypes = [ctypes.c_void_p, llama_context_params]
    llama_init_from_model.restype = ctypes.c_void_p

    llama_free = llama.llama_free
    llama_free.argtypes = [ctypes.c_void_p]
    llama_free.restype = None

    # Batch
    llama_batch_init = llama.llama_batch_init
    llama_batch_init.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.c_int32]
    llama_batch_init.restype = llama_batch

    llama_batch_free = llama.llama_batch_free
    llama_batch_free.argtypes = [llama_batch]
    llama_batch_free.restype = None
    
    llama_batch_get_one = llama.llama_batch_get_one
    llama_batch_get_one.argtypes = [ctypes.POINTER(llama_token), ctypes.c_int32]
    llama_batch_get_one.restype = llama_batch

    # Decode
    llama_decode = llama.llama_decode
    llama_decode.argtypes = [ctypes.c_void_p, llama_batch]
    llama_decode.restype = ctypes.c_int32

    # Logits
    llama_get_logits = llama.llama_get_logits
    llama_get_logits.argtypes = [ctypes.c_void_p]
    llama_get_logits.restype = ctypes.POINTER(ctypes.c_float)

    llama_get_logits_ith = llama.llama_get_logits_ith
    llama_get_logits_ith.argtypes = [ctypes.c_void_p, ctypes.c_int32]
    llama_get_logits_ith.restype = ctypes.POINTER(ctypes.c_float)

    llama_get_embeddings = llama.llama_get_embeddings
    llama_get_embeddings.argtypes = [ctypes.c_void_p]
    llama_get_embeddings.restype = ctypes.POINTER(ctypes.c_float)

    # Tokenize
    llama_tokenize = llama.llama_tokenize
    llama_tokenize.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int32,
        ctypes.POINTER(llama_token), ctypes.c_int32,
        ctypes.c_bool, ctypes.c_bool,
    ]
    llama_tokenize.restype = ctypes.c_int32

    # Vocab
    llama_vocab_n_tokens = llama.llama_vocab_n_tokens
    llama_vocab_n_tokens.argtypes = [ctypes.c_void_p]
    llama_vocab_n_tokens.restype = ctypes.c_int32

    llama_vocab_eos = llama.llama_vocab_eos
    llama_vocab_eos.argtypes = [ctypes.c_void_p]
    llama_vocab_eos.restype = llama_token

    llama_token_to_piece = llama.llama_token_to_piece
    llama_token_to_piece.argtypes = [ctypes.c_void_p, llama_token, ctypes.c_char_p, ctypes.c_int32, ctypes.c_int32, ctypes.c_bool]
    llama_token_to_piece.restype = ctypes.c_int

    # Memory (KV Cache)
    llama_get_memory = llama.llama_get_memory
    llama_get_memory.argtypes = [ctypes.c_void_p]
    llama_get_memory.restype = ctypes.c_void_p

    llama_memory_clear = llama.llama_memory_clear
    llama_memory_clear.argtypes = [ctypes.c_void_p, ctypes.c_bool]
    llama_memory_clear.restype = None

    # Sampler
    llama_sampler_chain_default_params = llama.llama_sampler_chain_default_params
    llama_sampler_chain_default_params.argtypes = []
    llama_sampler_chain_default_params.restype = llama_sampler_chain_params

    llama_sampler_chain_init = llama.llama_sampler_chain_init
    llama_sampler_chain_init.argtypes = [llama_sampler_chain_params]
    llama_sampler_chain_init.restype = ctypes.c_void_p

    llama_sampler_chain_add = llama.llama_sampler_chain_add
    llama_sampler_chain_add.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    llama_sampler_chain_add.restype = None

    llama_sampler_init_greedy = llama.llama_sampler_init_greedy
    llama_sampler_init_greedy.argtypes = []
    llama_sampler_init_greedy.restype = ctypes.c_void_p

    llama_sampler_init_dist = llama.llama_sampler_init_dist
    llama_sampler_init_dist.argtypes = [ctypes.c_uint32]
    llama_sampler_init_dist.restype = ctypes.c_void_p

    llama_sampler_init_temp = llama.llama_sampler_init_temp
    llama_sampler_init_temp.argtypes = [ctypes.c_float]
    llama_sampler_init_temp.restype = ctypes.c_void_p

    llama_sampler_init_top_k = llama.llama_sampler_init_top_k
    llama_sampler_init_top_k.argtypes = [ctypes.c_int32]
    llama_sampler_init_top_k.restype = ctypes.c_void_p

    llama_sampler_init_top_p = llama.llama_sampler_init_top_p
    llama_sampler_init_top_p.argtypes = [ctypes.c_float, ctypes.c_size_t]
    llama_sampler_init_top_p.restype = ctypes.c_void_p

    llama_sampler_sample = llama.llama_sampler_sample
    llama_sampler_sample.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int32]
    llama_sampler_sample.restype = llama_token

    llama_sampler_free = llama.llama_sampler_free
    llama_sampler_free.argtypes = [ctypes.c_void_p]
    llama_sampler_free.restype = None

    llama_sampler_init_logit_bias = llama.llama_sampler_init_logit_bias
    llama_sampler_init_logit_bias.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.POINTER(llama_logit_bias)]
    llama_sampler_init_logit_bias.restype = ctypes.c_void_p


def load_model(model_path: str):
    """
    加载 GGUF 模型（自动处理初始化和路径编码）
    
    Args:
        model_path: GGUF 模型文件路径
        
    Returns:
        model: llama_model 指针
    """
    lib_dir = Path(__file__).parent / 'bin'
    model_path = Path(model_path)
    model_rel = Path(relpath(model_path, lib_dir))

    # 跳转到 dll 所在目录，并将其加到 Path
    original_cwd = Path.cwd()
    os.chdir(lib_dir)
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(os.getcwd())
    os.environ['PATH'] = os.getcwd() + os.pathsep + os.environ['PATH']
    logger.info(f"Changed directory to: {Path.cwd()}")

    # 初始化 backend，载入模型
    init_llama_lib()
    model_params = llama_model_default_params()
    model = llama_model_load_from_file(
        model_rel.as_posix().encode('utf-8'),
        model_params
    )

    if model:
        os.chdir(original_cwd)
        logger.info(f"Restored directory to: {Path.cwd()}")
        return model
    else:
        logger.error(f'当前路径：{Path.cwd()}')
        logger.error(f'模型绝对路径：{model_path.as_posix()}')
        logger.error(f'模型可访问性：{model_path.exists()}')
        logger.error(f"模型加载失败: {model_path}")
        return None

def create_context(model, n_ctx=2048, n_batch=2048, n_ubatch=512, n_seq_max=1, 
                   embeddings=False, pooling_type=0, flash_attn=True, 
                   offload_kqv=True, no_perf=True, n_threads=None):
    """创建 ASR 专用的上下文"""
    params = llama_context_default_params()
    params.n_ctx = n_ctx
    params.n_batch = n_batch
    params.n_ubatch = n_ubatch
    params.n_seq_max = n_seq_max
    params.embeddings = embeddings
    params.pooling_type = pooling_type
    params.flash_attn_type = 1 if flash_attn else 0  # 1 = ON, 0 = OFF (auto typically uses what's available)
    params.offload_kqv = offload_kqv
    params.no_perf = no_perf
    
    if n_threads:
        params.n_threads = n_threads
        params.n_threads_batch = n_threads
    else:
        params.n_threads = os.cpu_count() // 2
        params.n_threads_batch = os.cpu_count()

    return llama_init_from_model(model, params)

class LlamaModel:
    """模型的面向对象封装"""
    def __init__(self, path, n_gpu_layers=-1):
        self.ptr = load_model(path)
            
        self.vocab = llama_model_get_vocab(self.ptr)
        self.n_embd = llama_model_n_embd(self.ptr)
        self.eos_token = llama_vocab_eos(self.vocab)

    def tokenize(self, text: str, add_special: bool = False, parse_special: bool = True) -> List[int]:
        """(Native) 文本转 Token ID 列表"""
        return text_to_tokens(self.vocab, text, add_special, parse_special)

    def detokenize(self, tokens: List[int]) -> str:
        """(Native) Token ID 列表转文本"""
        if tokens is None or len(tokens) == 0: return ""
        all_bytes = b"".join([self.token_to_bytes(tid) for tid in tokens])
        return all_bytes.decode('utf-8', errors='replace')

    def token_to_bytes(self, token_id: int) -> bytes:
        """(Native) 单个 Token 转字节"""
        return token_to_bytes(self.vocab, token_id)
        
    def token_to_piece(self, token_id: int) -> str:
        """(Native) 单个 Token 转字符串 Piece"""
        return self.token_to_bytes(token_id).decode('utf-8', errors='replace')

    def token_bos(self) -> int:
        return llama_vocab_bos(self.vocab)

    def token_eos(self) -> int:
        return llama_vocab_eos(self.vocab)
        
    def token_to_id(self, text: str) -> int:
        """(Native) 单个 Token 字符串转 ID (仅限 Exact Match)"""
        # 利用 tokenize 来查找 ID
        res = self.tokenize(text, add_special=False, parse_special=True)
        return res[0] if res else -1

    def __del__(self):
        if hasattr(self, 'ptr') and self.ptr:
            llama_model_free(self.ptr)
            self.ptr = None

class LlamaContext:
    """上下文的面向对象封装"""
    def __init__(self, model, n_ctx=2048, n_batch=2048, n_ubatch=512, n_seq_max=1, 
                 embeddings=False, pooling_type=0, flash_attn=True, 
                 offload_kqv=True, no_perf=True, n_threads=None, n_threads_batch=None):
        self.model = model # 保持模型引用防止被释放
        params = llama_context_default_params()
        params.n_ctx = n_ctx
        params.n_batch = n_batch
        params.n_ubatch = n_ubatch
        params.n_seq_max = n_seq_max
        params.embeddings = embeddings
        params.pooling_type = pooling_type
        params.flash_attn_type = 1 if flash_attn else 0
        params.offload_kqv = offload_kqv
        params.no_perf = no_perf
        
        # 线程配置
        cpu_count = os.cpu_count() or 4
        if n_threads:
            params.n_threads = n_threads
        else:
            params.n_threads = cpu_count // 2

        if n_threads_batch:
            params.n_threads_batch = n_threads_batch
        else:
            params.n_threads_batch = n_threads if n_threads else cpu_count

        self.ptr = llama_init_from_model(model.ptr, params)
        if not self.ptr:
            raise RuntimeError("上下文初始化失败")

    def decode(self, batch):
        struct = batch.struct if hasattr(batch, 'struct') else batch
        return llama_decode(self.ptr, struct)

    def decode_token(self, token_id):
        """
        原子操作：设置单 Token Batch 并执行解码
        """
        return self.decode(get_one_batch(token_id))

    def get_logits(self):
        """获取 Batch 中最后一个启用 Logits 的 Token 的输出"""
        return llama_get_logits(self.ptr)

    def get_logits_ith(self, i: int):
        """获取 Batch 中第 i 个 Token 的 Logits 输出 (前提是该 Token 启用了 Logits 标志)"""
        return llama_get_logits_ith(self.ptr, i)

    def get_embeddings(self):
        return llama_get_embeddings(self.ptr)

    def clear_kv_cache(self):
        mem = llama_get_memory(self.ptr)
        llama_memory_clear(mem, True)

    def __del__(self):
        if hasattr(self, 'ptr') and self.ptr:
            llama_free(self.ptr)
            self.ptr = None

class LlamaBatch:
    """Batch 的面向对象封装，支持直接属性访问"""
    def __init__(self, n_tokens, embd_dim=0, n_seq_max=1):
        self.struct = llama_batch_init(n_tokens, embd_dim, n_seq_max)
        self.n_tokens_max = n_tokens

    @property
    def n_tokens(self): return self.struct.n_tokens
    @n_tokens.setter
    def n_tokens(self, val): self.struct.n_tokens = val

    @property
    def token(self): return self.struct.token
    @property
    def embd(self): return self.struct.embd
    @property
    def pos(self): return self.struct.pos
    @property
    def n_seq_id(self): return self.struct.n_seq_id
    @property
    def seq_id(self): return self.struct.seq_id
    @property
    def logits(self): return self.struct.logits

    def set_embd(self, data: np.ndarray, pos: Union[np.ndarray, int] = 0, seq_id: int = 0):
        """
        高阶接口：直接注入 Embedding 数据并初始化位置信息
        
        Args:
            data: Embedding 数据 [n_tokens, dim]
            pos: 位置信息。
                 - 若为 int，则视为起始偏移量，自动生成 [offset, offset+1, ...]
                 - 若为 np.ndarray，则直接拷贝到 pos buffer (支持 Qwen3 等复杂位置编码)
            seq_id: 序列 ID
        """
        n_tokens = data.shape[0]
        if n_tokens > self.n_tokens_max:
            raise ValueError(f"Batch 空间不足: {n_tokens} > {self.n_tokens_max}")
        
        # 1. 内存移动 (Embedding)
        if not data.flags['C_CONTIGUOUS']:
            data = np.ascontiguousarray(data)
        ctypes.memmove(self.embd, data.ctypes.data, data.nbytes)
        
        # 2. 位置信息处理 (Position)
        if isinstance(pos, int):
            # 自动生成线性位置
            pos_offset = pos
            for i in range(n_tokens):
                self.pos[i] = pos_offset + i
        elif isinstance(pos, np.ndarray):
            # 外部提供的复杂位置 (如 Qwen3 的多平面位置)
            # 注意：不检查 pos 长度是否等于 n_tokens，因为可能有 stride (Qwen3 case)
            # 但必须确保不超过 batch capacity
            if not pos.flags['C_CONTIGUOUS']:
                pos = np.ascontiguousarray(pos)
            
            # 使用 memmove 直接拷贝
            # self.pos 是 ctypes 指针，可以直接操作
            ctypes.memmove(self.pos, pos.ctypes.data, pos.nbytes)
        else:
            raise TypeError(f"Unsupported pos type: {type(pos)}")

        # 3. 设置其他元数据
        self.n_tokens = n_tokens
        for i in range(n_tokens):
            self.n_seq_id[i] = 1
            self.seq_id[i][0] = seq_id
            self.logits[i] = 1 if i == n_tokens - 1 else 0
        
        return self

    def __del__(self):
        if hasattr(self, 'struct'):
            llama_batch_free(self.struct)

def get_one_batch(token_id: int):
    """
    底层极限优化：用于单 Token 生成的无分配 Batch 构造。
    相当于 C++ 的 llama_batch_get_one(&token, 1)。
    它不依赖 llama_batch_init 的内存分配，并允许底层自动推断 pos。
    """
    token_arr = (llama_token * 1)(token_id)
    return llama_batch_get_one(token_arr, 1)

class LlamaSampler:
    """采样器的面向对象封装"""
    def __init__(self, temperature=0.8, top_k=50, top_p=1.0, seed=None, logit_bias=None, n_vocab=0):
        import time
        if seed is None:
            seed = int(time.time())
            
        sparams = llama_sampler_chain_default_params()
        self.ptr = llama_sampler_chain_init(sparams)
        
        # Logit Bias (支持范围/掩码)
        if logit_bias and n_vocab > 0 and isinstance(logit_bias, dict):
            n_bias = len(logit_bias)
            BiasArray = llama_logit_bias * n_bias
            bias_data = BiasArray()
            
            for i, (token, bias) in enumerate(logit_bias.items()):
                bias_data[i].token = token
                bias_data[i].bias = bias
            
            llama_sampler_chain_add(self.ptr, llama_sampler_init_logit_bias(n_vocab, n_bias, bias_data))

        if temperature > 0:
            llama_sampler_chain_add(self.ptr, llama_sampler_init_top_k(top_k))
            llama_sampler_chain_add(self.ptr, llama_sampler_init_top_p(top_p, 1))
            llama_sampler_chain_add(self.ptr, llama_sampler_init_temp(temperature))
            llama_sampler_chain_add(self.ptr, llama_sampler_init_dist(seed))
        else:
            llama_sampler_chain_add(self.ptr, llama_sampler_init_greedy())

        self._neg_inf = -1e9

    def sample(self, ctx, idx=-1, limit_start=None, limit_end=None):
        """
        采样一个 Token
        
        Args:
            limit_start (int, optional): 限制采样范围的起始 Index (包含)
            limit_end (int, optional): 限制采样范围的结束 Index (不包含)
        """
        ctx_ptr = ctx
        if hasattr(ctx, 'ptr'):
            ctx_ptr = ctx.ptr
            
        # 动态范围限制 (直接操作 Logits 内存，极速)
        if (limit_start is not None or limit_end is not None) and hasattr(ctx, 'get_logits') and hasattr(ctx, 'model'):
            # 需要获取 n_vocab
            # LlamaContext -> LlamaModel -> vocab -> n_tokens
            if hasattr(ctx.model, 'vocab'):
                n_vocab = llama_vocab_n_tokens(ctx.model.vocab)
                
                # 获取 Logits Numpy View
                logits_ptr = ctx.get_logits()
                logits = np.ctypeslib.as_array(logits_ptr, shape=(n_vocab,))
                
                # In-place 修改
                # 注意：这会修改 ctx 中的 logits，影响本次采样。
                # 下一次 decode 会覆盖，所以是安全的。
                
                s = max(0, limit_start) if limit_start is not None else 0
                e = min(n_vocab, limit_end) if limit_end is not None else n_vocab
                
                if s > 0:
                    logits[0:s] = self._neg_inf
                if e < n_vocab:
                    logits[e:] = self._neg_inf
        
        return llama_sampler_sample(self.ptr, ctx_ptr, idx)

    def free(self):
        """释放采样器资源"""
        if hasattr(self, 'ptr') and self.ptr:
            llama_sampler_free(self.ptr)
            self.ptr = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.free()

    def __del__(self):
        self.free()


class ASRStreamDecoder:
    """ASR 专属流式解码器，集成字节解码与 ASRReporter 交互"""
    def __init__(self, vocab, reporter=None):
        self.vocab = vocab
        self.reporter = reporter
        self.byte_decoder = codecs.getincrementaldecoder("utf-8")(errors='replace')
        self.generated_text = ""
        self.tokens_generated = 0
        self.tokens = []

    def push(self, token_id: int):
        """推入 Token，返回新解码的文字片段"""
        raw_bytes = token_to_bytes(self.vocab, token_id)
        text_piece = self.byte_decoder.decode(raw_bytes, final=False)
        self.tokens.append(text_piece)
        self.tokens_generated += 1
        
        self.generated_text += text_piece
        
        if self.reporter:
            self.reporter.stream(text_piece)
            
        return text_piece

    def flush(self):
        """清空残余字节并返回"""
        remaining = self.byte_decoder.decode(b"", final=True)
        self.tokens.append(remaining)
        self.generated_text += remaining
        return remaining


def python_log_callback(level, message, user_data):
    """
    llama.cpp 日志回调函数
    level: 
        2 = ERROR
        3 = WARN
        4 = INFO
        5 = DEBUG
    """
    if not message: return
    try:
        msg_str = message.decode('utf-8', errors='replace').strip()
        if not msg_str or msg_str in ['.', '\n']: return
        
        if level == 2:
            logger.error(f"[llama.cpp] {msg_str}")
        elif level == 3:
            logger.warning(f"[llama.cpp] {msg_str}")
        elif level == 4:
            logger.info(f"[llama.cpp] {msg_str}")
        elif level >= 5:
            logger.debug(f"[llama.cpp] {msg_str}")
        else:
            logger.info(f"[llama.cpp] {msg_str}")
    except Exception as e:
        # 防止回调错误导致程序崩溃
        print(f"日志回调出错: {e}")

def configure_logging(quiet=False):
    """配置 llama.cpp 日志回调"""
    global _log_callback_ref
    if not llama_log_set: return
    
    LOG_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p)
    if not quiet:
        _log_callback_ref = LOG_CALLBACK(python_log_callback)
        llama_log_set(_log_callback_ref, None)
    else:
        # 如果需要静默，可以传递一个空函数，或者将 logger 级别调高
        _log_callback_ref = LOG_CALLBACK(lambda l, m, u: None)
        llama_log_set(_log_callback_ref, None)



# =========================================================================
# Embedding Table
# =========================================================================



class LlamaEmbeddingTable:
    """动态反量化 Embedding 表，支持 table[ids] 语法"""
    def __init__(self, raw_data, qtype):
        self.raw_data = raw_data
        self.qtype = qtype
        
    def __len__(self):
        return self.raw_data.shape[0]

    def __getitem__(self, tokens):
        from gguf.quants import dequantize
        
        # 如果是原生 float 类型，直接返回
        if self.raw_data.dtype in (np.float32, np.float16):
            return self.raw_data[tokens].astype(np.float32)
            
        # 调用官方库进行高性能反量化
        return dequantize(self.raw_data[tokens], self.qtype.value)




def _skip_gguf_value(mm, offs, v_type):
    # UINT8=0, INT8=1, UINT16=2, INT16=3, UINT32=4, INT32=5, FLOAT32=6, BOOL=7, STRING=8, ARRAY=9, UINT64=10, INT64=11, FLOAT64=12
    fixed = [1, 1, 2, 2, 4, 4, 4, 1, -1, -2, 8, 8, 8]
    val_len = fixed[v_type]
    if val_len > 0:
        return offs + val_len
    elif val_len == -1: # string
        slen = struct.unpack_from("<Q", mm, offs)[0]
        return offs + 8 + slen
    elif val_len == -2: # array
        itype, alen = struct.unpack_from("<IQ", mm, offs)
        offs += 12
        if itype == 8: # string array
            for _ in range(alen):
                slen = struct.unpack_from("<Q", mm, offs)[0]
                offs += 8 + slen
        else:
            item_len = fixed[itype]
            if item_len > 0:
                offs += item_len * alen
            else:
                raise ValueError("Nested arrays or unknown type not supported in fast skip")
        return offs

def get_token_embeddings_gguf(model_path, target_tensor="token_embd.weight"):
    """
    超极速 GGUF Embedding 提取 (直接二进制寻址)
    避免加载整个模型、避免解析包含 15 万词条的 tokenizer 对象。耗时降至 < 50ms。
    """
    t_start = time.time()
    mm = np.memmap(model_path, mode='r')
    
    # 获取文件头信息
    tensor_count, kv_count = struct.unpack_from("<QQ", mm, 8)
    offs = 24
    alignment = 32
    
    # 光速跃过/扫描所有 KV 字段
    for _ in range(kv_count):
        key_len = struct.unpack_from("<Q", mm, offs)[0]
        offs += 8
        if key_len == 17 and mm[offs:offs+17].tobytes() == b'general.alignment':
            offs += 17
            v_type = struct.unpack_from("<I", mm, offs)[0]
            offs += 4
            if v_type == 4: # UINT32
                alignment = struct.unpack_from("<I", mm, offs)[0]
                offs += 4
                continue
        else:
            offs += key_len
            
        v_type = struct.unpack_from("<I", mm, offs)[0]
        offs += 4
        offs = _skip_gguf_value(mm, offs, v_type)
        
    # 扫描 Tensor Infos 搜寻我们想要的张量
    target_rel_offset = None
    target_type = None
    target_shape = None # GGUF shape 是倒序的 [n_embd, vocab_size]
    
    target_bytes = target_tensor.encode('utf-8')
    for _ in range(tensor_count):
        name_len = struct.unpack_from("<Q", mm, offs)[0]
        offs += 8
        is_target = False
        if name_len == len(target_bytes) and mm[offs:offs+name_len].tobytes() == target_bytes:
            is_target = True
        offs += name_len
        
        n_dims = struct.unpack_from("<I", mm, offs)[0]
        offs += 4
        
        shape = struct.unpack_from(f"<{n_dims}Q", mm, offs) # 返回元组
        offs += 8 * n_dims
        
        t_type = struct.unpack_from("<I", mm, offs)[0]
        offs += 4
        
        rel_offset = struct.unpack_from("<Q", mm, offs)[0]
        offs += 8
        
        if is_target:
            target_shape = shape
            target_type = t_type
            target_rel_offset = rel_offset
            
    # 计算数据区起始点并加载张量
    padding = offs % alignment
    if padding != 0:
        offs += (alignment - padding)
    data_offset = offs
    
    if target_shape is None:
        logger.error(f"无法在 {model_path} 中找到 {target_tensor}")
        return None
        
    abs_offset = data_offset + target_rel_offset
    n_embd = target_shape[0]     # 特征维度
    vocab_size = target_shape[1] # 词表大小
    
    qtype = GGMLQuantizationType(target_type)
    if qtype in GGML_QUANT_SIZES:
        block_size, type_size = GGML_QUANT_SIZES[qtype]
        bytes_per_row = (n_embd // block_size) * type_size
    else:
        # F32 或 F16
        if qtype == GGMLQuantizationType.F32:
            bytes_per_row = n_embd * 4
        elif qtype == GGMLQuantizationType.F16:
            bytes_per_row = n_embd * 2
        else:
            raise ValueError(f"未知的数据格式支持: {qtype.name}")

    total_bytes = vocab_size * bytes_per_row
    raw_data = mm[abs_offset : abs_offset + total_bytes]
    
    if qtype in (GGMLQuantizationType.F32, GGMLQuantizationType.F16):
        if qtype == GGMLQuantizationType.F32:
            raw_data = raw_data.view(np.float32).reshape(vocab_size, n_embd)
        else:
            raw_data = raw_data.view(np.float16).reshape(vocab_size, n_embd)
    else:
        raw_data = raw_data.reshape(vocab_size, bytes_per_row)
        
    total_time = time.time() - t_start
    logger.info(f"--- [QwenASR] 已极速载入 Embedding 视图 ({total_time*1000:.1f}ms) ---")
    logger.info(f"    - 量化格式: {qtype.name} ({n_embd} dims, {vocab_size} tokens)")
    
    return LlamaEmbeddingTable(raw_data, qtype)



# =========================================================================
# Utilities
# =========================================================================


def text_to_tokens(vocab, text, add_special=False, parse_special=True):
    text_bytes = text.encode("utf-8")
    n_tokens_max = len(text_bytes) + 32
    tokens = (llama_token * n_tokens_max)()
    n = llama_tokenize(vocab, text_bytes, len(text_bytes), tokens, n_tokens_max, add_special, parse_special)
    return [tokens[i] for i in range(n)] if n >= 0 else []

def token_to_bytes(vocab, token_id):
    buf = ctypes.create_string_buffer(256)
    n = llama_token_to_piece(vocab, token_id, buf, ctypes.sizeof(buf), 0, True)
    return buf.raw[:n] if n > 0 else b""