import json 
import base64 
import asyncio
from multiprocessing import Queue

from util.server_cosmic import console, connections, queue_out, connections
from rich import inspect


async def ws_send():
    while True:
        try:
            # 获取识别结果（从多进程队列）
            result = await asyncio.to_thread(queue_out.get)

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
                (ws for ws in connections.values() if str(ws.id) == result.socket_id),
                None,
            )

            # 发送消息
            await websocket.send(json.dumps(message))

            console.print(f'识别结果：\n    [green]{result.text}\n')
        except Exception as e:
            print(e)


