# coding: utf-8
"""
input 子模块

包含输入处理相关功能，如快捷键处理和鼠标监听。

使用 ShortcutManager 统一管理所有快捷键（键盘和鼠标）。
"""

from util.client.input.shortcut_config import Shortcut, CommonShortcuts
from util.client.input.shortcut_manager import ShortcutManager

__all__ = [
    'Shortcut',
    'CommonShortcuts',
    'ShortcutManager',
]
