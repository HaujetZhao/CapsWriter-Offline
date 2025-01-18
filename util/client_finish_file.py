import wave
from subprocess import Popen


def finish_file(file: Popen[bytes] | wave.Wave_write):
    if isinstance(file, Popen):
        assert file.stdin is not None
        file.stdin.close()  # 停止输入，ffmpeg 会自动关闭
    # elif isinstance(file, wave.Wave_write):
    else:
        file.close()
    # else:
    #     raise TypeError("file must be Popen[bytes] or Wave_write")
