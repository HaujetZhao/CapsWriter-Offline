# coding: utf-8
"""
CapsWriter Offline 客户端主程序门面类 (Facade)

采用外观模式统一管理音频流 (AudioStreamManager)、
识别结果处理 (ResultProcessor) 和快捷键管理 (ShortcutManager)。
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

import colorama
from .state import get_state
from util.logger import setup_logger
from . import logger
from config_client import ClientConfig as Config, __version__
from util.tools.lifecycle import lifecycle
from .state import console
from .websocket_manager import WebSocketManager
from .manager import (
    ResourceManager, HardwareManager, TrayManager,
    MicRunner, FileRunner
)


class CapsWriterClient:
    """
    CapsWriter 客户端门面类
    
    管理的外部接口简洁：start()。
    """
    def __init__(self):
        # 1. 确定并切换工作目录
        self.base_dir = Path(__file__).parents[2]
        os.chdir(self.base_dir)
            
        # 2. 初始化核心状态单例 (基础设施层)
        self.state = get_state()

        # 3. 初始化各管理器 (职责下放)
        self.resource_manager = ResourceManager(self.state)
        self.hardware_manager = HardwareManager(self.state)
        self.tray_manager = TrayManager(self.state, self.base_dir)
        self.ws_manager = WebSocketManager(self.state)

    def _setup_logging(self):
        """重新配置主日志级别"""
        setup_logger('client', level=Config.log_level)

    def _setup_common(self):
        """
        初始化客户端基础环境 (双模共有)
        """
        # 1. 基础状态启动
        self.state.initialize()
        
        # 2. 日志
        self._setup_logging()

        # 3. 委派公共资源管理 (热词、LLM)
        self.resource_manager.initialize()

    def teardown(self):
        """
        统一释放所有资源（清理顺序：硬件 -> 托盘 -> WebSocket -> State）
        """
        logger.info("正在执行 CapsWriterClient 资源释放...")
        
        # 1. 硬件资源 (音频、快捷键、UDP)
        self.hardware_manager.teardown()
            
        # 2. 托盘资源
        try:
            from .ui import stop_tray
            stop_tray()
        except Exception:
            pass
            
        # 3. 关闭 WebSocket 连接
        self.ws_manager.close_sync()

        # 4. 重置 State
        try:
            self.state.reset()
        except Exception as e:
            logger.warning(f"重置状态时发生错误: {e}")

        logger.info("资源释放完成")
        console.print('[green4]再见！')

    async def _run_async(self):
        """内部异步运行环境"""
        # 3. 基础环境初始化 (双模共有)
        self._setup_common()
        
        files = [Path(f) for f in sys.argv[1:] if os.path.exists(f)]

        if files:
            # 文件转录模式
            runner = FileRunner(self.state, self.ws_manager, files)
        else:
            # 麦克风实时模式
            runner = MicRunner(
                self.state, self.ws_manager, self.hardware_manager, self.tray_manager
            )
        
        # 运行主循环
        await runner.run()

    def start(self):
        """
        启动客户端 (唯一入口)
        
        自动根据命令行参数识别模式。内部管理异步循环。
        """
        # 0. 终端颜色支持
        colorama.init()

        # 1. 注册全局清理函数 (使用实例方法)
        lifecycle.register_on_shutdown(self.teardown)
        
        # 2. 初始化生命周期
        lifecycle.initialize(logger=logger, exit_on_signal=True)
        
        try:
            # 使用 asyncio 运行主异步过程
            asyncio.run(self._run_async())
            
            # 4. 正常完成清理
            lifecycle.cleanup()
            
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("用户请求停止...")
            lifecycle.cleanup()
        except Exception as e:
            logger.error(f"客户端运行出错: {e}", exc_info=True)
            lifecycle.cleanup()
            raise
