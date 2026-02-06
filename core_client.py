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
from util.common.lifecycle import lifecycle
from util.client.cleanup import cleanup_client_resources, request_exit_from_tray

# 确保根目录位置正确，用相对路径加载模型
BASE_DIR = os.path.dirname(__file__)
os.chdir(BASE_DIR)

# 确保终端能使用 ANSI 控制字符
colorama.init()

# 初始化日志系统
logger = setup_logger('client', level=Config.log_level)

# 全局变量，用于跟踪资源状态
# _state is now managed by get_state() and its attributes
# _shortcut_handler and _stream_manager are now attributes of _state
# _processor is now an attribute of _state
_main_task = None  # 主任务引用


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
    global _main_task
    
    # 初始化生命周期
    lifecycle.initialize(logger=logger, exit_on_signal=True)

    # 保存当前任务的引用
    _main_task = asyncio.current_task()

    from util.client.state import console
    from util.client.output import ResultProcessor
    from util.client.startup import setup_client_components

    logger.info("=" * 50)
    logger.info("CapsWriter Offline Client 正在启动（麦克风模式）")
    logger.info(f"版本: {__version__}")
    logger.info(f"日志级别: {Config.log_level}")

    # 初始化所有组件
    _state = setup_client_components(BASE_DIR)

    # 接收结果
    try:
        processor = ResultProcessor(_state)
        _state.processor = processor # 注入状态以便清理

        # 主循环：只要没收到退出信号，就一直运行
        while not lifecycle.is_shutting_down:
            # 创建处理任务
            process_task = asyncio.create_task(processor.process_loop())
            # 创建等待退出任务
            wait_shutdown = asyncio.create_task(lifecycle.wait_for_shutdown())

            done, pending = await asyncio.wait(
                [process_task, wait_shutdown],
                return_when=asyncio.FIRST_COMPLETED
            )

            # 如果收到退出信号
            if wait_shutdown in done:
                logger.info("主循环检测到退出信号")
                process_task.cancel() # 取消正在进行的处理
                break
            
            # 如果处理任务结束（无论是正常还是异常），继续下一轮
            # 但 ResultProcessor 应该是一个无限循环，除非出错
            if process_task in done:
                # 检查是否有关闭请求（可能是 processor 内部触发）
                if lifecycle.is_shutting_down:
                    break
                # 如果没有请求退出但任务结束了，可能是异常
                try:
                    await process_task
                except Exception as e:
                    logger.error(f"处理循环异常: {e}")
                    # 防止死循环打印日志
                    await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("主任务被取消，正在退出...")
        raise
    except Exception as e:
        logger.error(f"接收结果时发生错误: {e}", exc_info=True)
        raise
    finally:
        # 这里的 finally 主要是为了 handle 协程内的局部资源
        # 全局资源清理交给 lifecycle
        pass


async def main_file(files: List[Path]) -> None:
    """
    文件转录模式主函数
    
    Args:
        files: 要转录的文件列表
    """
    # 初始化生命周期
    lifecycle.initialize(logger=logger, exit_on_signal=True)

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
        if lifecycle.is_shutting_down:
            break

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

    # 注册清理函数
    lifecycle.register_on_shutdown(cleanup_client_resources)

    try:
        asyncio.run(main_mic())
        lifecycle.cleanup() # 正常退出清理
    except KeyboardInterrupt:
        # 有了 lifecycle，通常这一步不会被触发，除非 signal handler 没生效
        # 或者在非 async 阶段被中断
        logger.info("收到停止信号...")
        lifecycle.cleanup()
    except asyncio.CancelledError:
        logger.info("任务已取消...")
        lifecycle.cleanup()
    except Exception as e:
        logger.error(f"运行时错误: {e}", exc_info=True)
        lifecycle.cleanup()
        raise


def init_file(files: List[Path]) -> None:
    """
    初始化并运行文件转录模式
    """
    from util.client.state import console
    
    lifecycle.register_on_shutdown(cleanup_client_resources)

    try:
        asyncio.run(main_file(files))
        lifecycle.cleanup()
    except KeyboardInterrupt:
        logger.info("收到停止信号...")
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
