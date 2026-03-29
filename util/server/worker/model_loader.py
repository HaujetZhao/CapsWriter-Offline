# coding: utf-8
"""
识模型加载模块

负责 ASR 引擎和标点模型的实例化，支持多种后端引擎的一致性加载。
"""

import time
from util.server.context import console
from util.server.check_model import check_model
from config_server import (
    ServerConfig as Config, 
    ParaformerArgs, ModelPaths, SenseVoiceArgs, 
    FunASRNanoGGUFArgs, Qwen3ASRGGUFArgs
)
from . import logger


class ModelLoader:
    """
    模型加载器
    
    根据系统配置加载对应的 ASR 核心引擎及辅助模型。
    """
    def __init__(self):
        self.recognizer = None
        self.punc_model = None

    def load(self):
        """
        加载模型资源
        
        支持的模型：fun_asr_nano, qwen_asr, sensevoice, paraformer
        """
        # 1. 基础校验 (确保模型文件存在)
        # check_model()
        
        # 2. 延迟导入大型库，避免主进程启动过慢
        with console.status("载入模块中...", spinner="bouncingBall", spinner_style="yellow"):
            import sherpa_onnx
        
        t1 = time.time()
        model_type = Config.model_type.lower()
        logger.info(f"Loader 开始加载语音模型: {model_type}")

        try:
            # 3. 实例化 ASR 引擎
            if model_type == 'fun_asr_nano':
                from util.server.engines.fun_asr_gguf import FunASREngine, ASREngineConfig as FunASRConfig
                config = FunASRConfig(**{k: v for k, v in FunASRNanoGGUFArgs.__dict__.items() if not k.startswith('_')})
                self.recognizer = FunASREngine(config)
            
            elif model_type == 'qwen_asr':
                from util.server.engines.qwen_asr_gguf.asr_engine import QwenASREngine, ASREngineConfig as QwenASRConfig
                config = QwenASRConfig(**{k: v for k, v in Qwen3ASRGGUFArgs.__dict__.items() if not k.startswith('_')})
                self.recognizer = QwenASREngine(config)
            
            elif model_type == 'sensevoice':
                from util.server.engines.sensevoice_onnx import SenseVoiceEngine, ASREngineConfig as SenseVoiceConfig
                config = SenseVoiceConfig(**{k: v for k, v in SenseVoiceArgs.__dict__.items() if not k.startswith('_')})
                self.recognizer = SenseVoiceEngine(config)
            
            elif model_type == 'paraformer':
                from util.server.engines.paraformer_onnx import ParaformerEngine, ASREngineConfig as ParaformerConfig
                config = ParaformerConfig(**{k: v for k, v in ParaformerArgs.__dict__.items() if not k.startswith('_')})
                self.recognizer = ParaformerEngine(config)
            
            else:
                raise ValueError(f"不支持的模型类型: {model_type}")

            # 4. 载入标点预测模型 (目前仅 Paraformer 需要)
            if model_type == 'paraformer':
                punc_cfg = sherpa_onnx.OfflinePunctuationConfig(
                    model=sherpa_onnx.OfflinePunctuationModelConfig(
                        ct_transformer=ModelPaths.punc_model_dir.as_posix()
                    ),
                )
                self.punc_model = sherpa_onnx.OfflinePunctuation(punc_cfg)

            # 5. 加载热词 (如果存在)
            if Config.hotwords_path.exists():
                hotwords = [l.strip() for l in Config.hotwords_path.read_text('utf-8').splitlines() 
                           if l.strip() and not l.strip().startswith('#')]
                self.recognizer.update_hotwords(hotwords)

            logger.info(f"模型加载完成，耗时: {time.time() - t1:.2f}s")
            
        except Exception as e:
            logger.error(f"Loader 加载失败: {str(e)}", exc_info=True)
            raise e

    def cleanup(self):
        """释放模型资源"""
        if self.recognizer and hasattr(self.recognizer, 'cleanup'):
            self.recognizer.cleanup()
        self.recognizer = None
        self.punc_model = None
