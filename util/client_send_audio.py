import asyncio
import base64
import json
from pathlib import Path
from subprocess import Popen
import uuid
from wave import Wave_write

import numpy as np
import websockets

from config import ClientConfig as Config
from util.client_cosmic import ClientAppState, ClientMessage, console
from util.client_create_file import create_file
from util.client_finish_file import finish_file
from util.client_write_file import write_file
from util.types import RecordingData


async def send_message(message: ClientMessage):
    # 发送数据
    if ClientAppState.websocket is None or ClientAppState.websocket.closed:
        if message["is_final"]:
            ClientAppState.audio_files.pop(message["task_id"])
            console.print("    服务端未连接，无法发送\n")
    else:
        try:
            await ClientAppState.websocket.send(json.dumps(message))
        except websockets.ConnectionClosedError:
            if message["is_final"]:
                console.print("[red]连接中断了")
        except Exception as e:  # pylint: disable=broad-exception-caught
            print("!!! UNEXPECTED ERROR !!! in client_send_audio.py")
            print(e)


async def send_audio():
    try:  # #TODO-REF: move this try-except block to where send_audio is called
        # 生成唯一任务 ID
        task_id = str(uuid.uuid1())

        # 任务起始时间
        time_start = 0

        # 音频数据临时存放处
        cache = list[RecordingData]()
        duration = 0

        # 保存音频文件
        file_path: str | Path = ""
        file: Popen[bytes] | Wave_write | None = None

        # 开始取数据
        while task := await ClientAppState.queue_in.get():
            ClientAppState.queue_in.task_done()
            if task["type"] == "begin":
                time_start = task["time"]
            elif task["type"] == "data":
                a_data = task["data"]
                # 在阈值之前积攒音频数据
                if task["time"] - time_start < Config.threshold:
                    cache.append(a_data)
                    continue

                # 获取音频数据
                if cache:
                    data: RecordingData = np.concatenate(cache)
                    cache.clear()
                else:
                    data = a_data
                duration += len(data) / 48000

                # 创建音频文件
                if Config.save_audio:
                    if not file_path:
                        file_path, file = create_file(
                            a_data.shape[1], time_start
                        )
                        ClientAppState.audio_files[task_id] = file_path
                    # 保存音频至本地文件
                    assert file, "PABLO_REF: file=None but file_path is given"
                    write_file(file, data)

                # 发送音频数据用于识别
                message = ClientMessage(
                    {
                        "task_id": task_id,  # 任务 ID
                        "seg_duration": Config.mic_seg_duration,  # 分段长度
                        "seg_overlap": Config.mic_seg_overlap,  # 分段重叠
                        "is_final": False,  # 是否结束
                        "time_start": time_start,  # 录音起始时间
                        "time_frame": task["time"],  # 该帧时间
                        "source": "mic",  # 数据来源：从麦克风收到的数据
                        "data": base64.b64encode(  # 数据
                            np.mean(data[::3], axis=1).tobytes()
                        ).decode("utf-8"),
                    }
                )
                task = asyncio.create_task(send_message(message))
            elif task["type"] == "finish":
                # 完成写入本地文件
                if Config.save_audio:
                    assert file, "PABLO_REF: file=None yet is expected"
                    finish_file(file)

                console.print(f"任务标识：{task_id}")
                console.print(f"    录音时长：{duration:.2f}s")

                # 告诉服务端音频片段结束了
                message = ClientMessage(
                    {
                        "task_id": task_id,
                        "seg_duration": 15,
                        "seg_overlap": 2,
                        "is_final": True,
                        "time_start": time_start,
                        "time_frame": task["time"],
                        "source": "mic",
                        "data": "",
                    }
                )
                task = asyncio.create_task(send_message(message))
                break
    except Exception as e:  # pylint: disable=broad-exception-caught
        print("!!! UNEXPECTED ERROR !!! in client_send_audio.py")
        print(type(e))
        print(e)
