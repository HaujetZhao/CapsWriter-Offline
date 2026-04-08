# coding: utf-8
"""
CapsWriter Offline Client 入口模块

这是语音输入客户端的主程序入口，支持两种模式：
1. 麦克风模式：实时语音输入
2. 文件转录模式：将音视频文件转录为字幕

使用方法：
    python core_client.py              # 麦克风模式
    python core_client.py file1.mp4    # 文件转录模式
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from platform import system
from typing import List

import colorama
import typer

from config_client import ClientConfig as Config, __version__
from util.logger import setup_logger
from util.tools.lifecycle import lifecycle


# 确保根目录位置正确，用相对路径加载模型
BASE_DIR = os.path.dirname(__file__)
os.chdir(BASE_DIR)

# 确保终端能使用 ANSI 控制字符
colorama.init()

# 初始化日志系统 (第一次初始化用于记录启动前期日志)
logger = setup_logger('client', level=Config.log_level)

def run():
    from util.client import CapsWriterClient
    
    # 实例化并启动门面类
    client = CapsWriterClient(BASE_DIR)
    
    try:
        asyncio.run(client.start())
    except Exception as e:
        # 顶层异常捕获，确保日志记录
        logger.error(f"CapsWriter 发生致命错误: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
