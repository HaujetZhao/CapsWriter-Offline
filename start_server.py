# coding: utf-8
import sys
from multiprocessing import freeze_support
from util.server.app import CapsWriterServer

if __name__ == '__main__':
    # 启用对 PyInstaller 打包后的多进程支持
    freeze_support()
    
    # 实例化并启动门面类
    # 环境初始化职责已下放至 CapsWriterServer
    server = CapsWriterServer()
    server.start()
    
    sys.exit(0)