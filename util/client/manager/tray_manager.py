# coding: utf-8
import os
from . import logger
from config_client import ClientConfig as Config
from util.tools.lifecycle import lifecycle


class TrayManager:
    """
    托盘管理器：负责系统托盘图标的初始化、菜单构建及回调处理。
    """
    def __init__(self, state, base_dir: str):
        self.state = state
        self.base_dir = base_dir

    def setup_tray(self):
        """初始化系统托盘图标"""
        if not Config.enable_tray:
            return

        try:
            from ..ui import enable_min_to_tray
        except ImportError as e:
            logger.warning(f"托盘模块导入失败，跳过托盘功能: {e}")
            return

        # 获取图标路径
        icon_path = os.path.join(self.base_dir, 'assets', 'icon.ico')
        
        # 启用托盘
        enable_min_to_tray(
            'CapsWriter Client',
            icon_path,
            exit_callback=self._request_exit,
            more_options=[
                ('📋 复制结果', self._copy_last_result),
                ('📝 上下文', self._add_context),
                ('✨ 添加热词', self._add_hotword),
                ('🛠️ 添加纠错', self._add_rectify),
                ('🧹 清除记忆', self._clear_memory),
                ('🔄 重启音频', self._restart_audio),
            ]
        )
        logger.info("托盘图标已启用")

    def _restart_audio(self):
        """重启音频流回调"""
        if self.state.stream_manager:
            self.state.stream_manager.reopen()
            logger.info("用户请求重启音频")

    def _clear_memory(self):
        """清除 LLM 对话历史回调"""
        from ..llm.llm_handler import clear_llm_history
        from ..ui import toast
        clear_llm_history()
        toast("清除成功：已清除所有角色的对话历史记录", duration=3000, bg="#075077")

    def _add_hotword(self):
        """打开添加热词界面回调"""
        try:
            from ..ui import on_add_hotword
            on_add_hotword()
        except ImportError as e:
            logger.warning(f"无法导入热词菜单处理器: {e}")

    def _add_rectify(self):
        """打开添加纠错界面回调"""
        try:
            from ..ui import on_add_rectify_record
            on_add_rectify_record()
        except ImportError as e:
            logger.warning(f"无法导入纠错菜单处理器: {e}")

    def _add_context(self):
        """打开编辑上下文界面回调"""
        try:
            from ..ui import on_edit_context
            on_edit_context()
        except ImportError as e:
            logger.warning(f"无法导入上下文菜单处理器: {e}")

    def _copy_last_result(self):
        """复制最后一次识别结果到剪贴板回调"""
        text = self.state.last_output_text
        if text:
            from ..llm.llm_clipboard import copy_to_clipboard
            copy_to_clipboard(text)

    def _request_exit(self, icon=None, item=None):
        """托盘图标引用的退出回调"""
        logger.info("托盘退出: 用户点击退出菜单，准备清理资源并退出")
        lifecycle.request_shutdown(reason="Tray Icon")
