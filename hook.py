import sys
from os.path import dirname

# 将「执行文件所在目录」添加到「模块查找路径」
sys.path.insert(0, dirname(sys.executable))
