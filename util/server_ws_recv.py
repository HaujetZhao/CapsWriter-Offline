import json
import time
from base64 import b64decode
from dataclasses import dataclass
from typing import Any

import websockets
from websockets.legacy.server import WebSocketServerProtocol

from util.my_status import Status
from util.server_classes import Task
from util.server_cosmic import Cosmic, console

status_mic = Status("正在接收音频", spinner="point")


@dataclass(frozen=False)
class Cache:
    """A mutable object to store audio data and offset time"""

    chunks: bytes = b""
    offset: int = 0
    frame_num: int = 0


async def message_handler(
    websocket: WebSocketServerProtocol, message: dict[str, Any], cache: Cache
) -> None:
    """处理得到的音频流数据"""

    queue_in = Cosmic.queue_in

    global status_mic  # pylint: disable=global-variable-not-assigned
    source = message["source"]
    is_final = message["is_final"]
    is_start = not bool(cache.chunks)

    # 获取 id
    task_id = message["task_id"]
    socket_id = str(websocket.id)

    # 获取分段长度（以多长的音频进行识别）
    seg_duration = message["seg_duration"]
    seg_overlap = message["seg_overlap"]
    seg_threshold = seg_duration + seg_overlap * 2

    # base64 解码音频数据，再
    # 音频数据是 float32、单声道、16000采样率
    data = b64decode(message["data"])
    cache.chunks += data
    cache.frame_num += len(data)

    if not is_final:
        # 打印消息
        if source == "mic":
            status_mic.start()
        if source == "file" and is_start:
            console.print("正在接收音频文件...")

        # 若缓冲已达到分段长度，将片段作为任务提交
        while len(cache.chunks) / 4 / 16000 >= seg_threshold:
            data = cache.chunks[: 4 * 16000 * (seg_duration + seg_overlap)]
            cache.chunks = cache.chunks[4 * 16000 * seg_duration :]
            task = Task(
                source=message["source"],
                data=data,
                offset=cache.offset,
                task_id=task_id,
                socket_id=socket_id,
                overlap=seg_overlap,
                is_final=False,
                time_start=message["time_start"],
                time_submit=time.time(),
            )
            cache.offset += seg_duration
            queue_in.put(task)

    elif is_final:
        # 打印消息
        if source == "mic":
            status_mic.stop()
        elif source == "file":
            print(f"音频文件接收完毕，时长 {cache.frame_num / 16000 / 4:.2f}s")

        # 客户端说片段结束，将缓冲区音频识别
        task = Task(
            source=message["source"],
            data=cache.chunks[0:],
            offset=cache.offset,
            task_id=task_id,
            socket_id=socket_id,
            overlap=seg_overlap,
            is_final=True,
            time_start=message["time_start"],
            time_submit=time.time(),
        )
        queue_in.put(task)

        # 还原缓冲区、偏移时长
        cache.chunks = b""
        cache.offset = 0
        cache.frame_num = 0


async def ws_recv(websocket: WebSocketServerProtocol) -> None:
    global status_mic  # pylint: disable=global-variable-not-assigned

    # 登记 socket 到字典，以 socket id 字符串为索引
    sockets = Cosmic.sockets
    sockets_id = Cosmic.sockets_id
    sockets[str(websocket.id)] = websocket
    sockets_id.append(str(websocket.id))
    console.print(f"接客了：{websocket}\n", style="yellow")

    # 设定分段长度
    # seg_duration = 15
    # seg_overlap = 2
    # seg_duration += seg_overlap * 2
    # #TODO: consider if this is necessary, and use constants

    # 片段缓冲区、偏移时长
    cache = Cache()

    # 接收数据
    try:
        async for message in websocket:

            # json 解码字符串
            message = json.loads(message)

            # 处理数据
            await message_handler(websocket, message, cache)

        console.print(
            "ConnectionClosed...",
        )
    except websockets.ConnectionClosed:
        console.print(
            "ConnectionClosed...",
        )
    except websockets.InvalidState:
        console.print("InvalidState...")
    except Exception as e:  # pylint: disable=broad-exception-caught
        console.print("!!! Unexpected Exception !!! in server_ws_recv.py")
        console.print("Exception:", e)
    finally:
        status_mic.stop()
        status_mic.on = False
        sockets.pop(str(websocket.id))
        sockets_id.remove(str(websocket.id))
