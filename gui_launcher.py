#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CapsWriter-Offline GUI 启动器（精简版）"""
import sys
import os

# EXE 运行时，切换到 EXE 所在目录（确保能找到本地文件）
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

# 添加当前目录到 Python 路径（确保能导入本地模块）
sys.path.insert(0, os.getcwd())

from gui.main_window import main
main()
