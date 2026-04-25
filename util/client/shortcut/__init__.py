# coding: utf-8
"""
shortcut 子模块

包含快捷键处理相关功能，使用 ShortcutManager 统一管理所有快捷键（键盘和鼠标）。
根据平台自动选择 Windows 或 Linux 实现。
"""

import platform

from .. import logger
from util.client.shortcut.shortcut_config import Shortcut, CommonShortcuts

if platform.system() == 'Linux':
    from util.client.shortcut.linux_shortcut_manager import LinuxShortcutManager as ShortcutManager
    from util.client.shortcut.linux_key_mapper import LinuxKeyMapper as KeyMapper
    from util.client.shortcut.linux_key_mapper import RESTORABLE_KEYS
else:
    from util.client.shortcut.shortcut_manager import ShortcutManager
    from util.client.shortcut.key_mapper import KeyMapper
    from util.client.shortcut.key_mapper import RESTORABLE_KEYS

__all__ = [
    'logger',
    'Shortcut',
    'CommonShortcuts',
    'ShortcutManager',
]
