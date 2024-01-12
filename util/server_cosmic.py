import sys
from pathlib import Path
from multiprocessing import Queue
from typing import Dict, List
import websockets
from rich.console import Console 
console = Console(highlight=False)





class Cosmic:
    sockets: Dict[str, websockets.WebSocketClientProtocol] = {}
    sockets_id: List
    queue_in = Queue()
    queue_out = Queue()
