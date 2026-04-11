# coding: utf-8
"""
WebSocket 管理器 (SocketManager)

负责维护 ASR 服务器的异步通讯层，包括 WebSocket Server 的生命周期管理、
心跳监控、数据发送任务的编排。
"""

import asyncio
import functools
import websockets
from config_server import ServerConfig as Config
from core.server.ws_recv import ws_recv
from core.server.ws_send import ws_send
from . import logger


class SocketManager:
    """
    WebSocket 网络管理器
    
    负责拉起并维护 WebSocket Server 以及识别结果的异步发送任务。
    """
    def __init__(self, app):
        self.app = app
        self._is_running = False

    async def run(self):
        """
        启动 WebSocket 网络服务
        """
        if self._is_running: return
        self._is_running = True

        loop = asyncio.get_running_loop()
        
        # 1. 优化守护线程执行器 (防止阻塞事件循环)
        from core.tools.daemon_executor import SimpleDaemonExecutor
        loop.set_default_executor(SimpleDaemonExecutor())

        # 2. 准备连接处理器 (注入 app 引用)
        handler = functools.partial(ws_recv, app=self.app)

        # 3. 启动服务
        logger.info(f"正在拉起 WebSocket 服务 (监听: {Config.addr}:{Config.port})")
        
        async with websockets.serve(
            handler,
            Config.addr,
            Config.port,
            subprotocols=["binary"],
            max_size=None
        ):
            # 4. 进入识别结果发送循环 (作为主阻塞任务)
            logger.info("WebSocket 发送协程已就绪")
            await ws_send(self.app)
            
        self._is_running = False
        logger.info("SocketManager: WebSocket 服务已退出")
