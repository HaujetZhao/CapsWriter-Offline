"""
GPU 加速管理模块

封装 GPU 显存频率锁定/解锁逻辑，用于减少冷启动延迟。
"""

import subprocess
import time
import ctypes
from config_server import ServerConfig as Config
from . import logger


class GpuBoostManager:
    """
    GPU 加速管理器。

    负责检测管理员权限、执行加速/取消加速命令、检查闲置超时。
    """

    def __init__(self, state):
        self.state = state

    # ── 公开方法 ──────────────────────────────────

    def handle_command(self, task):
        """处理 GPU 加速命令任务。"""
        if task.command != 'gpu_boost' or self.state.gpu_boosted:
            return
        if not self._check_admin():
            logger.warning("非管理员权限，无法执行 GPU 加速命令")
            return

        logger.info(f"GPU 加速命令: {Config.gpu_boost_cmd}")
        subprocess.run(Config.gpu_boost_cmd, shell=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.state.gpu_boosted = True
        self.state.gpu_last_active = 0  # 0 表示已加速但尚未有实际音频任务使用过

    def check_idle(self):
        """GPU 闲置超时检查，超时则取消加速。"""
        if not Config.gpu_boost_enabled or not self.state.gpu_boosted:
            return
        # gpu_last_active = 0 表示刚加速但尚未被实际音频任务使用，不取消
        if self.state.gpu_last_active <= 0:
            return

        idle_time = time.time() - self.state.gpu_last_active
        if idle_time <= Config.gpu_unboost_timeout:
            return

        if not self._check_admin():
            logger.warning("非管理员权限，无法执行 GPU 取消加速命令")
            return

        logger.info(f"GPU 闲置 {idle_time:.0f}s，取消加速: {Config.gpu_unboost_cmd}")
        subprocess.run(Config.gpu_unboost_cmd, shell=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.state.gpu_boosted = False
        self.state.gpu_last_active = 0.0

    # ── 内部方法 ──────────────────────────────────

    @staticmethod
    def _check_admin() -> bool:
        """检测是否以管理员权限运行。"""
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
