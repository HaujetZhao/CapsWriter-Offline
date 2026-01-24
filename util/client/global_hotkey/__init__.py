# coding: utf-8
"""
全局快捷键子模块

使用 pynput GlobalHotKeys 实现全局快捷键监听。
"""

from .. import logger
from util.client.global_hotkey.global_hotkey import (
    GlobalHotkeyManager,
    get_global_hotkey_manager,
)

__all__ = [
    'logger',
    'GlobalHotkeyManager',
    'get_global_hotkey_manager',
]
