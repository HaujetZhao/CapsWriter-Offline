# coding: utf-8


"""
这个文件仅仅是为了 PyInstaller 打包用
"""

import sys
import typer
from core_client import init_file, init_mic

if __name__ == "__main__":
    # 如果参数传入文件，那就转录文件
    # 如果没有多余参数，就从麦克风输入
    if sys.argv[1:]:
        typer.run(init_file)
    else:
        init_mic()