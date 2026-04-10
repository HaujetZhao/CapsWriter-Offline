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
from util.server.ws_recv import ws_recv
from util.server.ws_send import ws_send
from . import logger


class SocketManager:
    """
    WebSocket 网络管理器
    
    管理的异步任务包括：接收连接 (ws_recv)、数据发送循环 (ws_send)。
    """
    def __init__(self, app):
        self._server_task = None
        self._send_task = None
        self._shutdown_task = None
        self.app = app

    async def run(self):
        """
        异步运行 WebSocket 服务
        
        执行全流程：注册生命周期循环 -> 启动业务任务 -> 维持服务 -> 优雅停止。
        """
        loop = asyncio.get_running_loop()
        

        # 2. 优化守护线程执行器 (防止阻塞事件循环)
        from util.tools.daemon_executor import SimpleDaemonExecutor
        loop.set_default_executor(SimpleDaemonExecutor())

        # 3. 启动 WebSocket 服务器
        logger.info(f"正在拉起 WebSocket 服务 (监听: {Config.addr}:{Config.port})")
        
        # 使用 partial 将 app 注入 ws_recv
        handler = functools.partial(ws_recv, app=self.app)

        async with websockets.serve(
            handler,
            Config.addr,
            Config.port,
            subprotocols=["binary"],
            max_size=None
        ) as server:
            
            # 4. 创建识别结果回传任务 (全局任务)
            await ws_send(self.app)
            
        logger.info("SocketManager: WebSocket 服务已彻底退出")
