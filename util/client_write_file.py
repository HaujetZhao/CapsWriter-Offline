import wave
from subprocess import Popen
from typing import Union

import numpy as np


def write_file(file: Union[Popen, wave.Wave_write], data: np.ndarray):
    if isinstance(file, Popen):
        file.stdin.write(data.tobytes())
        file.stdin.flush()
    elif isinstance(file, wave.Wave_write):
        data = (data * (2**15 - 1)).astype(np.int16).tobytes()
        file.writeframes(data)
