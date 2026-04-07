# coding: utf-8
from . import logger
from platform import system
from config_client import ClientConfig as Config
from ..audio import AudioStreamManager
from ..shortcut.shortcut_config import Shortcut
from ..shortcut.shortcut_manager import ShortcutManager


class HardwareManager:
    """
    硬件管理器：负责音频流、快捷键和 UDP 控制等硬件相关资源的初始化与生命周期管理。
    """
    def __init__(self, state):
        self.state = state
        self.stream_manager = None
        self.shortcut_manager = None
        self.udp_controller = None

    def setup_mic_resources(self):
        """初始化麦克风模式特有资源 (音频硬件、快捷键、UDP)"""
        # 1. 音频流管理
        self._setup_audio_stream()

        # 2. 快捷键管理器
        self._setup_shortcuts()

        # 3. UDP 控制 (可选)
        self._setup_udp_control()

        # 4. Windows 周期性内存清理
        self._check_windows_memory_cleanup()

    def _setup_audio_stream(self):
        """配置并开启音频流"""
        logger.info("正在打开音频流...")
        self.stream_manager = AudioStreamManager(self.state)
        self.state.stream_manager = self.stream_manager
        self.stream_manager.open()

    def _setup_shortcuts(self):
        """配置并开启快捷键监听"""
        shortcuts = [Shortcut(**sc) for sc in Config.shortcuts]
        logger.info(f"正在初始化快捷键管理器，共 {len(shortcuts)} 个快捷键")

        self.shortcut_manager = ShortcutManager(self.state, shortcuts)
        self.state.shortcut_manager = self.shortcut_manager
        self.shortcut_manager.start()
        self.state.shortcut_handler = self.shortcut_manager

    def _setup_udp_control(self):
        """配置并开启 UDP 控制器"""
        if Config.udp_control:
            from ..udp.udp_control import UDPController
            logger.info(f"正在启用 UDP 控制，端口: {Config.udp_control_port}")
            self.udp_controller = UDPController(self.shortcut_manager)
            self.state.udp_controller = self.udp_controller
            self.udp_controller.start()

    def _check_windows_memory_cleanup(self):
        """针对 Windows 平台进行初次内存清理"""
        if system() == 'Windows':
            from util.tools.empty_working_set import empty_current_working_set
            try:
                empty_current_working_set()
            except Exception as e:
                logger.debug(f"初始内存清理失败 (非致命): {e}")
