import json 
import base64 
import asyncio
from multiprocessing import Queue

from util.server_cosmic import console, Cosmic
from util.server_classes import Result
from util.asyncio_to_thread import to_thread
from rich import inspect


async def ws_send():

    queue_out = Cosmic.queue_out
    sockets = Cosmic.sockets

    while True:
        try:
            # 获取识别结果（从多进程队列）
            result: Result = await to_thread(queue_out.get)

            # 得到退出的通知
            if result is None:
                return

            # 构建消息
            message = {
                'task_id': result.task_id,
                'duration': result.duration,
                'time_start': result.time_start,
                'time_submit': result.time_submit,
                'time_complete': result.time_complete,
                'tokens': result.tokens,
                'timestamps': result.timestamps,
                'text': result.text,
                'is_final': result.is_final,
            }

            # 获得 socket
            websocket = next(
                (ws for ws in sockets.values() if str(ws.id) == result.socket_id),
                None,
            )

            if not websocket:
                continue

            # 发送消息
            await websocket.send(json.dumps(message))

            if result.source == 'mic':
                console.print(f'识别结果：\n    [green]{result.text}')
            elif result.source == 'file':
                console.print(f'    转录进度：{result.duration:.2f}s', end='\r')
                if result.is_final:
                    console.print('\n    [green]转录完成')

        except Exception as e:
            print(e)


