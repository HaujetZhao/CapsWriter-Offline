#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CapsWriter-Offline GUI 启动器 - 双击运行（无控制台）"""
import os
import sys

# 切换到脚本所在目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from gui.main_window import main
main()
