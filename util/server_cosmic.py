from __future__ import annotations  # Queue[Task], ListProxy[str] needs this
from dataclasses import dataclass, field
from multiprocessing import Queue
from multiprocessing.managers import ListProxy

from rich.console import Console
from websockets.legacy.server import WebSocketServerProtocol
from util.server_classes import Result, Task

console = Console(highlight=False)


@dataclass(frozen=False)
class CosmicType:
    sockets: dict[str, WebSocketServerProtocol] = field(default_factory=dict)
    sockets_id: ListProxy[str] = field(default_factory=list[str])
    queue_in: Queue[Task] = field(default_factory=Queue)
    queue_out: Queue[bool | Result | None] = field(default_factory=Queue)


Cosmic = CosmicType()
