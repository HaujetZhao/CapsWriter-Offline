import re
import time
from pathlib import Path

from config import ClientConfig as Config
from util.client_cosmic import ClientAppState, console

UuidStr = str
# #TODO-STY-UUID_STR: consider using a NewType for UuidStr


def rename_audio(task_id: UuidStr, text: str, start_sec: float) -> Path | None:

    # 获取旧文件名
    file_path = Path(ClientAppState.audio_files.pop(task_id))

    # 确保旧文件存在
    if not file_path.exists():
        console.print(f"    文件不存在：{file_path}")
        return None

    # 构建新文件名
    time.strftime("%Y", time.localtime(start_sec))
    time.strftime("%m", time.localtime(start_sec))
    time_ymdhms = time.strftime("%Y%m%d-%H%M%S", time.localtime(start_sec))
    file_stem = f"({time_ymdhms}){text[:Config.audio_name_len]}"
    file_stem = re.sub(r'[\\/:"*?<>|]', " ", file_stem)

    # 重命名
    file_path_new = file_path.with_name(file_stem + file_path.suffix)
    file_path.rename(file_path_new)

    # 返回新的录音文件路径
    return file_path_new
