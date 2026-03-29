# coding: utf-8
"""
CapsWriter Offline Server (主入口)

这是服务端的主启动脚本。核心逻辑已封装至 util.server.app.CapsWriterServer 类中，
遵循门面模式 (Facade Pattern) 实现各管理器的统一调度。
"""

import os
from util.server.app import CapsWriterServer


# 切换工作目录至脚本所在文件夹
BASE_DIR = os.path.dirname(__file__)
if BASE_DIR:
    os.chdir(BASE_DIR)


def main():
    """初始化并启动 CapsWriter 服务端"""
    server = CapsWriterServer()
    server.start()


if __name__ == "__main__":
    main()
