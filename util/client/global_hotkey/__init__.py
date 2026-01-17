# coding: utf-8
"""
全局快捷键子模块

使用 pynput GlobalHotKeys 实现全局快捷键监听。

使用示例:
    from util.client.global_hotkey import GlobalHotkeyManager

    manager = GlobalHotkeyManager()
    manager.register('<esc>', lambda: print('ESC pressed'))
    manager.start()
"""

from util.client.global_hotkey.global_hotkey import (
    GlobalHotkeyManager,
    get_global_hotkey_manager,
)

__all__ = [
    'GlobalHotkeyManager',
    'get_global_hotkey_manager',
]
