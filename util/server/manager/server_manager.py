# coding: utf-8
"""
WebSocket 管理器 (SocketManager)

负责维护 ASR 服务器的异步通讯层，包括 WebSocket Server 的生命周期管理、
心跳监控、数据发送任务的编排。
"""

import asyncio
import websockets
from config_server import ServerConfig as Config
from util.server.ws_recv import ws_recv
from util.server.ws_send import ws_send
from util.tools.lifecycle import lifecycle
from . import logger


class SocketManager:
    """
    WebSocket 网络管理器
    
    管理的异步任务包括：接收连接 (ws_recv)、数据发送循环 (ws_send)。
    """
    def __init__(self):
        self._server_task = None
        self._send_task = None
        self._shutdown_task = None

    async def run(self):
        """
        异步运行 WebSocket 服务
        
        执行全流程：注册生命周期循环 -> 启动业务任务 -> 维持服务 -> 优雅停止。
        """
        loop = asyncio.get_running_loop()
        
        # 1. 向生命周期管理器同步当前事件循环 (规范初始化)
        lifecycle.initialize(loop=loop, logger=logger)
        
        if lifecycle.is_shutting_down:
            logger.info("SocketManager: 检测到系统正在停机，放弃启动")
            return

        # 2. 优化守护线程执行器 (防止阻塞事件循环)
        from util.tools.daemon_executor import SimpleDaemonExecutor
        loop.set_default_executor(SimpleDaemonExecutor())

        # 3. 启动 WebSocket 服务器
        logger.info(f"正在拉起 WebSocket 服务 (监听: {Config.addr}:{Config.port})")
        async with websockets.serve(
            ws_recv,
            Config.addr,
            Config.port,
            subprotocols=["binary"],
            max_size=None
        ) as server:
            
            # 4. 创建识别结果回传任务 (全局任务)
            self._send_task = asyncio.create_task(ws_send())
            
            # 5. 创建生命周期监控任务 (阻塞等待直到收到退出信号)
            # 如果系统已经标记关闭，确保触发退出
            if lifecycle.is_shutting_down:
                lifecycle.request_shutdown("Startup conflict")
                
            self._shutdown_task = asyncio.create_task(lifecycle.wait_for_shutdown())

            # 6. 进入主监听阻塞状态
            done, pending = await asyncio.wait(
                [self._send_task, self._shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            # 7. 开始优雅关闭流程
            if self._shutdown_task in done:
                logger.info("SocketManager: 收到系统停机指令，正在取消所有网络任务...")
                
            # 取消所有尚未完成的任务
            for task in pending:
                task.cancel()
                try:
                    # 允许任务处理 CancelledError
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"任务取消时遇到异常: {str(e)}")
            
            # 检查发送任务是否还有未捕获错误
            if self._send_task in done and not self._send_task.cancelled():
                try:
                    await self._send_task
                except Exception as e:
                    logger.error(f"SocketManager: 发送任务意外崩溃: {str(e)}")

        logger.info("SocketManager: WebSocket 服务已彻底退出")
