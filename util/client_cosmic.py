from asyncio import AbstractEventLoop, Queue
from dataclasses import dataclass, field
from typing import Union

import sounddevice as sd
from rich.console import Console
from rich.theme import Theme
from websockets.legacy.client import WebSocketClientProtocol

my_theme = Theme({"markdown.code": "cyan", "markdown.item.number": "yellow"})
console = Console(highlight=False, soft_wrap=False, theme=my_theme)


# pylint: disable=too-many-instance-attributes
@dataclass(frozen=False)
class Cosmic:
    """
    A global storage to be accessed across modules, named Cosmic

    #TODO: wrong place of initiation: I think it's
        done in util/client_check_websocket.py
    """

    on: bool = False
    queue_in: Queue = field(default_factory=Queue)
    queue_out: Queue = field(default_factory=Queue)
    loop: Union[None, AbstractEventLoop] = None
    websocket: WebSocketClientProtocol = field(
        default_factory=WebSocketClientProtocol
    )
    audio_files: dict = field(default_factory=dict)
    stream: Union[None, sd.InputStream] = None
    kwd_list: list[str] = field(default_factory=list)
