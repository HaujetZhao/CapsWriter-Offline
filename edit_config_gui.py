#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CapsWriter-Offline 配置工具
双击此文件启动图形化配置界面
"""

import sys
import os

# 确保项目根目录在 Python 路径中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from gui.main_window import main

if __name__ == "__main__":
    main()
