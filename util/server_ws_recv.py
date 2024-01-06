import json 
import base64 
import asyncio
import websockets
from base64 import b64decode

from util.server_cosmic import console, connections, queue_in, queue_out
from util.server_classes import Task, Result



async def message_file_handler(websocket, message):
    """处理由文件得到的音频流，一个 message 包含了整段音频"""

    global chunks, offset, status

    # 获取 id
    task_id = message['task_id']
    socket_id = str(websocket.id)

    # 获取分段长度
    seg_duration = message['seg_duration']
    seg_overlap = message['seg_overlap']
    seg_threshold = seg_duration + seg_overlap * 2

    # base64 解码音频数据
    # 音频数据是 float32、单声道、16000采样率
    chunks = b64decode(message['data'])

    print(f'收到音频文件，时长 {len(chunks)/4/16000:.2f}s')

    # 如果收到了空内容
    if len(chunks) == 0:
        result = Result(task_id, socket_id, 'file')
        result.is_final = True
        queue_out.put(result)
        return

    # 分段提交任务
    is_final = False
    while len(chunks) > 0:

        # 判断是否为最后一段
        if len(chunks) <= seg_threshold * 16000 * 4:
            is_final = True

        data = chunks[:4 * 16000 * (seg_duration + seg_overlap)]
        chunks = chunks[4 * 16000 * seg_duration:]
        task = Task(source='file',
                    data=data, offset=offset,
                    task_id=task_id, socket_id=socket_id,
                    overlap=seg_overlap, is_final=is_final,
                    time_start=message['time_start'],
                    time_submit=message['time_frame'])
        offset += seg_duration
        queue_in.put(task)

    # 还原缓冲区、偏移时长
    chunks = b''
    offset = 0


async def message_mic_handler(websocket, message):
    """处理由麦克风得到的音频流"""

    global chunks, offset, status

    # 获取 id
    task_id = message['task_id']
    socket_id = str(websocket.id)

    # 获取分段长度
    seg_duration = message['seg_duration']
    seg_overlap = message['seg_overlap']
    seg_threshold = seg_duration + seg_overlap * 2

    # base64 解码音频数据
    # 音频数据是 float32、单声道、16000采样率
    data = b64decode(message['data'])

    if not message['is_final']:
        status.start()

        # 将音频片段加入缓冲区
        chunks += data

        # 若缓冲已达到分段长度，将片段作为任务提交
        while len(chunks) / 4 / 16000 >= seg_threshold:
            data = chunks[:4 * 16000 * (seg_duration + seg_overlap)]
            chunks = chunks[4 * 16000 * seg_duration:]
            task = Task(source='mic',
                        data=data, offset=offset,
                        task_id=task_id, socket_id=socket_id,
                        overlap=seg_overlap, is_final=False,
                        time_start=message['time_start'],
                        time_submit=message['time_frame'])
            offset += seg_duration
            queue_in.put(task)

    elif message['is_final']:
        status.stop()
        # 客户端说片段结束，将缓冲区音频识别
        task = Task(source='mic',
                    data=chunks[0:], offset=offset,
                    task_id=task_id, socket_id=socket_id,
                    overlap=seg_overlap, is_final=True,
                    time_start=message['time_start'],
                    time_submit=message['time_frame'])
        queue_in.put(task)

        # 还原缓冲区、偏移时长
        chunks = b''
        offset = 0


async def ws_recv(websocket):
    global chunks, offset, status

    status = console.status('正在接收音频', spinner='point')

    # 登记 socket 到字典，以 socket id 字符串为索引
    connections[str(websocket.id)] = websocket
    console.print(f'接客了：{websocket}\n', style='yellow')

    # 设定分段长度
    seg_duration = 15
    seg_overlap = 2
    seg_threshold = seg_duration + seg_overlap * 2

    # 片段缓冲区、偏移时长
    chunks = b''
    offset = 0

    # 接收数据
    try:
        async for message in websocket:

            # json 解码字符串
            message = json.loads(message)

            if message['source'] == 'mic':
                await message_mic_handler(websocket, message)
            elif message['source'] == 'file':
                await message_file_handler(websocket, message)

        console.print("ConnectionClosed...", )
    except websockets.ConnectionClosed:
        console.print("ConnectionClosed...", )
    except websockets.InvalidState:
        console.print("InvalidState...")
    except Exception as e:
        console.print("Exception:", e)
    finally:
        status.stop()
        connections.pop(str(websocket.id))
