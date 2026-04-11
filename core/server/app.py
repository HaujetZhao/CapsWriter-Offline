# coding: utf-8
"""
CapsWriter Offline 服务端主程序门面类 (Facade)

采用外观模式统一管理进程管理器 (ProcessManager) 和网络管理器 (SocketManager)。
该类是整个服务端应用的中心指挥部，负责初始化生命周期、托盘图标、
并协调子进程与 WebSocket 服务的启动与退出。
"""

import os
import asyncio
import logging
from pathlib import Path
from core.logger import setup_logger
from config_server import ServerConfig as Config, __version__
from .state import ServerState, console
from core.tools.signal_handler import register_signal
from .worker.process_manager import ProcessManager
from .connection.server_manager import SocketManager
from .ui.tray_manager import TrayManager
from . import logger
import colorama 

class CapsWriterServer:
    """
    CapsWriter 服务端外观类
    
    管理的外部接口极其简洁：start()。
    """
    def __init__(self):
        # 确保正确的工作目录
        self.base_dir = Path(__file__).parents[2]
        os.chdir(self.base_dir)

        # 初始化事件循环
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # 初始化状态容器
        self.state = ServerState(app=self)

        # 基本配置与组件实例化
        self.process_manager = ProcessManager(self)
        self.socket_manager = SocketManager(self)
        self.tray_manager = TrayManager(self)

        self.version = __version__
        self.is_alive = False


    def _print_banner(self):
        """打印启动信息"""
        console.line(2)
        console.rule('[bold #d55252]CapsWriter Offline Server'); console.line()
        console.print(f'版本：[bold green]{self.version}', end='\n\n')
        console.print(f'项目地址：[cyan underline]https://github.com/HaujetZhao/CapsWriter-Offline', end='\n\n')
        console.print(f'当前基文件夹：[cyan underline]{self.base_dir}', end='\n\n')
        console.print(f'绑定的服务地址：[cyan underline]{Config.addr}:{Config.port}', end='\n\n')

    def stop(self):
        """
        清理服务端资源
        """
        # 防连续触发
        if not self.is_alive: return
        self.is_alive = False 

        logger.info("=" * 50)
        logger.info("开始清理服务端资源...")

        self.state.queue_out.put(None)
        
        # 0. 停止协程
        self.loop.stop()


        # 1. 终止识别子进程
        self.process_manager.stop()

        # 2. 停止托盘图标
        try:
            from core.ui.tray import stop_tray
            stop_tray()
        except:
            pass

        logger.info("服务端资源清理完成")
        console.print('[green4]再见！')


    def start(self):
        """
        同步启动服务端 (主入口)
        
        注册信号处理、拉起子进程并进入网络服务监听循环。
        """
        # 防连续触发
        if self.is_alive: return
        self.is_alive = True

        # 注册退出信号处理
        register_signal(self.stop)

        # 托盘图标
        self.tray_manager.setup_tray()
        self._print_banner()

        # 拉起识别子进程
        self.process_manager.start_worker()
        
        # 开启网络服务监听 (接管当前线程直至退出)
        try:
            self.loop.run_until_complete(self.socket_manager.run()) 
        except RuntimeError:
            pass