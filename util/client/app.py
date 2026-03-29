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
from platform import system

from util.client.state import get_state
from util.logger import setup_logger
from . import logger
from config_client import ClientConfig as Config, __version__
from util.tools.lifecycle import lifecycle
from util.client.cleanup import cleanup_client_resources, request_exit_from_tray


class CapsWriterClient:
    """
    CapsWriter 客户端门面类
    
    管理的外部接口简洁：start()。
    """
    def __init__(self, base_dir: str = None):
        # 1. 确定工作目录
        self.base_dir = base_dir or os.getcwd()
        if not os.path.exists(self.base_dir):
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            
        # 2. 初始化核心状态单例 (基础设施层)
        self.state = get_state()
        self.version = __version__
        self.log_level = Config.log_level
        self._main_task = None

    def _setup_logging(self):
        """重新配置主日志级别"""
        setup_logger('client', level=self.log_level)

    def _setup_tray(self):
        """
        初始化系统托盘图标
        """
        if not Config.enable_tray:
            return

        try:
            from util.client.ui import enable_min_to_tray, toast
        except ImportError as e:
            logger.warning(f"托盘模块导入失败，跳过托盘功能: {e}")
            return

        def restart_audio():
            if self.state.stream_manager:
                self.state.stream_manager.reopen()
                logger.info("用户请求重启音频")

        def clear_memory():
            from util.client.llm.llm_handler import clear_llm_history
            clear_llm_history()
            toast("清除成功：已清除所有角色的对话历史记录", duration=3000, bg="#075077")

        def add_hotword():
            try:
                from util.client.ui import on_add_hotword
                on_add_hotword()
            except ImportError as e:
                logger.warning(f"无法导入热词菜单处理器: {e}")

        def add_rectify():
            try:
                from util.client.ui import on_add_rectify_record
                on_add_rectify_record()
            except ImportError as e:
                logger.warning(f"无法导入纠错菜单处理器: {e}")

        def add_context():
            try:
                from util.client.ui import on_edit_context
                on_edit_context()
            except ImportError as e:
                logger.warning(f"无法导入上下文菜单处理器: {e}")

        def copy_last_result():
            text = self.state.last_output_text
            if text:
                from util.client.llm.llm_clipboard import copy_to_clipboard
                copy_to_clipboard(text)

        icon_path = os.path.join(self.base_dir, 'assets', 'icon.ico')
        enable_min_to_tray(
            'CapsWriter Client',
            icon_path,
            exit_callback=request_exit_from_tray,
            more_options=[
                ('📋 复制结果', copy_last_result),
                ('📝 上下文', add_context),
                ('✨ 添加热词', add_hotword),
                ('🛠️ 添加纠错', add_rectify),
                ('🧹 清除记忆', clear_memory),
                ('🔄 重启音频', restart_audio),
            ]
        )
        logger.info("托盘图标已启用")

    def _setup_env(self):
        """
        初始化客户端各个组件及环境
        """
        # 1. 基础状态启动
        self.state.initialize()
        
        # 2. 日志
        self._setup_logging()

        # 3. 托盘
        self._setup_tray()

        # 4. UI 提示
        from util.client.ui import TipsDisplay
        TipsDisplay.show_mic_tips()

        # 5. 热词管理
        logger.info("正在加载热词...")
        from util.client.hotword import get_hotword_manager
        hotword_files = {
            'hot': Path('hot.txt'),
            'rule': Path('hot-rule.txt'),
            'rectify': Path('hot-rectify.txt'),
        }
        hotword_manager = get_hotword_manager(
            hotword_files=hotword_files,
            threshold=Config.hot_thresh,
            similar_threshold=Config.hot_similar,
            rectify_threshold=Config.hot_rectify
        )
        hotword_manager.load_all()
        hotword_manager.start_file_watcher()

        # 6. LLM 系统
        from util.client.llm.llm_handler import init_llm_system
        logger.info("正在初始化 LLM 系统...")
        init_llm_system()
        logger.info("LLM 系统初始化完成")

        # 7. 音频流管理
        from util.client.audio import AudioStreamManager
        logger.info("正在打开音频流...")
        stream_manager = AudioStreamManager(self.state)
        self.state.stream_manager = stream_manager
        stream_manager.open()

        # 8. 快捷键管理器
        from util.client.shortcut.shortcut_config import Shortcut
        from util.client.shortcut.shortcut_manager import ShortcutManager
        shortcuts = [Shortcut(**sc) for sc in Config.shortcuts]
        logger.info(f"正在初始化快捷键管理器，共 {len(shortcuts)} 个快捷键")

        shortcut_manager = ShortcutManager(self.state, shortcuts)
        self.state.shortcut_manager = shortcut_manager
        shortcut_manager.start()
        self.state.shortcut_handler = shortcut_manager

        # 9. UDP 控制（可选）
        if Config.udp_control:
            from util.client.udp.udp_control import UDPController
            logger.info(f"正在启用 UDP 控制，端口: {Config.udp_control_port}")
            udp_controller = UDPController(shortcut_manager)
            self.state.udp_controller = udp_controller
            udp_controller.start()

        # 10. Windows 内存整理
        if system() == 'Windows':
            from util.tools.empty_working_set import empty_current_working_set
            empty_current_working_set()

        logger.info("客户端初始化完成，等待语音输入...")

    def start(self):
        """留给下一阶段实现循环分发"""
        pass
