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
import atexit
from pathlib import Path
from platform import system
from typing import List

import colorama
import typer

from config import ClientConfig as Config, __version__
from util.logger import setup_logger
from util.common.lifecycle import lifecycle

# 确保根目录位置正确，用相对路径加载模型
BASE_DIR = os.path.dirname(__file__)
os.chdir(BASE_DIR)

# 确保终端能使用 ANSI 控制字符
colorama.init()

# 初始化日志系统
logger = setup_logger('client', level=Config.log_level)

# 全局变量，用于跟踪资源状态
_state = None
_shortcut_handler = None
_stream_manager = None
_processor = None  # 结果处理器引用
_main_task = None  # 主任务引用


def request_exit_from_tray():
    """从托盘请求退出"""
    global _main_task, _processor
    logger.info("托盘退出回调函数被调用")

    # 1. 触发通用生命周期退出
    lifecycle.request_shutdown(reason="Tray Icon")

    # 2. 通知处理器退出（立即解除阻塞）
    if _processor:
        logger.debug("正在通知处理器退出...")
        try:
            _processor.request_exit()
        except Exception as e:
            logger.warning(f"通知处理器退出时发生错误: {e}")

    # 3. 取消主任务（确保退出）
    if _main_task and not _main_task.done():
        logger.debug("正在从托盘线程取消主任务...")
        try:
            _main_task.cancel()
        except Exception as e:
            logger.warning(f"取消主任务时发生错误: {e}")


def cleanup_client_resources():
    """
    清理客户端资源的函数
    注册到 LifecycleManager
    """
    logger.info("=" * 50)
    logger.info("开始清理客户端资源...")

    # 解绑快捷键
    if _shortcut_handler:
        try:
            _shortcut_handler.unbind()
            logger.debug("快捷键已解绑")
        except Exception as e:
            logger.warning(f"解绑快捷键时发生错误: {e}")

    # 关闭音频流
    if _stream_manager:
        try:
            _stream_manager.close()
            logger.debug("音频流已关闭")
        except Exception as e:
            logger.warning(f"关闭音频流时发生错误: {e}")

    # 关闭 WebSocket 连接
    if _state and _state.websocket:
        try:
            # 检查是否有 close 方法
            if hasattr(_state.websocket, 'closed'):
                # WebSocket 连接对象，检查 closed 属性
                if not _state.websocket.closed:
                    # 需要在异步上下文中关闭
                    # 注意：如果此时 loop 已关闭，这里会失败。
                    # LifecycleManager 的 cleanup 策略很重要。
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(_state.websocket.close())
                        loop.close()
                        logger.debug("WebSocket 连接已关闭")
                    except Exception:
                        pass
            elif hasattr(_state.websocket, 'close'):
                # 其他连接对象，直接调用 close
                _state.websocket.close()
                logger.debug("WebSocket 连接已关闭")
        except Exception as e:
            logger.warning(f"关闭 WebSocket 连接时发生错误: {e}")

    # 停止托盘图标
    try:
        from util.ui.tray import stop_tray
        stop_tray()
    except Exception as e:
        logger.warning(f"停止托盘图标时发生错误: {e}")

    logger.info("客户端资源清理完成")


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
    global _state, _shortcut_handler, _stream_manager, _processor, _main_task
    
    # 初始化生命周期
    lifecycle.initialize(logger=logger, exit_on_signal=True)

    # 保存当前任务的引用
    _main_task = asyncio.current_task()

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
    _state = get_state()
    _state.initialize()

    # 根据配置决定是否启用托盘图标
    if Config.enable_tray:
        from util.ui.tray import enable_min_to_tray
        icon_path = os.path.join(BASE_DIR, 'assets', 'icon.ico')
        enable_min_to_tray('CapsWriter Client', icon_path, logger=logger, exit_callback=request_exit_from_tray)
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
    _stream_manager = AudioStreamManager(_state)
    _stream_manager.open()

    # 绑定快捷键
    logger.info(f"正在绑定快捷键: {Config.shortcut}")
    _shortcut_handler = ShortcutHandler(_state)
    _shortcut_handler.bind()

    # 清空物理内存工作集（Windows）
    if system() == 'Windows':
        empty_current_working_set()

    logger.info("客户端初始化完成，等待语音输入...")

    # 接收结果
    try:
        processor = ResultProcessor(_state)
        global _processor
        _processor = processor  # 保存引用以便退出时调用

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
    # ... (省略部分未变代码)
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
