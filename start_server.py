'''
这个文件仅仅是为了 PyInstaller 打包用
'''

import sys; from os.path import dirname; BASE_DIR = dirname(sys.executable)
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, BASE_DIR + os.sep + r'libs')
from pathlib import Path
import os


if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # 在打包环境中
    code_file = Path(BASE_DIR) / 'core_server.py'
    with open(code_file, 'r', encoding="utf-8") as f:
        code = f.read()
    exec(code, globals(), locals())
else:
    # 在正常环境中
    import core_server
    import core_client