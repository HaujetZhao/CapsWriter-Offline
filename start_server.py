# coding: utf-8


'''
这个文件仅仅是为了 PyInstaller 打包用
'''

from multiprocessing import freeze_support
import core_server


if __name__ == '__main__':
    freeze_support()
    core_server.init()