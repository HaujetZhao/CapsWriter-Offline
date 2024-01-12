import base64
import json
import os
import sys
import platform
import uuid
from pathlib import Path
import time
import re
import wave
import asyncio
import subprocess

import numpy as np
import websockets
import typer
import colorama
from util import srt_from_txt
from util.client_cosmic import console, Cosmic
from util.client_check_websocket import check_websocket
from config import ClientConfig as Config



async def transcribe_check(file: Path):
    # 检查连接
    if not await check_websocket():
        console.print('无法连接到服务端')
        sys.exit()

    if not file.exists():
        console.print(f'文件不存在：{file}')
        return False

async def transcribe_send(file: Path):

    # 获取连接
    websocket = Cosmic.websocket

    # 生成任务 id
    task_id = str(uuid.uuid1())
    console.print(f'\n任务标识：{task_id}')
    console.print(f'    处理文件：{file}')

    # 获取音频数据，ffmpeg 输出采样率 16000，单声道，float32 格式
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", file,
        "-f", "f32le",
        "-ac", "1",
        "-ar", "16000",
        "-",
    ]
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    console.print(f'    正在提取音频', end='\r')
    data = process.stdout.read()
    audio_duration = len(data) / 4 / 16000
    console.print(f'    音频长度：{audio_duration:.2f}s')

    # 构建分段消息，发送给服务端
    offset = 0
    while True:
        chunk_end = offset + 16000*4*60
        is_final = False if chunk_end < len(data) else True
        message = {
            'task_id': task_id,                     # 任务 ID
            'seg_duration': Config.file_seg_duration,    # 分段长度
            'seg_overlap': Config.file_seg_overlap,      # 分段重叠
            'is_final': is_final,                       # 是否结束
            'time_start': time.time(),              # 录音起始时间
            'time_frame': time.time(),              # 该帧时间
            'source': 'file',                       # 数据来源：从文件读的数据
            'data': base64.b64encode(
                        data[offset: chunk_end]
                    ).decode('utf-8'),
        }
        offset = chunk_end
        progress = min(offset / 4 / 16000, audio_duration)
        await websocket.send(json.dumps(message))
        console.print(f'    发送进度：{progress:.2f}s', end='\r')
        if is_final:
            break

async def transcribe_recv(file: Path):

    # 获取连接
    websocket = Cosmic.websocket

    # 接收结果
    async for message in websocket:
        message = json.loads(message)
        console.print(f'    转录进度: {message["duration"]:.2f}s', end='\r')
        if message['is_final']:
            break

    # 解析结果
    text_merge = message['text']
    text_split = re.sub('[，。？]', '\n', text_merge)
    timestamps = message['timestamps']
    tokens = message['tokens']

    # 得到文件名
    json_filename = Path(file).with_suffix(".json")
    txt_filename = Path(file).with_suffix(".txt")
    merge_filename = Path(file).with_suffix(".merge.txt")

    # 写入结果
    with open(merge_filename, "w", encoding="utf-8") as f:
        f.write(text_merge)
    with open(txt_filename, "w", encoding="utf-8") as f:
        f.write(text_split)
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump({'timestamps': timestamps, 'tokens': tokens}, f, ensure_ascii=False)
    srt_from_txt.one_task(txt_filename)

    process_duration = message['time_complete'] - message['time_start']
    console.print(f'\033[K    处理耗时：{process_duration:.2f}s')
    console.print(f'    识别结果：\n[green]{message["text"]}')
