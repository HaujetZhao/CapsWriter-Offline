# coding: utf-8
"""
识模型加载模块

负责 ASR 引擎和标点模型的实例化，支持多种后端引擎的一致性加载。
"""

import time
from core.server.state import console
from config_server import (
    ServerConfig as Config, 
    ModelPaths
)
from ..engines.factory import EngineFactory
from ..engines.base import EngineCapabilities
from . import logger


class ModelLoader:
    """
    模型加载器
    
    负责 ASR 引擎和辅助模型（标点、对齐器）的生命周期管理。
    自动根据引擎能力挂载补丁插件。
    """
    def __init__(self):
        self.recognizer = None
        self.punc_model = None
        self.aligner = None

    def load(self):
        """
        加载模型资源
        
        逻辑流程：
        1. 加载 ASR 核心引擎（通过工厂模式）
        2. 扫描引擎能力 (Capabilities)
        3. 自适应挂载缺失能力的插件 (Punc, Aligner)
        """
        # 1. 延迟导入通用库
        with console.status("载入模块中...", spinner="bouncingBall", spinner_style="yellow"):
            import sherpa_onnx
        
        t1 = time.time()
        model_type = Config.model_type.lower()
        logger.info(f"Loader 开始初始化语音系统 (引擎: {model_type})")

        try:
            # 2. 通过工厂实例化 ASR 核心引擎
            self.recognizer = EngineFactory.create_asr_engine(model_type)
            caps = self.recognizer.capabilities
            logger.info(f"引擎加载成功，能力清单: {[c.name for c in caps]}")

            # 3. 智能补丁：如果引擎不自带标点能力，则挂载标点模型
            if EngineCapabilities.PUNC not in caps:
                self._load_punc_model()

            # 4. 智能补丁：如果引擎不自带时间戳能力，则挂载对齐器插件
            if EngineCapabilities.TIMESTAMPS not in caps:
                self._load_align_model()

            # 5. 加载热词 (如果引擎支持 HOTWORDS 能力)
            if EngineCapabilities.HOTWORDS in caps and Config.hotwords_path.exists():
                hotwords = [l.strip() for l in Config.hotwords_path.read_text('utf-8').splitlines() 
                           if l.strip() and not l.strip().startswith('#')]
                self.recognizer.update_hotwords(hotwords)

            logger.info(f"全系统初始化完成，耗时: {time.time() - t1:.2f}s")
            
        except Exception as e:
            logger.error(f"Loader 加载失败: {str(e)}", exc_info=True)
            raise e

    def _load_punc_model(self):
        """加载标点补足模型插件"""
        logger.info("引擎不具备标点能力，正在挂载 PuncEngine 补丁...")
        self.punc_model = EngineFactory.create_punc_engine()

    def _load_align_model(self):
        """加载时间戳对齐补丁代理 (ManagedAlignerProxy)"""
        from ..engines.manager import ManagedAlignerProxy
        logger.info(f"引擎不具备时间戳能力，已挂载 Aligner 托管代理 (闲置卸载时间: {Config.aligner_idle_timeout}s)")
        # 挂载代理而非实体模型，实现按需加载与自动释放
        self.aligner = ManagedAlignerProxy(timeout_sec=Config.aligner_idle_timeout)

    def cleanup(self):
        """释放模型资源"""
        if self.recognizer and hasattr(self.recognizer, 'cleanup'):
            self.recognizer.cleanup()
        if self.aligner and hasattr(self.aligner, 'cleanup'):
            self.aligner.cleanup()
        self.recognizer = None
        self.punc_model = None
        self.aligner = None
