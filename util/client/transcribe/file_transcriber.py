# coding: utf-8
"""
文件转录模块

提供 FileTranscriber 类用于将音视频文件转录为字幕。
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from config import ClientConfig as Config
from util.client.state import console
from util.client.websocket_manager import WebSocketManager
from util.tools import srt_from_txt
from util.logger import get_logger

if TYPE_CHECKING:
    from util.client.state import ClientState

# 日志记录器
logger = get_logger('client')


class FileTranscriber:
    """
    文件转录器
    
    负责将音视频文件转录为字幕：
    - 使用 FFmpeg 提取音频
    - 将音频数据发送到服务端
    - 接收识别结果
    - 生成 SRT 字幕文件
    """
    
    def __init__(self, state: 'ClientState', file: Path):
        """
        初始化文件转录器
        
        Args:
            state: 客户端状态实例
            file: 要转录的文件路径
        """
        self.state = state
        self.file = file
        self._ws_manager = WebSocketManager(state)
        self.task_id: Optional[str] = None
        self._audio_duration: float = 0.0
    
    async def check(self) -> bool:
        """
        检查转录条件
        
        Returns:
            是否满足转录条件
        """
        if not await self._ws_manager.connect():
            console.print('无法连接到服务端')
            logger.error("无法连接到服务端")
            return False
        
        if not self.file.exists():
            console.print(f'文件不存在：{self.file}')
            logger.error(f"文件不存在: {self.file}")
            return False
        
        return True
    
    async def send(self) -> None:
        """发送音频数据到服务端"""
        websocket = self.state.websocket
        
        self.task_id = str(uuid.uuid1())
        console.print(f'\n任务标识：{self.task_id}')
        console.print(f'    处理文件：{self.file}')
        
        logger.info(f"开始转录文件: {self.file}, 任务ID: {self.task_id}")
        
        # 使用 FFmpeg 提取音频
        ffmpeg_cmd = [
            "ffmpeg",
            "-i", str(self.file),
            "-f", "f32le",
            "-ac", "1",
            "-ar", "16000",
            "-",
        ]
        
        console.print('    正在提取音频', end='\r')
        
        try:
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            data = process.stdout.read()
        except Exception as e:
            console.print(f'    [red]提取音频失败: {e}')
            logger.error(f"FFmpeg 提取音频失败: {e}")
            return
        
        self._audio_duration = len(data) / 4 / 16000
        console.print(f'    音频长度：{self._audio_duration:.2f}s')
        logger.debug(f"音频提取完成，时长: {self._audio_duration:.2f}s")
        
        # 分段发送
        offset = 0
        chunk_size = 16000 * 4 * 60
        
        while True:
            chunk_end = offset + chunk_size
            is_final = chunk_end >= len(data)
            
            message = {
                'task_id': self.task_id,
                'seg_duration': Config.file_seg_duration,
                'seg_overlap': Config.file_seg_overlap,
                'is_final': is_final,
                'time_start': time.time(),
                'time_frame': time.time(),
                'source': 'file',
                'data': base64.b64encode(data[offset:chunk_end]).decode('utf-8'),
            }
            
            offset = chunk_end
            progress = min(offset / 4 / 16000, self._audio_duration)
            
            await websocket.send(json.dumps(message))
            console.print(f'    发送进度：{progress:.2f}s', end='\r')
            
            if is_final:
                break
        
        logger.debug("音频数据发送完成")
    
    async def receive(self) -> None:
        """接收转录结果"""
        websocket = self.state.websocket
        
        async for message in websocket:
            message = json.loads(message)
            console.print(f'    转录进度: {message["duration"]:.2f}s', end='\r')
            if message['is_final']:
                break
        
        # 解析结果
        # text: 简单拼接（用于显示）
        # text_accu: 精确拼接（用于字幕生成，带时间戳）
        text_display = message['text']
        text_accu = message.get('text_accu', message['text'])
        text_split = re.sub('[，。？]', '\n', text_accu)
        timestamps = message['timestamps']
        tokens = message['tokens']
        
        # 保存结果文件
        json_filename = self.file.with_suffix('.json')
        txt_filename = self.file.with_suffix('.txt')
        merge_filename = self.file.with_suffix('.merge.txt')
        
        with open(merge_filename, 'w', encoding='utf-8') as f:
            f.write(text_accu)
        with open(txt_filename, 'w', encoding='utf-8') as f:
            f.write(text_split)
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump({'timestamps': timestamps, 'tokens': tokens}, f, ensure_ascii=False)
        
        srt_from_txt.one_task(txt_filename)
        
        process_duration = message['time_complete'] - message['time_start']
        console.print(f'\033[K    处理耗时：{process_duration:.2f}s')
        console.print(f'    识别结果：\n[green]{text_display}')
        
        logger.info(
            f"转录完成: {self.file}, 处理耗时: {process_duration:.2f}s, "
            f"文本长度: {len(text_display)}"
        )
