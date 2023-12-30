import sys
from pathlib import Path
from multiprocessing import Queue
import websockets
from rich.console import Console 
console = Console(highlight=False)





class Cosmic:
    addr = '0.0.0.0'
    port = '6016'

    format_num      = True      # 输出时是否将中文数字转为阿拉伯数字
    format_punc     = False      # 输出时是否启用标点符号引擎（在 MacOS 上标点引擎似乎有问题，应当改为 False）
    format_spell    = True      # 输出时是否调整中英之间的空格


connections: dict[str:websockets.WebSocketClientProtocol] = dict()

queue_in = Queue()
queue_out = Queue()
