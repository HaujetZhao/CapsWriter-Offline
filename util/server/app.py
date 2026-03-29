# coding: utf-8
"""
CapsWriter Offline 服务端主程序门面类 (Facade)

采用外观模式统一管理进程管理器 (ProcessManager) 和网络管理器 (SocketManager)。
该类是整个服务端应用的中心指挥部，负责初始化生命周期、托盘图标、
并协调子进程与 WebSocket 服务的启动与退出。
"""

import os
import asyncio
from util.logger import setup_logger
import logging
from config_server import ServerConfig as Config, __version__
from util.tools.lifecycle import lifecycle
from util.server.cleanup import (
    setup_tray, print_banner, 
    cleanup_server_resources, console
)
from .manager.process_manager import ProcessManager
from .manager.server_manager import SocketManager
from . import logger


class CapsWriterServer:
    """
    CapsWriter 服务端外观类
    
    管理的外部接口极其简洁：start()。
    """
    def __init__(self):
        # 1. 初始化核心状态管理类 (基础设施层)
        self.process_manager = ProcessManager()
        self.socket_manager = SocketManager()
        
        # 2. 基本配置
        self.version = __version__
        self.log_level = Config.log_level

    def _setup_logging(self):
        """配置系统日志级别及第三方库噪音抑制"""
        # 1. 重新配置主日志级别
        setup_logger('server', level=self.log_level)
        
        # 2. 接管并降低 websockets 日志噪音
        ws_logger = logging.getLogger('websockets')
        ws_logger.setLevel(logging.WARNING)
        ws_logger.propagate = False
        for handler in logger.handlers:
            ws_logger.addHandler(handler)

    def _setup_env(self):
        """配置系统生命周期 (信号处理、自动清理、托盘控制)"""
        # 1. 初始化日志
        self._setup_logging()

        # 2. 初始化生命周期
        lifecycle.initialize(logger=logger, exit_on_signal=False)
        
        # 注册全局清理回调
        lifecycle.register_on_shutdown(cleanup_server_resources)
        
        # 注册托盘与 Banner
        setup_tray()
        print_banner()
        
        logger.info("=" * 50)
        logger.info(f"CapsWriter Offline Server (v{self.version}) 准备就绪")

    def start(self):
        """
        同步启动服务端 (主入口)
        
        这是 CoreServer 真正应调用的方法。它将接管进程所有权，直到服务退出。
        """
        # 1. 环境准备
        self._setup_env()
        
        try:
            # 2. 启动识别子进程 (模型加载成功前会阻塞)
            self.process_manager.start_worker()
            
            # 3. 运行异步 WebSocket 服务循环
            # 这会阻塞主线程直到 lifecycle 被标记退出
            asyncio.run(self.socket_manager.run())
            
            # 4. 正常退出后的收尾工作
            lifecycle.cleanup()
                
        except Exception as e:
            logger.error(f"服务端运行时遭遇不可恢复的错误: {str(e)}", exc_info=True)
            lifecycle.request_shutdown()
            lifecycle.cleanup()
            raise e

    def stop(self):
        """主动安全停止服务"""
        logger.info("客户端请求安全停机")
        lifecycle.request_shutdown()
