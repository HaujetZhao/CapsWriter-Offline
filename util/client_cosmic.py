# #TODO: Queue of `Task` (task is not defined)
from __future__ import annotations  # Queue[Task], ListProxy[str] needs this

from asyncio import AbstractEventLoop, Queue
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypedDict

import sounddevice as sd  # pyright: ignore[reportMissingTypeStubs]
from rich.console import Console
from rich.theme import Theme
from util.types import RecordingData
from websockets.legacy.client import WebSocketClientProtocol


class NonDataClientTask(TypedDict):
    type: Literal["begin", "finish"]
    time: float
    data: None


class DataClientTask(TypedDict):
    type: Literal["data"]
    time: float
    data: RecordingData


ClientTask = NonDataClientTask | DataClientTask


class ClientMessage(TypedDict):
    """
    ClientMessage is a dict of the following
    #TODO-REF-DC: change to dataclass
    """

    task_id: str
    seg_duration: float  # Config.file_seg_duration by default
    seg_overlap: float  # Config.file_seg_overlap by default
    is_final: bool  # is_final: chunk_end >= len(data) (is ended)
    time_start: float  # time.time(), time of recording start
    time_frame: float  # time.time(), time of current frame
    source: Literal["file", "mic"]  # data source: from file
    data: str  # base64.b64encode(data[offset:chunk_end]).decode("utf-8")


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

    on: float | bool = False
    queue_in: Queue[ClientTask] = field(default_factory=Queue)
    # Seems like queue_out is never used in the code.
    # queue_out: Queue = field(default_factory=Queue)
    loop: None | AbstractEventLoop = None
    websocket: WebSocketClientProtocol | None = None
    # next line can avoid async iter problem but it breaks the functionality.
    # websocket: WebSocketClientProtocol = field(
    #     default_factory=WebSocketClientProtocol
    # )
    # #TODO: fix client cosmic initiation.
    audio_files: dict[str, Path] = field(default_factory=dict)
    # #TODO: use NewType UuidStr for audio_files keys.
    stream: None | sd.InputStream = None
    # #TODO-REF-APP: remove None from stream
    kwd_list: list[str] = field(default_factory=list)


ClientAppState = ClientAppStateType()
