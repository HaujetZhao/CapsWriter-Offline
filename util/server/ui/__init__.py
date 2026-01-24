# coding: utf-8
"""
服务端 UI 门面模块

该模块作为服务端访问 UI 功能的统一入口。
在导入此模块时，会自动将服务端的 logger 注入到通用 UI 模块中。
并重新导出服务端需要的 UI 组件。
"""

from .. import logger
import util.ui

# 1. 注入 Server Logger 到通用 UI 模块
util.ui.set_ui_logger(logger)

# 2. 重新导出通用 UI 组件 (Re-export)
from util.ui import (
    enable_min_to_tray,
    toast,          # 服务端理论上也可能发 toast
)
# 注意：stop_tray 通常是在 cleanup 中使用，也可以导出
from util.ui.tray import stop_tray


__all__ = [
    'logger',
    'enable_min_to_tray',
    'stop_tray',
    'toast',
]
