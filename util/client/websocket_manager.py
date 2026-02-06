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
from . import logger

if TYPE_CHECKING:
    from util.client.state import ClientState



class WebSocketManager:
    """
    WebSocket 连接管理器
    
    负责管理与识别服务端的 WebSocket 连接，提供自动重连和
    错误处理功能。
    
    Attributes:
        state: 客户端状态实例
        max_retries: 最大重试次数
    """
    
    def __init__(self, state: 'ClientState', max_retries: int = 3):
        """
        初始化 WebSocket 管理器
        
        Args:
            state: 客户端状态实例
            max_retries: 连接失败时的最大重试次数
        """
        self.state = state
        self.max_retries = max_retries
    
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
                logger.warning(f"连接被拒绝 (尝试 {attempt}/{self.max_retries})")
            except TimeoutError:
                logger.warning(f"连接超时 (尝试 {attempt}/{self.max_retries})")
            except Exception as e:
                logger.error(f"连接失败: {e} (尝试 {attempt}/{self.max_retries})")
        
        logger.error(f"无法连接到服务端 {url}，已重试 {self.max_retries} 次")
        return False
    
    async def send(self, message: dict) -> bool:
        """
        发送消息到服务端
        
        Args:
            message: 要发送的消息字典，会被序列化为 JSON
            
        Returns:
            发送是否成功
        """
        if not self.is_connected:
            logger.warning("无法发送消息：WebSocket 未连接")
            return False
        
        try:
            await self.state.websocket.send(json.dumps(message))
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
    
    async def receive(self) -> Optional[dict]:
        """
        接收服务端消息
        
        Returns:
            解析后的消息字典，如果失败返回 None
        """
        if not self.is_connected:
            logger.warning("无法接收消息：WebSocket 未连接")
            return None
        
        try:
            message = await self.state.websocket.recv()
            return json.loads(message)
            
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
