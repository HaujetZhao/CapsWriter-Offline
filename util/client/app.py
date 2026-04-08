# coding: utf-8
"""
CapsWriter Offline 客户端主程序门面类 (Facade)

采用外观模式统一管理音频流 (AudioStreamManager)、
识别结果处理 (ResultProcessor) 和快捷键管理 (ShortcutManager)。
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

import colorama
from .state import get_state
from . import logger
from config_client import ClientConfig as Config, __version__
from util.tools.lifecycle import lifecycle
from .state import console
from .websocket_manager import WebSocketManager
from typing import TYPE_CHECKING, Optional
from .manager import (
    TrayManager,
    MicRunner, FileRunner
)
from .audio.stream import AudioStreamManager
from .shortcut.shortcut_manager import ShortcutManager
from .shortcut.shortcut_config import Shortcut

from .udp.udp_control import UDPController

from .hotword import get_hotword_manager, init_hotword_system
from .llm.llm_handler import get_handler, init_llm_system
from .output.text_output import TextOutput
from .diary.diary_writer import DiaryWriter
from .ui import stop_tray
from util.tools.empty_working_set import empty_current_working_set
from platform import system


class CapsWriterClient:
    """
    CapsWriter 客户端门面类
    
    管理的外部接口简洁：start()。
    """
    def __init__(self):
        # 1. 确定并切换工作目录
        self.base_dir = Path(__file__).parents[2]
        os.chdir(self.base_dir)
            
        # 2. 初始化核心状态单例 (基础设施层)
        self.state = get_state()
        self.state.app = self

        # 3. 初始化核心功能组件 (单例持有)
        init_hotword_system()
        init_llm_system()

        self.hotword = get_hotword_manager()
        self.llm = get_handler()
        self.output = TextOutput()
        self.diary = DiaryWriter(base_path=self.base_dir / '日记')

        # 初始化各管理器
        self.ws = WebSocketManager(self)
        self.tray = TrayManager(self)

        # 实例化硬件资源管理组件
        self.stream = AudioStreamManager(self)
        self.shortcut = ShortcutManager(self, [Shortcut(**sc) for sc in Config.shortcuts])
        self.udp = UDPController(self.shortcut)

        # 内存清理
        empty_current_working_set()

    def teardown(self):
        """
        统一释放所有资源（清理顺序：硬件 -> 托盘 -> WebSocket -> State）
        """
        logger.info("正在执行 CapsWriterClient 资源释放...")
        
        # 1. 直接关闭核心硬件资源
        for resource, name in [(self.udp, 'UDP 控制器'), (self.shortcut, '快捷键监听'), (self.stream, '音频流')]:
            try:
                # 统一调用关闭/停止接口 (stop 或 close)
                getattr(resource, 'stop', getattr(resource, 'close', lambda: None))()
                logger.debug(f"{name} 已关闭")
            except Exception as e:
                logger.warning(f"关闭 {name} 时出错: {e}")

        # 2. 托盘资源
        stop_tray()

        # 3. 关闭 WebSocket 连接
        self.ws.close_sync()

        # 4. 重置 State
        try:
            self.state.reset()
        except Exception as e:
            logger.warning(f"重置状态时发生错误: {e}")

        logger.info("资源释放完成")
        console.print('[green4]再见！')

    async def _run_async(self):
        """内部异步运行环境"""
        self.state.initialize()

        files = [Path(f) for f in sys.argv[1:] if os.path.exists(f)]

        if files:
            # 文件转录模式
            runner = FileRunner(self, files)
        else:
            # 麦克风实时模式
            runner = MicRunner(self)
        
        # 运行主循环
        await runner.run()

    def start(self):
        """
        启动客户端 (唯一入口)
        
        自动根据命令行参数识别模式。内部管理异步循环。
        """
        # 0. 终端支持代码
        colorama.init()

        # 1. 注册全局清理函数 (使用实例方法)
        lifecycle.register_on_shutdown(self.teardown)
        
        # 2. 初始化生命周期
        lifecycle.initialize(logger=logger, exit_on_signal=True)
        
        try:
            # 使用 asyncio 运行主异步过程
            asyncio.run(self._run_async())
            
            # 4. 正常完成清理
            lifecycle.cleanup()
            
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("用户请求停止...")
            lifecycle.cleanup()
        except Exception as e:
            logger.error(f"客户端运行出错: {e}", exc_info=True)
            lifecycle.cleanup()
            raise
