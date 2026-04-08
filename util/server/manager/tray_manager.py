# coding: utf-8
import os
from .. import logger
from config_server import ServerConfig as Config
from util.tools.lifecycle import lifecycle


class TrayManager:
    """
    托盘管理器：负责系统托盘图标的初始化、菜单构建及回调处理。
    """
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def setup_tray(self):
        """初始化系统托盘图标"""
        if not Config.enable_tray:
            return

        try:
            from util.server.ui import enable_min_to_tray
        except ImportError as e:
            logger.warning(f"托盘模块导入失败，跳过托盘功能: {e}")
            return

        # 获取图标路径
        icon_path = os.path.join(self.base_dir, 'assets', 'icon.ico')
        
        # 启用托盘
        enable_min_to_tray(
            'CapsWriter Server',
            icon_path,
            exit_callback=self._request_exit
        )
        logger.info("托盘图标已启用")

    def _request_exit(self, icon=None, item=None):
        """托盘图标引用的退出回调"""
        logger.info("托盘退出: 用户点击退出菜单，准备清理资源并退出")
        lifecycle.request_shutdown(reason="Tray Icon")
