import os
import time
import ctypes
from pathlib import Path
from typing import Optional, Tuple

from .. import llama, logger
from ..nano_ctc import load_ctc_tokens
from ..nano_onnx import load_onnx_models
from ..hotword.manager import get_hotword_manager
from ..utils import vprint
from ..prompt_utils import PromptBuilder
from ..nano_dataclass import ASREngineConfig

class ModelManager:
    """管理所有模型组件的代码"""
    
    def __init__(self, config: ASREngineConfig):
        self.config = config
        
        # 运行时对象
        self.encoder_sess = None
        self.ctc_sess = None
        self.model = None  # LlamaModel 实例
        self.ctx = None    # LlamaContext 实例
        self.vocab = None
        self.eos_token = None
        self.embedding_table = None
        self.ctc_id2token = None
        self.hotword_manager = None
        self.corrector = None
        self.prompt_builder = None
        
        self._initialized = False

    def initialize(self, verbose: bool = True) -> bool:
        if self._initialized:
            return True
        
        try:
            t_start = time.perf_counter()
            
            # 1. ONNX
            vprint("[1/6] 加载 ONNX 模型...", verbose)
            self.encoder_sess, self.ctc_sess, _ = load_onnx_models(
                self.config.encoder_onnx_path,
                self.config.ctc_onnx_path
            )

            # 2. GGUF
            vprint("[2/6] 加载 GGUF LLM Decoder...", verbose)
            self.model = llama.LlamaModel(self.config.decoder_gguf_path, n_gpu_layers=-1)
            self.vocab = self.model.vocab
            self.eos_token = self.model.eos_token

            # 3. Embeddings
            vprint("[3/6] 加载 Embedding 权重...", verbose)
            self.embedding_table = llama.get_token_embeddings_gguf(self.config.decoder_gguf_path)
            
            # 4. Context
            vprint("[4/6] 创建 LLM 上下文...", verbose)
            self.ctx = llama.LlamaContext(
                self.model,
                n_ctx=2048,
                n_batch=2048,
                n_ubatch=self.config.n_ubatch,
                n_threads=self.config.n_threads,
                n_threads_batch=self.config.n_threads_batch
            )
            
            # 5. CTC & Prompt
            vprint("[5/6] 加载 CTC 词表与 Prompt 构建器...", verbose)
            self.ctc_id2token = load_ctc_tokens(self.config.tokens_path)
            self.prompt_builder = PromptBuilder(self.vocab, self.embedding_table)

            # 6. Hotwords
            vprint("[6/6] 初始化热词管理器...", verbose)
            hw_path = self.config.hotwords_path
            if not hw_path:
                # 默认逻辑
                script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                hw_path = os.path.join(script_dir, "hot.txt")
                
            self.hotword_manager = get_hotword_manager(
                hotword_file=Path(hw_path),
                threshold=1.0,
                similar_threshold=self.config.similar_threshold
            )
            self.hotword_manager.load()
            self.hotword_manager.start_file_watcher()
            self.corrector = self.hotword_manager.get_corrector()
            
            self._initialized = True
            vprint(f"✓ 模型加载完成 (耗时: {time.perf_counter() - t_start:.2f}s)", verbose)
            return True
            
        except Exception as e:
            logger.error(f"✗ 初始化失败: {e}", exc_info=True)
            return False

    def cleanup(self):
        if self.hotword_manager:
            self.hotword_manager.stop_file_watcher()
        
        # 显式释放高级对象
        self.ctx = None
        self.model = None
        
        # 尝试清理后端
        try:
            llama.llama_backend_free()
        except:
            pass
            
        self._initialized = False
        logger.info("[ASR] 资源已释放")

