# coding: utf-8

import os
import sys
import platform
import signal
import asyncio
from pathlib import Path

import keyboard

from config import ClientConfig as Config
from util.client_cosmic import console, Cosmic
from util.client_stream import stream_open, stream_close
from util.client_shortcut_handler import shortcut_handler
from util.client_recv_result import recv_result
from util.client_show_tips import show_tips
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from util.client_hot_update import HotHandler, update_hot_all, observe_hot

# 确保根目录位置正确，用相对路径加载模型
BASE_DIR = os.path.dirname(__file__); os.chdir(BASE_DIR)

# MacOS 的权限设置
if platform.system() == 'Darwin':
    if os.getuid() != 0:
        print('在 MacOS 上需要以管理员启动客户端才能监听键盘活动，请 sudo 启动')
        input('按回车退出'); sys.exit()
    else:
        os.umask(0o000)


async def main():
    Cosmic.loop = asyncio.get_event_loop()

    show_tips()

    # 更新热词
    update_hot_all()

    # 实时更新热词
    observer = observe_hot()

    # 打开音频流
    Cosmic.stream = stream_open()

    # Ctrl-C 关闭音频流，触发自动重启
    signal.signal(signal.SIGINT, stream_close)

    # 绑定按键
    keyboard.hook_key(Config.shortcut, shortcut_handler)

    # 接收结果
    while True:
        await recv_result()



def init():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print(f'再见！')
    finally:
        print('...')


if __name__ == "__main__":
    init()
