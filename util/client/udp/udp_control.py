# coding: utf-8
"""
UDP 控制模块

通过 UDP 信号控制录音的开始和停止，使外部程序能够触发语音转录。

命令协议：
- START: 开始录音
- STOP: 停止录音
"""

from __future__ import annotations

import socket
import threading
from typing import TYPE_CHECKING

from config_client import ClientConfig as Config
from . import logger

if TYPE_CHECKING:
    from util.client.shortcut.shortcut_manager import ShortcutManager



class UDPController:
    """
    UDP 控制器
    
    在后台线程监听 UDP 端口，接收控制命令来开始/停止录音。
    """
    
    def __init__(self, shortcut_manager: ShortcutManager):
        """
        初始化 UDP 控制器

        Args:
            shortcut_manager: 快捷键管理器实例，用于调用录音控制方法
        """
        self.manager = shortcut_manager
        self.running = False
        self._thread = None
        self._sock = None
    
    def start(self) -> None:
        """启动 UDP 监听"""
        if self.running:
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._listen, daemon=True, name="UDPController")
        self._thread.start()
        logger.info(f"UDP 控制器已启动，监听端口: {Config.udp_control_port}")
    
    def stop(self) -> None:
        """停止 UDP 监听"""
        self.running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        logger.info("UDP 控制器已停止")
    
    def _listen(self) -> None:
        """监听循环"""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind((Config.udp_control_addr, Config.udp_control_port))
            self._sock.settimeout(0.5)
            
            logger.debug(f"UDP 控制器绑定到 {Config.udp_control_addr}:{Config.udp_control_port}")
            
            while self.running:
                try:
                    data, addr = self._sock.recvfrom(1024)
                    command = data.decode('utf-8').strip().upper()
                    self._handle_command(command, addr)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        logger.error(f"UDP 控制器接收错误: {e}")
        
        except Exception as e:
            logger.error(f"UDP 控制器启动失败: {e}")
        finally:
            if self._sock:
                self._sock.close()
    
    def _handle_command(self, command: str, addr: tuple) -> None:
        """
        处理接收到的命令

        Args:
            command: 命令字符串 (START/STOP)
            addr: 发送方地址
        """
        state = self.manager.state

        if command == 'START':
            if not state.recording:
                logger.info(f"UDP 控制：开始录音 (来自 {addr[0]}:{addr[1]})")
                # 使用第一个可用的快捷键任务启动录音
                if self.manager.tasks:
                    first_task = next(iter(self.manager.tasks.values()))
                    first_task.launch()
            else:
                logger.debug("UDP 控制：忽略 START 命令（已在录音中）")

        elif command == 'STOP':
            if state.recording:
                logger.info(f"UDP 控制：停止录音 (来自 {addr[0]}:{addr[1]})")
                # 停止所有录音任务
                for task in self.manager.tasks.values():
                    if task.is_recording:
                        task.finish()
            else:
                logger.debug("UDP 控制：忽略 STOP 命令（未在录音）")

        else:
            logger.warning(f"UDP 控制：未知命令 '{command}' (来自 {addr[0]}:{addr[1]})")
