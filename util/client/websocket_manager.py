# coding: utf-8
"""
WebSocket 连接管理模块

提供 WebSocketManager 类用于管理与服务端的 WebSocket 连接，
包括连接建立、重连、消息发送和连接状态检查。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from config_client import ClientConfig as Config
from util.protocol import AudioMessage, RecognitionMessage
from . import logger

if TYPE_CHECKING:
    from util.client.state import ClientState
    from .app import CapsWriterClient


class WebSocketManager:
    """
    WebSocket 连接管理器
    
    负责管理与识别服务端的 WebSocket 连接，提供自动重连和
    错误处理功能。
    
    Attributes:
        app: 客户端 App 实例
        max_retries: 最大重试次数
    """
    
    def __init__(self, app: 'CapsWriterClient', max_retries: int = 3):
        """
        初始化 WebSocket 管理器
        
        Args:
            app: 客户端 App 实例
            max_retries: 连接失败时的最大重试次数
        """
        self.app = app
        self.max_retries = max_retries

    @property
    def state(self) -> 'ClientState':
        """快捷访问状态单例"""
        return self.app.state
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.state.is_connected
    
    async def connect(self) -> bool:
        """
        建立 WebSocket 连接
        
        尝试连接到配置的服务端地址，如果失败会自动重试。
        
        Returns:
            连接是否成功
        """
        # 如果已连接，直接返回
        if self.is_connected:
            return True
        
        # 清理旧连接
        if self.state.websocket is not None:
            self.state.websocket = None
        
        url = f"ws://{Config.addr}:{Config.port}"
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"正在连接服务端 {url} (尝试 {attempt}/{self.max_retries})")
                
                self.state.websocket = await websockets.connect(
                    url,
                    subprotocols=["binary"],
                    max_size=None
                )
                
                logger.info(f"WebSocket 连接成功: {url}")
                return True
                
            except ConnectionRefusedError:
                logger.debug(f"连接被拒绝 (尝试 {attempt}/{self.max_retries})")
            except TimeoutError:
                logger.debug(f"连接超时 (尝试 {attempt}/{self.max_retries})")
            except Exception as e:
                logger.debug(f"连接失败: {e} (尝试 {attempt}/{self.max_retries})")
        
        logger.debug(f"连接服务端 {url} 失败，已重试 {self.max_retries} 次 (请检查服务端是否已启动)")
        return False
    
    async def send(self, message: AudioMessage) -> bool:
        """
        发送消息到服务端
        
        Args:
            message: 要发送的 AudioMessage 对象
            
        Returns:
            发送是否成功
        """
        if not self.is_connected:
            logger.warning("无法发送消息：WebSocket 未连接")
            return False
        
        try:
            await self.state.websocket.send(message.to_json())
            return True
            
        except ConnectionClosedError:
            logger.error("发送失败：连接已断开")
            self.state.websocket = None
            return False
            
        except ConnectionClosedOK:
            logger.info("发送失败：连接已正常关闭")
            self.state.websocket = None
            return False
            
        except Exception as e:
            logger.error(f"发送消息时发生错误: {e}", exc_info=True)
            return False
    
    async def receive(self) -> Optional[RecognitionMessage]:
        """
        接收服务端消息
        
        Returns:
            解析后的 RecognitionMessage 对象，如果失败返回 None
        """
        if not self.is_connected:
            logger.warning("无法接收消息：WebSocket 未连接")
            return None
        
        try:
            raw_message = await self.state.websocket.recv()
            data = json.loads(raw_message)
            return RecognitionMessage.from_dict(data)
            
        except ConnectionClosedError:
            logger.error("接收失败：连接已断开")
            self.state.websocket = None
            return None
            
        except ConnectionClosedOK:
            logger.info("接收失败：连接已正常关闭")
            self.state.websocket = None
            return None
            
        except json.JSONDecodeError as e:
            logger.error(f"消息解析失败: {e}")
            return None
            
        except Exception as e:
            logger.error(f"接收消息时发生错误: {e}", exc_info=True)
            return None
    
    async def close(self) -> None:
        """关闭 WebSocket 连接"""
        if self.state.websocket is not None:
            try:
                await self.state.websocket.close()
                logger.info("WebSocket 连接已关闭")
            except Exception as e:
                logger.debug(f"关闭连接时发生错误: {e}")
            finally:
                self.state.websocket = None

    def close_sync(self) -> None:
        """
        从同步上下文（如 teardown）关闭连接
        
        使用 run_coroutine_threadsafe 安全地将关闭操作调度到已有的事件循环。
        如果事件循环未运行，则直接置空连接引用。
        """
        if self.state.websocket is None:
            return

        loop = self.state.loop
        if loop and loop.is_running():
            import asyncio
            asyncio.run_coroutine_threadsafe(self.close(), loop)
            logger.debug("已调度 WebSocket 关闭（threadsafe）")
        else:
            # 事件循环已停止，直接清空引用
            self.state.websocket = None
            logger.debug("事件循环已停，直接置空 WebSocket 引用")
