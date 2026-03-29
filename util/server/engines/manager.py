import time
from .factory import EngineFactory
from .base import BaseAlignEngine
from . import logger

class ManagedAlignerProxy(BaseAlignEngine):
    """
    对齐引擎托管代理
    
    实现“懒加载”与“闲置卸载”逻辑。
    由于 TaskHandler 是单线程同步的，此处无需线程锁。
    """

    def __init__(self, timeout_sec=600):
        self.engine = None
        self.timeout = timeout_sec
        self.last_active = time.time()
        self.is_processing = False

    def align(self, audio, text, **kwargs):
        # 1. 懒加载
        if self.engine is None:
            logger.info("🚩 [AlignerProxy] 检测到文件任务需求，正在即时加载对齐引擎...")
            self.engine = EngineFactory.create_align_engine()
        
        # 2. 标记运行并执行
        self.is_processing = True
        try:
            res = self.engine.align(audio, text, **kwargs)
            self.last_active = time.time()
            return res
        finally:
            self.is_processing = False

    def check_idle(self):
        """ 闲置检查：由外部循环在空闲时调用 """
        if self.timeout <= 0 or self.is_processing or self.engine is None:
            return

        idle_time = time.time() - self.last_active
        if idle_time > self.timeout:
            logger.info(f"🚩 [AlignerProxy] 对齐引擎已闲置 {idle_time:.0f}s，正在自动卸载以释放显存...")
            self.engine.cleanup()
            self.engine = None

    def cleanup(self):
        if self.engine:
            self.engine.cleanup()
            self.engine = None
