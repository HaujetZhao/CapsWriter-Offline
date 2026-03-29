# coding: utf-8
from typing import Any, Dict, Type, Optional
from .base import BaseEngine
from config_server import (
    ParaformerArgs, SenseVoiceArgs, 
    FunASRNanoGGUFArgs, Qwen3ASRGGUFArgs
)


class EngineFactory:
    """
    引擎工厂类
    
    统一管理所有 ASR 引擎的实例化逻辑。使用延迟加载模式避免启动过慢。
    """

    @staticmethod
    def _load_sensevoice():
        from .sensevoice_onnx.asr_engine import SenseVoiceEngine, SenseVoiceConfig
        return SenseVoiceEngine, SenseVoiceConfig, SenseVoiceArgs

    @staticmethod
    def _load_paraformer():
        from .paraformer_onnx.asr_engine import ParaformerEngine, ParaformerConfig
        return ParaformerEngine, ParaformerConfig, ParaformerArgs

    @staticmethod
    def _load_fun_asr_nano():
        from .fun_asr_gguf.asr_engine import FunASREngine, ASREngineConfig as FunASRConfig
        return FunASREngine, FunASRConfig, FunASRNanoGGUFArgs

    @staticmethod
    def _load_qwen_asr():
        from .qwen_asr_gguf.asr_engine import QwenASREngine, ASREngineConfig as QwenASRConfig
        return QwenASREngine, QwenASRConfig, Qwen3ASRGGUFArgs

    # 引擎名称与加载方法的映射
    _LOADERS = {
        'sensevoice': _load_sensevoice,
        'paraformer': _load_paraformer,
        'fun_asr_nano': _load_fun_asr_nano,
        'qwen_asr': _load_qwen_asr
    }

    @staticmethod
    def create_engine(model_type: str) -> BaseEngine:
        """
        根据模型类型创建对应的引擎实例
        """
        model_type = model_type.lower()
        if model_type not in EngineFactory._LOADERS:
            raise ValueError(f"EngineFactory: 不支持的模型类型 '{model_type}'")

        # 1. 执行延迟加载函数
        loader = EngineFactory._LOADERS[model_type]
        EngineClass, ConfigClass, ArgsObj = loader()
        
        # 2. 从 Args 对象动态构建引擎 Config
        config_data = {
            k: v for k, v in ArgsObj.__dict__.items() 
            if not k.startswith('_')
        }
        config = ConfigClass(**config_data)
        
        # 3. 实例化并返回
        return EngineClass(config)
