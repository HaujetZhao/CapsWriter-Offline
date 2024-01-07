import sys
from pathlib import Path
from multiprocessing import Queue
from typing import Dict, AnyStr
import websockets
from rich.console import Console 
console = Console(highlight=False)





class Cosmic:
    ...


connections: Dict[str, websockets.WebSocketClientProtocol] = dict()

queue_in = Queue()
queue_out = Queue()
