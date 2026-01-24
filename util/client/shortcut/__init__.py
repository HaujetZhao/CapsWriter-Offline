# coding: utf-8
"""
shortcut 子模块

包含快捷键处理相关功能，使用 ShortcutManager 统一管理所有快捷键（键盘和鼠标）。
"""

from .. import logger
from util.client.shortcut.shortcut_config import Shortcut, CommonShortcuts
from util.client.shortcut.shortcut_manager import ShortcutManager

__all__ = [
    'logger',
    'Shortcut',
    'CommonShortcuts',
    'ShortcutManager',
]
