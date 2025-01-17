from dataclasses import dataclass, field
from typing import Any


# pylint: disable=too-many-instance-attributes
@dataclass(frozen=True)
class Task:
    source: str
    data: Any  # #TODO: fix any
    offset: float
    overlap: float
    task_id: str
    socket_id: str
    is_final: bool
    time_start: float
    time_submit: float
    samplerate: int = 16000


@dataclass(frozen=False)  # need to assign "duration"
class Result:
    task_id: str  # Task ID
    socket_id: str  # Socket ID
    source: str  # Source of the audio stream ('file' or 'mic')
    duration: float = 0  # Total audio duration
    time_start: float = 0  # Recording start time
    time_submit: float = 0  # Segment submission time
    time_complete: float = 0  # Recognition completion time
    tokens: list[str] = field(default_factory=list)  # Character-level tokens
    timestamps: list[float] = field(
        default_factory=list
    )  # Timestamps of character-level tokens
    text: str = ""  # Merged text
    is_final: bool = False  # Whether all segment recognition is complete
