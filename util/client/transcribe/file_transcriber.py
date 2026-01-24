# coding: utf-8
"""
文件转录模块

提供 FileTranscriber 类用于将音视频文件转录为字幕。
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import subprocess
import time
import uuid
import websockets
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from config import ClientConfig as Config
from util.client.state import console
from util.client.websocket_manager import WebSocketManager
from util.tools import srt_from_txt
from . import logger

if TYPE_CHECKING:
    from util.client.state import ClientState



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
        # 1. 检查 FFmpeg 和 ffprobe 环境
        import shutil
        ffmpeg_path = shutil.which('ffmpeg')
        ffprobe_path = shutil.which('ffprobe')
        
        if ffmpeg_path is None:
            console.print('\n[bold red]错误：未检测到 FFmpeg 环境[/bold red]')
            console.print('    文件转录功能依赖 FFmpeg 来提取音视频中的音频。')
            console.print('    [cyan]建议处理方案：[/cyan]')
            console.print('    1. 请确保已安装 FFmpeg 并将其 [bold]bin[/bold] 目录添加到系统环境变量 [bold]Path[/bold] 中。')
            console.print('    2. 或者将 [bold]ffmpeg.exe[/bold] 放置在程序根目录下。')
            console.print('    3. 也可以前往官方下载：[u]https://ffmpeg.org/download.html[/u]\n')
            logger.error("未检测到 FFmpeg 环境，无法进行文件转录")
            return False
            
        if ffprobe_path is None:
            console.print('\n[bold yellow]提示：未检测到 ffprobe 环境[/bold yellow]')
            console.print('    程序将无法预先获取文件时长，进度条将只显示当前已发送时长。')
            console.print('    [cyan]建议：[/cyan]若需完整进度条，请在安装 FFmpeg 时确保 bin 目录下包含 ffprobe.exe。\n')
            logger.warning("未检测到 ffprobe 环境，进度显示将受到限制")

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
    
    async def _get_audio_duration(self) -> float:
        """使用 ffprobe 获取音视频文件的确切时长"""
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(self.file)
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                return float(stdout.decode().strip())
        except Exception as e:
            logger.warning(f"无法通过 ffprobe 获取时长: {e}")
        return 0.0

    async def send(self) -> None:
        """发送音频数据到服务端 (异步流式处理)"""
        websocket = self.state.websocket
        
        self.task_id = str(uuid.uuid1())
        console.print(f'\n任务标识：{self.task_id}')
        console.print(f'    处理文件：{self.file}')
        
        # 1. 预先获取时长以便显示进度
        self._audio_duration = await self._get_audio_duration()
        if self._audio_duration > 0:
            console.print(f'    音频长度：{self._audio_duration:.2f}s')
        
        logger.info(f"开始转录文件: {self.file}, 任务ID: {self.task_id}")
        
        # 2. 异步流式提取并发送
        ffmpeg_cmd = [
            "ffmpeg", "-i", str(self.file),
            "-f", "f32le", "-ac", "1", "-ar", "16000", "-"
        ]
        
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
                # 异步读取一块数据
                data = await process.stdout.read(chunk_size)
                if not data:
                    break
                
                # 探测下一块是否还有数据，以确定是否为结束片段
                # 注意：这里我们通过读取到的长度是否小于 chunk_size 
                # 或者尝试再读 1 字节来辅助判断（更稳妥的是直接发，直到读空）
                # 这里简单处理：只要本次读到了数据就发出去，真正的 is_final 由循环结束后的空包确定
                
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
            }
            await websocket.send(json.dumps(final_message))
            await process.wait()
            
            if self._audio_duration == 0:
                self._audio_duration = progress # 回填时长供 receive 使用
                console.print(f'    音频长度：{self._audio_duration:.2f}s')

            logger.debug("音频数据发送完成")
            
        except websockets.exceptions.ConnectionClosed:
            console.print('\n[bold red]错误：与服务端的连接已断开，请检查服务端是否正常运行。[/bold red]')
            logger.error(f"发送数据时连接断开: {self.file}")
            # 尝试杀掉 FFmpeg 进程
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

        # 解析结果
        # text: 简单拼接（用于显示）
        # text_accu: 精确拼接（用于字幕生成，带时间戳）
        text_display = message['text']
        text_accu = message.get('text_accu', message['text'])
        text_split = re.sub('[，。？]', '\n', text_accu)
        timestamps = message['timestamps']
        tokens = message['tokens']
        
        # 按照配置保存结果文件
        json_filename = self.file.with_suffix('.json')
        txt_filename = self.file.with_suffix('.txt')
        merge_filename = self.file.with_suffix('.merge.txt')
        
        # 1. 保存 merge.txt (如果启用)
        if Config.file_save_merge:
            with open(merge_filename, 'w', encoding='utf-8') as f:
                f.write(text_accu)
            logger.debug(f"保存合并文本: {merge_filename}")

        # 2. 保存 txt 或为了生成 srt 而暂时保存 txt
        if Config.file_save_txt or Config.file_save_srt:
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write(text_split)
            logger.debug(f"保存切分文本: {txt_filename}")

        # 3. 保存 json (如果启用)
        if Config.file_save_json:
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump({'timestamps': timestamps, 'tokens': tokens}, f, ensure_ascii=False)
            logger.debug(f"保存 JSON 结果: {json_filename}")
        
        # 4. 生成 srt (如果启用)
        if Config.file_save_srt:
            srt_from_txt.one_task(txt_filename)
        
        # 5. 清理中间生成的 txt (如果用户不想要)
        if not Config.file_save_txt and txt_filename.exists():
            try:
                txt_filename.unlink()
                logger.debug(f"清理中间 TXT 文件: {txt_filename}")
            except Exception as e:
                logger.warning(f"清理中间 TXT 文件失败: {e}")
        
        process_duration = message['time_complete'] - message['time_start']
        console.print(f'\033[K    处理耗时：{process_duration:.2f}s')
        console.print(f'    识别结果：\n[green]{text_display}')
        
        logger.info(
            f"转录完成: {self.file}, 处理耗时: {process_duration:.2f}s, "
            f"文本长度: {len(text_display)}"
        )
