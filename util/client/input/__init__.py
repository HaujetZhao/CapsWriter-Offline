# coding: utf-8
"""
input 子模块

包含输入处理相关功能，如快捷键处理和鼠标监听。

新版使用 ShortcutManager 统一管理所有快捷键（键盘和鼠标）。
"""

from util.client.input.shortcut_config import Shortcut, CommonShortcuts
from util.client.input.shortcut_manager import ShortcutManager
from util.client.input.shortcut import ShortcutHandler  # 保留向后兼容
from util.client.input.mouse import MouseHandler  # 保留向后兼容

__all__ = [
    'Shortcut',
    'CommonShortcuts',
    'ShortcutManager',
    'ShortcutHandler',  # 向后兼容
    'MouseHandler',  # 向后兼容
]
