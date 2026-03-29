import os
import time
from pathlib import Path

from . import llama
from .encoder import AudioEncoder
from .ctc_decoder import CTCDecoder
from .utils import vprint, timer
from .prompt_builder import PromptBuilder
from .schema import ASREngineConfig

class Models:
    """管理所有模型组件的代码"""
    
    def __init__(self, config: ASREngineConfig):
        self.config = config
        verbose = self.config.verbose
        
        # 运行时组件
        self.encoder = None
        self.ctc_decoder = None
        
        # LLM 相关
        self.model = None
        self.ctx = None
        self.vocab = None
        self.eos_token = None
        self.embedding_table = None
        
        # 辅助组件
        self.prompt_builder = None
        
        self._initialized = False

        try:
            _, elapsed = timer(self._load_models, verbose)
            vprint(f"✓ 模型加载完成 (耗时: {elapsed:.2f}s)", verbose)
            self._initialized = True
        except Exception as e:
            vprint(f"✗ 初始化失败: {e}", verbose)
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"模型初始化失败: {e}")

    def _load_models(self, verbose):
        """执行实际的模型加载逻辑"""
        # 1. Encoder (ONNX)
        vprint("[1/6] 加载音频编码器 (Encoder)...", verbose)
        self.encoder = AudioEncoder(
            model_path=self.config.encoder_onnx_path,
            onnx_provider=self.config.onnx_provider,
            dml_pad_to=self.config.dml_pad_to
        )

        # 2. CTC Decoder (ONNX + Search)
        vprint("[2/6] 加载 CTC 解码器...", verbose)
        self.ctc_decoder = CTCDecoder(
            model_path=self.config.ctc_onnx_path,
            tokens_path=self.config.tokens_path,
            onnx_provider=self.config.onnx_provider,
            dml_pad_to=self.config.dml_pad_to,
            hotwords=self.config.hotwords,
            similar_threshold=self.config.similar_threshold
        )

        # 3. GGUF LLM Decoder
        vprint("[3/6] 加载 GGUF LLM 解码器...", verbose)
        if self.config.vulkan_force_fp32:
            os.environ["GGML_VK_DISABLE_F16"] = "1" 
        self.model = llama.LlamaModel(self.config.decoder_gguf_path, use_gpu=self.config.llm_use_gpu)
        self.vocab = self.model.vocab
        self.eos_token = self.model.eos_token

        # 4. Embeddings
        vprint("[4/6] 加载 Embedding 权重...", verbose)
        self.embedding_table = llama.get_token_embeddings_gguf(self.config.decoder_gguf_path)
        
        # 5. LLM Context
        vprint("[5/6] 创建 LLM 上下文...", verbose)
        self.ctx = llama.LlamaContext(
            self.model,
            n_ctx=2048,
            n_batch=2048,
            n_ubatch=self.config.n_ubatch,
            n_threads=self.config.n_threads,
        )
        
        # 6. Prompt构建器
        vprint("[6/6] 初始化 Prompt 构建器器...", verbose)
        self.prompt_builder = PromptBuilder(self.vocab, self.embedding_table)

    def cleanup(self):
        self.ctx = None
        self.model = None
        self.encoder = None
        self.ctc_decoder = None
        self._initialized = False
        print("[ASR] 资源已释放")

