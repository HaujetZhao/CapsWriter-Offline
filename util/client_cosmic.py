# #TODO: Queue of `Task` (task is not defined)
from __future__ import annotations  # Queue[Task], ListProxy[str] needs this
from asyncio import AbstractEventLoop, Queue
from dataclasses import dataclass, field
from typing import TypedDict

import sounddevice as sd
from rich.console import Console
from rich.theme import Theme
from websockets.legacy.client import WebSocketClientProtocol


class ClientTask(TypedDict):
    type: str
    time: float
    data: np.ndarray


my_theme = Theme({"markdown.code": "cyan", "markdown.item.number": "yellow"})
console = Console(highlight=False, soft_wrap=False, theme=my_theme)


# pylint: disable=too-many-instance-attributes
@dataclass(frozen=False)
class ClientAppStateType:
    """
    A global storage to be accessed across modules, named Cosmic

    #TODO: wrong place of initiation: I think it's
        done in util/client_check_websocket.py
    """

    on: bool = False
    queue_in: Queue[ClientTask] = field(default_factory=Queue)
    queue_out: Queue = field(default_factory=Queue)
    loop: None | AbstractEventLoop = None
    websocket: WebSocketClientProtocol = None
    # next line can avoid async iter problem but it breaks the functionality.
    # websocket: WebSocketClientProtocol = field(
    #     default_factory=WebSocketClientProtocol
    # )
    # #TODO: fix client cosmic initiation.
    audio_files: dict = field(default_factory=dict)
    stream: None | sd.InputStream = None
    kwd_list: list[str] = field(default_factory=list)


ClientAppState = ClientAppStateType()
