# coding: utf-8
import asyncio
from . import logger
from ..ui import TipsDisplay
from config_client import ClientConfig as Config, __version__


class MicRunner:
    """
    麦克风模式运行器：负责麦克风模式下的资源初始化、识别处理器循环及生命周期监控。
    """
    def __init__(self, app):
        self.app = app
        self.processor = None

    @property
    def state(self):
        return self.app.state

    @property
    def ws_manager(self):
        return self.app.ws

    @property
    def tray_manager(self):
        return self.app.tray

    def _setup_resources(self):
        """初始化麦克风模式特有资源 (音频硬件、快捷键、UI 托盘)"""
        # 1. 托盘
        self.tray_manager.setup_tray()

        # 2. UI 提示
        TipsDisplay.show_mic_tips()

        # 3. 开启运行组件 (音频流、快捷键监听)
        logger.info("正在开启硬件资源...")
        self.app.stream.start()
        self.app.shortcut.start()
        
        # 4. 开启 UDP 控制 (如果启用)
        if Config.udp_control:
            self.app.udp.start()

        # 5. 开启后台服务 (热词监视、LLM 监控)
        self.app.hotword.load_all()
        self.app.hotword.start_file_watcher()
        self.app.llm.start()

    async def run(self):
        """麦克风模式主循环"""
        self._setup_resources()

        from ..output import ResultProcessor
        self.processor = ResultProcessor(self.app)
        
        logger.info("=" * 50)
        logger.info("CapsWriter Offline Client 正在启动（麦克风模式）")
        logger.info(f"版本: {__version__}")
        logger.info(f"日志级别: {Config.log_level}")

        while True:
            # 消息处理任务
            await self.processor.process_loop()

            # 无法连接，2秒后重试
            await asyncio.sleep(2)
            

