from dataclasses import dataclass, field
from multiprocessing import Queue
from multiprocessing.managers import ListProxy

import websockets
from rich.console import Console

console = Console(highlight=False)

# class Cosmic:
#     sockets: Dict[str, websockets.WebSocketClientProtocol] = {}
#     sockets_id: List
#     queue_in = Queue()
#     queue_out = Queue()


@dataclass(frozen=False)
class CosmicType:
    sockets: dict[str, websockets.WebSocketClientProtocol] = field(
        default_factory=dict
    )
    sockets_id: ListProxy = field(default_factory=list)
    queue_in: Queue = field(default_factory=Queue)
    queue_out: Queue = field(default_factory=Queue)


Cosmic = CosmicType()
