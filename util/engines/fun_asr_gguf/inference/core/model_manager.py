import os
import time
from pathlib import Path

from .. import llama
from ..encoder import AudioEncoder
from ..ctc import CTCDecoder
from ..hotword.manager import get_hotword_manager
from ..utils import vprint
from ..prompt_utils import PromptBuilder
from ..schema import ASREngineConfig

class ModelManager:
    """管理所有模型组件的代码"""
    
    def __init__(self, config: ASREngineConfig):
        self.config = config
        
        # 设置图形加速环境
        if not self.config.vulkan_enable:
            os.environ["VK_ICD_FILENAMES"] = "none"       # 禁止 Vulkan
        if self.config.vulkan_force_fp32:
            os.environ["GGML_VK_DISABLE_F16"] = "1"       # 禁止 VulkanFP16 计算（Intel集显fp16有溢出问题）

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
        self.hotword_manager = None
        self.corrector = None
        self.prompt_builder = None
        
        self._initialized = False

    def initialize(self, verbose: bool = True) -> bool:
        if self._initialized:
            return True
        
        try:
            t_start = time.perf_counter()
            
            # 1. Encoder (ONNX)
            vprint("[1/6] 加载音频编码器 (Encoder)...", verbose)
            self.encoder = AudioEncoder(
                model_path=self.config.encoder_onnx_path,
                dml_enable=self.config.dml_enable,
                pad_to=self.config.pad_to
            )

            # 2. CTC Decoder (ONNX + Search)
            vprint("[2/6] 加载 CTC 推理与解码器...", verbose)
            self.ctc_decoder = CTCDecoder(
                model_path=self.config.ctc_onnx_path,
                tokens_path=self.config.tokens_path,
                dml_enable=self.config.dml_enable,
                pad_to=self.config.pad_to
            )

            # 3. GGUF LLM Decoder
            vprint("[3/6] 加载 GGUF LLM 解码器...", verbose)
            self.model = llama.LlamaModel(self.config.decoder_gguf_path)
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
            
            # 6. Prompt & Hotwords
            vprint("[6/6] 初始化 Prompt 构建器与热词管理器...", verbose)
            self.prompt_builder = PromptBuilder(self.vocab, self.embedding_table)

            hw_path = self.config.hotwords_path
            if not hw_path:
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
            self.corrector.correct("热个身") # 热身
            
            # 绑定校对器到 CTC 解码器
            self.ctc_decoder.corrector = self.corrector

            self._initialized = True
            vprint(f"✓ 模型加载完成 (耗时: {time.perf_counter() - t_start:.2f}s)", verbose)
            return True
            
        except Exception as e:
            vprint(f"✗ 初始化失败: {e}", verbose)
            import traceback
            traceback.print_exc()
            return False

    def cleanup(self):
        if self.hotword_manager:
            self.hotword_manager.stop_file_watcher()
        self.ctx = None
        self.model = None
        self.encoder = None
        self.ctc_decoder = None
        self._initialized = False
        print("[ASR] 资源已释放")

