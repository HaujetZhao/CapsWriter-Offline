# coding: utf-8
"""
文件转录模块

提供 FileTranscriber 类用于将音视频文件转录为字幕。
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
import websockets
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from config_client import ClientConfig as Config
from util.client.state import console
from util.client.websocket_manager import WebSocketManager
from .media_tool import MediaTool
from .result_handler import ResultHandler
from . import logger

if TYPE_CHECKING:
    from util.client.state import ClientState


class FileTranscriber:
    """
    文件转录器
    
    协调转录流程：
    1. 检查环境与文件
    2. 调用 MediaTool 提取音频
    3. 通过 WebSocket 发送数据
    4. 调用 ResultHandler 处理结果
    """
    
    def __init__(self, state: 'ClientState', file: Path):
        self.state = state
        self.file = file
        self._ws_manager = WebSocketManager(state)
        self.task_id: Optional[str] = None
        self._audio_duration: float = 0.0
    
    async def check(self) -> bool:
        """检查转录条件"""
        # 1. 检查媒体工具环境 (FFmpeg)
        if not MediaTool.check_environment():
            return False

        # 2. 检查服务端连接
        if not await self._ws_manager.connect():
            console.print('无法连接到服务端')
            logger.error("无法连接到服务端")
            return False
        
        # 3. 检查文件是否存在
        if not self.file.exists():
            console.print(f'文件不存在：{self.file}')
            logger.error(f"文件不存在: {self.file}")
            return False
        
        return True
    
    async def send(self) -> None:
        """发送音频数据到服务端 (异步流式处理)"""
        websocket = self.state.websocket
        
        self.task_id = str(uuid.uuid1())
        console.print(f'\n任务标识：{self.task_id}')
        console.print(f'    处理文件：{self.file}')
        
        # 1. 预先获取时长
        self._audio_duration = await MediaTool.get_audio_duration(self.file)
        if self._audio_duration > 0:
            console.print(f'    音频长度：{self._audio_duration:.2f}s')
        
        logger.info(f"开始转录文件: {self.file}, 任务ID: {self.task_id}")
        
        # 2. 启动 FFmpeg 进程
        ffmpeg_cmd = MediaTool.build_ffmpeg_cmd(self.file)
        
        try:
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            # 分块大小：1分钟音频 (16000 * 4 * 60 bytes)
            chunk_size = 16000 * 4 * 60
            bytes_sent = 0
            
            while True:
                data = await process.stdout.read(chunk_size)
                if not data:
                    break
                
                bytes_sent += len(data)
                progress = bytes_sent / 4 / 16000
                if self._audio_duration > 0:
                    prog_str = f'    发送进度：{progress:.2f}s / {self._audio_duration:.2f}s'
                else:
                    prog_str = f'    发送进度：{progress:.2f}s'
                console.print(prog_str, end='\r')

                message = {
                    'task_id': self.task_id,
                    'seg_duration': Config.file_seg_duration,
                    'seg_overlap': Config.file_seg_overlap,
                    'is_final': False,
                    'time_start': time.time(),
                    'time_frame': time.time(),
                    'source': 'file',
                    'data': base64.b64encode(data).decode('utf-8'),
                    'context': Config.context,
                }
                await websocket.send(json.dumps(message))

            # 发送结束标志
            final_message = {
                'task_id': self.task_id,
                'seg_duration': Config.file_seg_duration,
                'seg_overlap': Config.file_seg_overlap,
                'is_final': True,
                'time_start': time.time(),
                'time_frame': time.time(),
                'source': 'file',
                'data': '',
                'context': Config.context,
            }
            await websocket.send(json.dumps(final_message))
            await process.wait()
            
            if self._audio_duration == 0:
                self._audio_duration = progress 
                console.print(f'    音频长度：{self._audio_duration:.2f}s')

            logger.debug("音频数据发送完成")
            
        except websockets.exceptions.ConnectionClosed:
            console.print('\n[bold red]错误：与服务端的连接已断开，请检查服务端是否正常运行。[/bold red]')
            logger.error(f"发送数据时连接断开: {self.file}")
            if 'process' in locals() and process.returncode is None:
                process.terminate()
            raise
        except Exception as e:
            console.print(f'\n[red]转录过程中发生错误: {e}')
            logger.error(f"转录发送异常: {e}", exc_info=True)
            if 'process' in locals() and process.returncode is None:
                process.terminate()
            return
    
    async def receive(self) -> None:
        """接收转录结果"""
        websocket = self.state.websocket
        
        try:
            async for message in websocket:
                message = json.loads(message)
                console.print(f'    转录进度: {message["duration"]:.2f}s', end='\r')
                if message['is_final']:
                    break
        except websockets.exceptions.ConnectionClosed:
            console.print('\n[bold red]错误：在等待识别结果时，与服务端的连接已断开。[/bold red]')
            logger.error(f"接收结果时连接断开: {self.file}")
            return
        except Exception as e:
            logger.error(f"接收消息错误: {e}")
            return

        # 调用结果处理器进行保存和格式化
        text_display = ResultHandler.save_results(self.file, message)
        
        process_duration = message['time_complete'] - message['time_start']
        console.print(f'\033[K    处理耗时：{process_duration:.2f}s')
        console.print(f'    识别结果：\n[green]{text_display}')
        
        logger.info(
            f"转录完成: {self.file}, 处理耗时: {process_duration:.2f}s, "
            f"文本长度: {len(text_display)}"
        )
