# coding: utf-8
"""
服务端资源清理与辅助模块

负责服务端资源清理、托盘图标和Banner显示。
"""

import os
import asyncio
from rich.console import Console

from config_server import ServerConfig as Config, __version__
from . import logger
from util.common.lifecycle import lifecycle
from util.server.state import get_state
from util.ui.tray import stop_tray

console = Console(highlight=False)

# 计算项目根目录: util/server/cleanup.py -> util/server -> util -> root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def request_exit_from_tray(icon=None, item=None):
    """托盘退出请求回调"""
    logger.info("托盘退出: 用户点击退出菜单")
    lifecycle.request_shutdown(reason="Tray Icon")


def cleanup_server_resources():
    """
    清理服务端资源
    """
    state = get_state()
    
    logger.info("=" * 50)
    logger.info("开始清理服务端资源...")

    # 1. 这里可以关闭所有 WebSocket 连接
    # 但由于 websockets.serve 管理连接，主循环退出时会自动关闭
    # 我们在这个回调里主要关注那些不会自动维护的资源

    # 2. 终止识别子进程
    _recognize_process = state.recognize_process
    if _recognize_process and _recognize_process.is_alive():
        logger.info("正在终止识别子进程...")
        # 尝试优雅终止
        _recognize_process.terminate()
        _recognize_process.join(timeout=5)
        if _recognize_process.is_alive():
            logger.warning("识别进程未能在5秒内退出，强制终止")
            try:
                # 在 Windows 上 Process.kill() 等同于 TerminateProcess
                _recognize_process.kill() 
                _recognize_process.join(timeout=1)
            except Exception as e:
                logger.error(f"强制终止失败: {e}")
        else:
            logger.info("识别进程已正常退出")
    elif _recognize_process:
        logger.info("识别进程已退出")

    # 3. 停止托盘图标
    stop_tray()

    logger.info("服务端资源清理完成")
    console.print('[green4]再见！')


def setup_tray():
    """启用托盘图标"""
    if Config.enable_tray:
        from util.server.ui import enable_min_to_tray
        icon_path = os.path.join(BASE_DIR, 'assets', 'icon.ico')
        enable_min_to_tray('CapsWriter Server', icon_path, exit_callback=request_exit_from_tray)
        logger.info("托盘图标已启用")


def print_banner():
    """打印启动信息"""
    console.line(2)
    console.rule('[bold #d55252]CapsWriter Offline Server'); console.line()
    console.print(f'版本：[bold green]{__version__}', end='\n\n')
    console.print(f'项目地址：[cyan underline]https://github.com/HaujetZhao/CapsWriter-Offline', end='\n\n')
    console.print(f'当前基文件夹：[cyan underline]{BASE_DIR}', end='\n\n')
    console.print(f'绑定的服务地址：[cyan underline]{Config.addr}:{Config.port}', end='\n\n')
