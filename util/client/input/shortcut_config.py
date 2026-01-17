# coding: utf-8
"""
快捷键配置数据类

定义 Shortcut 数据结构，用于配置快捷键行为。
避免循环导入：此模块不依赖 config.py。
"""

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class Shortcut:
    """
    快捷键配置类

    Attributes:
        key: 快捷键名称（支持 pynput 格式，如 'caps_lock', 'a', 'f1', 'ctrl+shift+a'）
        type: 输入类型，'keyboard' 或 'mouse'
        suppress: 是否阻塞按键事件（让其它程序收不到这个按键消息）
        restore: 录音完成后是否自动恢复按键状态（仅对有状态的键有效，如 CapsLock, Shift）
        hold_mode: 长按模式。True=按下录音松开停止；False=单击开始再次单击停止
        threshold: 按下快捷键后触发语音识别的时间阈值（秒），用于防止误触。None 表示使用 Config.threshold
        enabled: 是否启用此快捷键
    """
    key: str
    type: Literal['keyboard', 'mouse'] = 'keyboard'
    suppress: bool = False
    restore: bool = True
    hold_mode: bool = True
    threshold: Optional[float] = None  # None 表示使用 Config.threshold
    enabled: bool = True

    # 鼠标特定配置
    mouse_button: Literal['x1', 'x2'] = 'x2'  # 仅当 type='mouse' 时有效

    def __post_init__(self):
        """初始化后验证配置"""
        # 规范化键名
        if self.type == 'keyboard':
            self.key = self._normalize_key(self.key)
        elif self.type == 'mouse':
            self.key = self.mouse_button

    def get_threshold(self, default_threshold: float = 0.3) -> float:
        """
        获取快捷键的阈值

        Args:
            default_threshold: 默认阈值

        Returns:
            float: 阈值（秒）
        """
        return self.threshold if self.threshold is not None else default_threshold

    @staticmethod
    def _normalize_key(key: str) -> str:
        """
        规范化键名

        Args:
            key: 原始键名

        Returns:
            str: 规范化后的键名（pynput 格式）
        """
        # 转小写
        key = key.lower().strip()

        # 替换常见别名
        aliases = {
            'capslock': 'caps_lock',
            'caps lock': 'caps_lock',
            ' ': 'space',
            'control': 'ctrl',
        }

        for old, new in aliases.items():
            key = key.replace(old, new)

        # 移除左右修饰符标记（pynput 会自动处理）
        # 保留 'left ctrl' 这样的形式

        return key

    def is_toggle_key(self) -> bool:
        """
        判断是否是切换型按键（有状态的键）

        Returns:
            bool: 是否是切换型按键
        """
        toggle_keys = {
            'caps_lock', 'num_lock', 'scroll_lock',
            'shift', 'ctrl', 'alt', 'cmd', 'win'
        }
        # 检查 key 是否包含切换键（考虑组合键情况）
        return any(toggle_key in self.key for toggle_key in toggle_keys)


# 预定义常用快捷键配置
@dataclass
class CommonShortcuts:
    """常用快捷键预设"""

    @staticmethod
    def caps_lock() -> Shortcut:
        """CapsLock 键（默认配置）"""
        return Shortcut(
            key='caps_lock',
            type='keyboard',
            suppress=False,
            restore=True,
            hold_mode=True,
            threshold=0.3
        )

    @staticmethod
    def mouse_x2() -> Shortcut:
        """鼠标 X2 键（前进键）"""
        return Shortcut(
            key='x2',
            type='mouse',
            suppress=True,
            restore=False,
            hold_mode=True,
            threshold=0.3,
            mouse_button='x2'
        )

    @staticmethod
    def f12() -> Shortcut:
        """F12 键"""
        return Shortcut(
            key='f12',
            type='keyboard',
            suppress=False,
            restore=False,
            hold_mode=True,
            threshold=0.3
        )

    @staticmethod
    def space() -> Shortcut:
        """空格键"""
        return Shortcut(
            key='space',
            type='keyboard',
            suppress=False,
            restore=False,
            hold_mode=True,
            threshold=0.3
        )
