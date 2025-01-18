import wave
from subprocess import Popen

import numpy as np

from util.types import RecordingData


def write_file(file: Popen[bytes] | wave.Wave_write, data: RecordingData):
    if isinstance(file, Popen):
        stdin = file.stdin
        assert stdin is not None
        stdin.write(data.tobytes())
        stdin.flush()
    else:
        # elif isinstance(file, wave.Wave_write):
        frame = (data * (2**15 - 1)).astype(np.int16).tobytes()
        file.writeframes(frame)
