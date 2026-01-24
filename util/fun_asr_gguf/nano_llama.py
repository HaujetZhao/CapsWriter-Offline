import sys
import os
import ctypes
import numpy as np
import gguf
from . import logger

# =========================================================================
# Configuration
# =========================================================================
QUIET_LOGS = True
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

# Global function pointers (will be initialized in init_llama_lib)
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
llama_tokenize = None
llama_vocab_n_tokens = None
llama_vocab_eos = None
llama_token_to_piece = None
llama_get_memory = None
llama_memory_clear = None

def init_llama_lib():
    """初始化 llama.cpp 库，自动从模块所在目录加载 DLL"""
    global llama, ggml, ggml_base
    global llama_log_set, llama_backend_init, llama_backend_free
    global llama_model_default_params, llama_model_load_from_file, llama_model_free, llama_model_get_vocab
    global llama_context_default_params, llama_init_from_model, llama_free
    global llama_batch_init, llama_batch_free
    global llama_decode, llama_get_logits, llama_tokenize
    global llama_get_memory, llama_memory_clear
    global llama_vocab_n_tokens, llama_vocab_eos, llama_token_to_piece
    global _log_callback_ref

    # 获取模块所在目录下的 bin 目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.join(base_dir, "bin")

    original_cwd = os.getcwd()
    os.chdir(lib_dir)
    try:
        ggml = ctypes.CDLL("./ggml.dll")
        ggml_base = ctypes.CDLL("./ggml-base.dll")
        llama = ctypes.CDLL("./llama.dll")

        # 先设置日志回调（在加载 backend 之前）
        LOG_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p)
        llama_log_set = llama.llama_log_set
        llama_log_set.argtypes = [LOG_CALLBACK, ctypes.c_void_p]
        llama_log_set.restype = None

        if QUIET_LOGS:
            _log_callback_ref = LOG_CALLBACK(quiet_log_callback)
            llama_log_set(_log_callback_ref, None)

        # 然后再加载 backend
        ggml_backend_load_all = ggml.ggml_backend_load_all
        ggml_backend_load_all.argtypes = []
        ggml_backend_load_all.restype = None
        ggml_backend_load_all()
    except Exception as e:
        logger.error(f"加载 llama.cpp 动态库失败: {e}", exc_info=True)
        logger.error(f"尝试加载目录: {lib_dir}")
        raise
    finally:
        os.chdir(original_cwd)

    # Initialize backend
    llama_backend_init = llama.llama_backend_init
    llama_backend_init.argtypes = []
    llama_backend_init.restype = None
    llama_backend_init()



    llama_backend_free = llama.llama_backend_free
    llama_backend_free.argtypes = []
    llama_backend_free.restype = None

    # Model
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

    # Decode
    llama_decode = llama.llama_decode
    llama_decode.argtypes = [ctypes.c_void_p, llama_batch]
    llama_decode.restype = ctypes.c_int32

    # Logits
    llama_get_logits = llama.llama_get_logits
    llama_get_logits.argtypes = [ctypes.c_void_p]
    llama_get_logits.restype = ctypes.POINTER(ctypes.c_float)

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

def load_model(model_path: str):
    """
    加载 GGUF 模型（自动处理初始化和路径编码）
    
    Args:
        model_path: GGUF 模型文件路径
        
    Returns:
        model: llama_model 指针
    """
    init_llama_lib()
    
    if not os.path.exists(model_path):
        logger.error(f"GGUF 模型文件不存在: {model_path}")
        return None
        
    model_params = llama_model_default_params()
    
    return llama_model_load_from_file(
        model_path.encode('utf-8'),
        model_params
    )

_log_callback_ref = None

def quiet_log_callback(level, message, user_data):
    pass

def configure_logging(quiet=True):
    """配置 llama.cpp 日志回调"""
    global _log_callback_ref, llama_log_set
    
    if not llama_log_set:
        return
        
    LOG_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p)
    
    if quiet:
        _log_callback_ref = LOG_CALLBACK(quiet_log_callback)
        llama_log_set(_log_callback_ref, None)
    else:
        # Restore default (pass None to reset? or just do nothing if we want default behavior)
        # llama.cpp default is usually stderr. passing NULL might reset it if the API supports it.
        # But for now, user just wants to silence it.
        pass

# =========================================================================
# Utilities
# =========================================================================

class ByteDecoder:
    """
    字节级解码器，用于处理 BPE 拆分的 UTF-8 字符
    """
    def __init__(self):
        self.buffer = b""
    
    def decode(self, raw_bytes):
        self.buffer += raw_bytes
        result = ""
        while self.buffer:
            try:
                result += self.buffer.decode('utf-8')
                self.buffer = b""
                break
            except UnicodeDecodeError as e:
                if e.reason == 'unexpected end of data' or 'invalid continuation' in e.reason:
                    if e.start > 0:
                        result += self.buffer[:e.start].decode('utf-8', errors='replace')
                        self.buffer = self.buffer[e.start:]
                    break
                else:
                    result += self.buffer[:1].decode('utf-8', errors='replace')
                    self.buffer = self.buffer[1:]
        return result
    
    def flush(self):
        if self.buffer:
            result = self.buffer.decode('utf-8', errors='replace')
            self.buffer = b""
            return result
        return ""

def text_to_tokens(vocab, text):
    """使用 llama.dll 进行文本分词"""
    # Note: requires llama_tokenize to be initialized
    text_bytes = text.encode("utf-8")
    n_tokens_max = len(text_bytes) + 32
    tokens = (llama_token * n_tokens_max)()
    
    n = llama_tokenize(vocab, text_bytes, len(text_bytes), tokens, n_tokens_max, False, True)
    if n < 0:
        return []
    return [tokens[i] for i in range(n)]

def token_to_bytes(vocab, token_id):
    """将 token 转换为原始字节 (用于 BPE 字节级 token)"""
    # Note: requires llama_token_to_piece to be initialized
    buf = ctypes.create_string_buffer(256)
    n = llama_token_to_piece(vocab, token_id, buf, ctypes.sizeof(buf), 0, True)
    if n > 0:
        return buf.raw[:n]
    return b""

def get_token_embeddings_gguf(model_path, cache_dir=None):
    """
    使用 gguf 库从 GGUF 读取 token_embd.weight。
    支持 F16/F32 和 Q8_0 量化格式
    使用缓存机制：首次读取后保存为 .npy 文件，后续直接加载缓存
    """
    if cache_dir is None:
        cache_dir = os.path.dirname(model_path)
    
    model_name = os.path.splitext(os.path.basename(model_path))[0]
    cache_path = os.path.join(cache_dir, f"{model_name}.embd.npy")
    
    if os.path.exists(cache_path):
        if os.path.getmtime(cache_path) >= os.path.getmtime(model_path):
            return np.load(cache_path)
    
    reader = gguf.GGUFReader(model_path, mode='r')
    
    for t in reader.tensors:
        if t.name == "token_embd.weight":
            if t.tensor_type == 8: # GGML_TYPE_Q8_0
                block_size_bytes = 34
                num_values_per_block = 32
                
                raw_data = t.data
                data_u8 = np.frombuffer(raw_data, dtype=np.uint8)
                n_blocks = data_u8.size // block_size_bytes
                
                blocks = data_u8.reshape(n_blocks, block_size_bytes)
                deltas = blocks[:, :2].view(np.float16).flatten()
                quants = blocks[:, 2:].view(np.int8)
                
                data = (deltas[:, np.newaxis] * quants).flatten().astype(np.float32).reshape(-1, 1024)
            else:
                data = t.data
                if data.dtype == np.float16:
                    data = data.astype(np.float32)
            
            np.save(cache_path, data)
            return data
    return None
