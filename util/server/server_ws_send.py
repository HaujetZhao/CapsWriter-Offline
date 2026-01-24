import json
import base64
import asyncio
from multiprocessing import Queue

from util.server.server_cosmic import console, Cosmic
from util.server.server_classes import Result
from util.tools.asyncio_to_thread import to_thread
from . import logger
from rich import inspect



async def ws_send():

    queue_out = Cosmic.queue_out
    sockets = Cosmic.sockets

    logger.info("WebSocket 发送任务已启动")

    while True:
        try:
            # 获取识别结果（从多进程队列）
            result: Result = await to_thread(queue_out.get)

            # 得到退出的通知
            if result is None:
                logger.info("收到退出通知，停止发送任务")
                return

            # 构建消息
            message = {
                'task_id': result.task_id,
                'duration': result.duration,
                'time_start': result.time_start,
                'time_submit': result.time_submit,
                'time_complete': result.time_complete,
                'text': result.text,               # 主要输出（简单拼接）
                'text_accu': result.text_accu,     # 精确输出（时间戳拼接）
                'tokens': result.tokens,
                'timestamps': result.timestamps,
                'is_final': result.is_final,
            }

            # 获得 socket
            websocket = next(
                (ws for ws in sockets.values() if str(ws.id) == result.socket_id),
                None,
            )

            if not websocket:
                logger.warning(f"客户端 {result.socket_id} 不存在，跳过发送结果，任务ID: {result.task_id}")
                continue

            # 发送消息
            await websocket.send(json.dumps(message))
            logger.debug(f"发送识别结果，任务ID: {result.task_id}, 文本长度: {len(result.text)}")

            if result.source == 'mic':
                console.print(f'识别结果：\n    [green]{result.text}')
                logger.info(f"麦克风识别结果: {result.text}")
            elif result.source == 'file':
                console.print(f'    转录进度：{result.duration:.2f}s', end='\r')
                logger.debug(f"文件转录进度: {result.duration:.2f}s")
                if result.is_final:
                    console.print('\n    [green]转录完成')
                    logger.info(f"文件转录完成，任务ID: {result.task_id}, 总时长: {result.duration:.2f}s")

        except Exception as e:
            logger.error(f"发送结果时发生错误: {e}", exc_info=True)
            print(e)


