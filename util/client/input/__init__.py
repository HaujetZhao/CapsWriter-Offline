# coding: utf-8
"""
input 子模块

包含输入处理相关功能，如快捷键处理和鼠标监听。
"""

from util.client.input.shortcut import ShortcutHandler
from util.client.input.mouse import MouseHandler

__all__ = [
    'ShortcutHandler',
    'MouseHandler',
]

