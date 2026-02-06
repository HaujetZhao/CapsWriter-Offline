import sys
import os
from os.path import dirname, join, exists

# 将「执行文件所在目录」添加到「模块查找路径」
# 这确保了可以找到复制的源文件（config.py, core_*.py, util/ 等）
executable_dir = dirname(sys.executable)
sys.path.insert(0, executable_dir)

# PyInstaller 打包时，第三方依赖（DLL, PYD）放在 internal/ 目录
# 需要将 internal/ 也添加到路径，否则 Python 无法找到这些依赖
internal_dir = join(executable_dir, 'internal')
if exists(internal_dir):
    sys.path.insert(0, internal_dir)
