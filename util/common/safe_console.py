# coding: utf-8
"""
控制台输出安全工具模块

在 GUI 模式下禁用 Rich console 输出，防止编码错误导致程序崩溃。
"""

import os
import sys
from rich.console import Console
from rich.theme import Theme


def is_gui_mode() -> bool:
    """
    检测是否在 GUI 模式下运行（无真实终端）
    
    Returns:
        True 如果在 GUI 模式下（应禁用控制台输出），否则 False
    """
    # 1. 检查环境变量标志（由 GUI 启动器设置）
    if os.environ.get('CAPSWRITER_SUBPROCESS') == '1':
        return True
    # 2. 检查 stdout 是否存在且是真正的终端
    if not sys.stdout or not hasattr(sys.stdout, 'isatty'):
        return True
    try:
        if not sys.stdout.isatty():
            return True
    except Exception:
        return True
    return False


def create_safe_console(theme: Theme = None, **kwargs) -> Console:
    """
    创建一个安全的 Console 实例
    
    在 GUI 模式下自动使用 quiet=True 禁用所有输出。
    
    Args:
        theme: 可选的 Rich Theme
        **kwargs: 传递给 Console 构造函数的其他参数
        
    Returns:
        配置好的 Console 实例
    """
    is_quiet = is_gui_mode()
    if theme:
        return Console(theme=theme, quiet=is_quiet, **kwargs)
    else:
        return Console(quiet=is_quiet, **kwargs)
