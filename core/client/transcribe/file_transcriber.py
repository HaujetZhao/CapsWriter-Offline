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
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from config_client import ClientConfig as Config
from core.client.state import console
from core.client.connection import WebSocketManager
from core.protocol import AudioMessage, RecognitionMessage
from .media_tool import MediaTool
from .result_handler import ResultHandler
from . import logger
from core.tools.token_sync import sync_tokens_from_text

if TYPE_CHECKING:
    from core.client.state import ClientState
    from core.client.app import CapsWriterClient


class FileTranscriber:
    """
    文件转录器
    
    协调转录流程：
    1. 检查环境与文件
    2. 调用 MediaTool 提取音频
    3. 通过 WebSocket 发送数据
    4. 调用 ResultHandler 处理结果
    """
    
    def __init__(self, app: CapsWriterClient, file: Path):
        """
        初始化文件转录器
        
        Args:
            app: 客户端 App 实例
            file: 要转录的文件路径
        """
        self.app = app
        self.file = file
        self.task_id: Optional[str] = None
        self._audio_duration: float = 0.0

    @property
    def state(self) -> ClientState:
        """快捷访问状态单例"""
        return self.app.state

    @property
    def _ws_manager(self) -> 'WebSocketManager':
        """快捷访问桥接到 app.ws"""
        return self.app.ws
    
    async def check(self) -> bool:
        """检查转录条件"""
        # 检查文件是否存在
        if not self.file.exists():
            logger.error(f"文件不存在: {self.file}")
            return False

        # 检查媒体工具环境 (FFmpeg)
        if not MediaTool.check_environment():
            return False

        # 检查服务端连接
        if not await self._ws_manager.connect():
            logger.error("无法连接到服务端")
            return False
        
        
        return True
    
    async def send(self) -> None:
        """发送音频数据到服务端 (异步流式处理)"""
        
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

                message = AudioMessage(
                    task_id=self.task_id,
                    source='file',
                    data=base64.b64encode(data).decode('utf-8'),
                    is_final=False,
                    time_start=time.time(),
                    seg_duration=Config.file_seg_duration,
                    seg_overlap=Config.file_seg_overlap,
                    context=Config.context,
                    language=Config.language,
                )
                if not await self._ws_manager.send(message):
                    raise ConnectionError("消息发送失败，连接可能已断开")

            # 发送结束标志
            final_message = AudioMessage(
                task_id=self.task_id,
                source='file',
                data='',
                is_final=True,
                time_start=time.time(),
                seg_duration=Config.file_seg_duration,
                seg_overlap=Config.file_seg_overlap,
                context=Config.context,
                language=Config.language,
            )
            if not await self._ws_manager.send(final_message):
                raise ConnectionError("结束标志发送失败")
            await process.wait()
            
            if self._audio_duration == 0:
                self._audio_duration = progress 
                console.print(f'    音频长度：{self._audio_duration:.2f}s')

            logger.debug("音频数据发送完成")
            
        except ConnectionError as e:
            logger.error(f"发送数据失败: {e}, 文件: {self.file}")
            if 'process' in locals() and process.returncode is None:
                process.terminate()
            return
        except Exception as e:
            logger.error(f"转录发送异常: {e}", exc_info=True)
            if 'process' in locals() and process.returncode is None:
                process.terminate()
            return
    
    async def receive(self) -> None:
        """接收转录结果"""
        
        try:
            while True:
                msg = await self._ws_manager.receive()
                if not msg:
                    break
                
                console.print(f'    转录进度: {msg.duration:.2f}s', end='\r')
                if msg.is_final:
                    message = msg # 保持变量名兼容后续调用
                    break
        except ConnectionError as e:
            logger.error(f"{e}, 文件: {self.file}")
            return
        except Exception as e:
            logger.error(f"接收消息错误: {e}")
            return

        # 应用热词并同步 tokens
        self._apply_hotwords(message)

        # 调用结果处理器进行保存和格式化
        text_display = ResultHandler.save_results(self.file, message)
        
        process_duration = message.time_complete - message.time_start
        console.print(f'\033[K    处理耗时：{process_duration:.2f}s')
        console.print(f'    识别结果：\n[green]{text_display}')
        
        logger.info(
            f"转录完成: {self.file}, 处理耗时: {process_duration:.2f}s, "
            f"文本长度: {len(text_display)}"
        )

    def _apply_hotwords(self, message: RecognitionMessage) -> None:
        """对识别结果应用热词替换并同步 tokens"""
        text_accu = message.text_accu or message.text
        corrected = text_accu

        # 1. 音素热词替换
        if Config.hot:
            correction = self.app.hotword.get_phoneme_corrector().correct(text_accu, k=10)
            corrected = correction.text
            # 记录热词匹配日志
            for origin, hw, score in correction.matchs:
                logger.info(f"热词匹配: 「{origin}」→「{hw}」(分数={score:.2f})")
                console.print(f'    [cyan]热词匹配:[/] 「{origin}」→「[green]{hw}[/]」(分数={score:.2f})')
            for origin, hw, score in correction.similars:
                logger.debug(f"热词参考: 「{origin}」≈「{hw}」(分数={score:.2f})")

        # 2. 规则替换
        if Config.hot_rule:
            corrected = self.app.hotword.get_rule_corrector().substitute(corrected)

        # 3. 有变化则同步到 tokens 并更新 message
        if corrected != text_accu and message.tokens:
            new_tokens, new_timestamps = sync_tokens_from_text(
                message.tokens, message.timestamps, corrected
            )
            message.text_accu = corrected
            message.text = corrected
            message.tokens = new_tokens
            message.timestamps = new_timestamps
            logger.debug(f"热词修正: {text_accu[:60]} → {corrected[:60]}")

    async def close(self) -> None:
        """释放资源，关闭 WebSocket 连接"""
        await self._ws_manager.close()
