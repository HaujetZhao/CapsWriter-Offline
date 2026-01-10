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
import signal
import sys
from pathlib import Path
from platform import system
from typing import List

import colorama
import typer

from config import ClientConfig as Config, __version__
from util.logger import setup_logger

# 确保根目录位置正确，用相对路径加载模型
BASE_DIR = os.path.dirname(__file__)
os.chdir(BASE_DIR)

# 确保终端能使用 ANSI 控制字符
colorama.init()

# 初始化日志系统
logger = setup_logger('client', level=Config.log_level)


def _check_macos_permissions() -> None:
    """检查 MacOS 权限设置"""
    if system() == 'Darwin' and not sys.argv[1:]:
        if os.getuid() != 0:
            print('在 MacOS 上需要以管理员启动客户端才能监听键盘活动，请 sudo 启动')
            input('按回车退出')
            sys.exit(1)
        else:
            os.umask(0o000)


async def main_mic() -> None:
    """
    麦克风模式主函数
    
    启动实时语音识别，监听快捷键开始/结束录音。
    """
    from util.client.state import get_state, console
    from util.client.audio import AudioStreamManager
    from util.client.input import ShortcutHandler
    from util.client.processing import ResultProcessor, HotwordManager
    from util.client.ui import TipsDisplay
    from util.llm.llm_handler import init_llm_system
    from util.tools.empty_working_set import empty_current_working_set
    
    logger.info("=" * 50)
    logger.info("CapsWriter Offline Client 正在启动（麦克风模式）")
    logger.info(f"版本: {__version__}")
    logger.info(f"日志级别: {Config.log_level}")
    
    # 初始化状态
    state = get_state()
    state.initialize()
    
    # 根据配置决定是否启用托盘图标
    if Config.enable_tray:
        from util.ui.tray import enable_min_to_tray
        icon_path = os.path.join(BASE_DIR, 'assets', 'icon.ico')
        enable_min_to_tray('CapsWriter Client', icon_path)
        logger.info("托盘图标已启用")
    
    # 显示启动提示
    TipsDisplay.show_mic_tips()
    
    # 加载热词
    logger.info("正在加载热词...")
    hotword_manager = HotwordManager()
    hotword_manager.load_all()
    
    # 启动热词文件监视
    hotword_manager.start_file_watcher()
    
    # 初始化 LLM 系统
    logger.info("正在初始化 LLM 系统...")
    init_llm_system()
    logger.info("LLM 系统初始化完成")
    
    # 打开音频流
    logger.info("正在打开音频流...")
    stream_manager = AudioStreamManager(state)
    stream_manager.open()
    
    # Ctrl-C 关闭音频流，触发自动重启
    def on_signal(signum, frame):
        stream_manager.close()
    signal.signal(signal.SIGINT, on_signal)
    
    # 绑定快捷键
    logger.info(f"正在绑定快捷键: {Config.shortcut}")
    shortcut_handler = ShortcutHandler(state)
    shortcut_handler.bind()
    
    # 清空物理内存工作集（Windows）
    if system() == 'Windows':
        empty_current_working_set()
    
    logger.info("客户端初始化完成，等待语音输入...")
    
    # 接收结果
    try:
        processor = ResultProcessor(state)
        while True:
            await processor.process_loop()
    except Exception as e:
        logger.error(f"接收结果时发生错误: {e}", exc_info=True)
        raise


async def main_file(files: List[Path]) -> None:
    """
    文件转录模式主函数
    
    Args:
        files: 要转录的文件列表
    """
    from util.client.state import get_state, console
    from util.client.transcribe import FileTranscriber, SrtAdjuster
    from util.client.ui import TipsDisplay
    
    logger.info("=" * 50)
    logger.info("CapsWriter Offline Client 正在启动（文件转录模式）")
    logger.info(f"版本: {__version__}")
    logger.info(f"日志级别: {Config.log_level}")
    logger.info(f"待处理文件: {[str(f) for f in files]}")
    
    state = get_state()
    TipsDisplay.show_file_tips()
    
    srt_adjuster = SrtAdjuster()
    
    for file in files:
        logger.info(f"正在处理文件: {file}")
        
        if file.suffix in ['.txt', '.json', '.srt']:
            srt_adjuster.adjust(file)
        else:
            transcriber = FileTranscriber(state, file)
            if await transcriber.check():
                await transcriber.send()
                await transcriber.receive()
        
        logger.info(f"文件处理完成: {file}")
    
    # 关闭连接
    if state.websocket:
        await state.websocket.close()
    
    logger.info("所有文件已处理完成")
    input('\n按回车退出\n')


def init_mic() -> None:
    """初始化并运行麦克风模式"""
    from util.client.state import console
    
    try:
        asyncio.run(main_mic())
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在退出...")
        console.print('再见！')
    except Exception as e:
        logger.error(f"运行时错误: {e}", exc_info=True)
        raise
    finally:
        print('...')


def init_file(files: List[Path]) -> None:
    """
    初始化并运行文件转录模式
    
    Args:
        files: 用 CapsWriter Server 转录音视频文件，生成 srt 字幕
    """
    from util.client.state import console
    
    try:
        asyncio.run(main_file(files))
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在退出...")
        console.print('再见！')
        sys.exit(0)
    except Exception as e:
        logger.error(f"转录文件时发生错误: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # 检查 MacOS 权限
    _check_macos_permissions()
    
    # 如果参数传入文件，那就转录文件
    # 如果没有多余参数，就从麦克风输入
    if sys.argv[1:]:
        typer.run(init_file)
    else:
        init_mic()
