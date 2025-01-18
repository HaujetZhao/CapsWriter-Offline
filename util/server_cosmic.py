from __future__ import annotations  # Queue[Task], ListProxy[str] needs this
from dataclasses import dataclass, field
from multiprocessing import Queue
from multiprocessing.managers import ListProxy
from typing import TypedDict

from rich.console import Console
from websockets.legacy.server import WebSocketServerProtocol
from util.server_classes import Result, Task

console = Console(highlight=False)


class Message(TypedDict):
    # #TODO: check message and Result, are they the same?
    # #TODO: rename to ServerMessage
    task_id: str
    duration: float
    time_start: float
    time_submit: float
    time_complete: float
    tokens: list[str]
    timestamps: list[float]
    text: str
    is_final: bool


@dataclass(frozen=False)
class ServerAppStateType:
    sockets: dict[str, WebSocketServerProtocol] = field(default_factory=dict)
    sockets_id: ListProxy[str] = field(default_factory=list[str])
    queue_in: Queue[Task] = field(default_factory=Queue)
    queue_out: Queue[bool | Result | None] = field(default_factory=Queue)


ServerAppState = ServerAppStateType()
