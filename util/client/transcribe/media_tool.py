# coding: utf-8
import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from util.client.state import console
from . import logger

class MediaTool:
    """媒体工具类：负责 FFmpeg 相关操作"""

    @staticmethod
    def check_environment() -> bool:
        """检查 FFmpeg 和 ffprobe 环境"""
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
            
        return True

    @staticmethod
    async def get_audio_duration(file: Path) -> float:
        """获取音视频文件时长"""
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(file)
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

    @staticmethod
    def build_ffmpeg_cmd(file: Path) -> List[str]:
        """构建提取音频的 FFmpeg 命令"""
        return [
            "ffmpeg", "-i", str(file),
            "-f", "f32le", "-ac", "1", "-ar", "16000", "-"
        ]
