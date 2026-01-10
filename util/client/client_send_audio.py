import asyncio

from util.client.client_cosmic import Cosmic, console
from config import ClientConfig as Config
from util.logger import get_logger
import numpy as np
import base64
import json
import websockets
from util.client.client_create_file import create_file
from util.client.client_write_file import write_file
from util.client.client_finish_file import finish_file
import uuid

# 获取日志记录器
logger = get_logger('client')



async def send_message(message):
    # 发送数据
    # 检查 websocket 是否存在且未关闭
    if Cosmic.websocket is None:
        if message['is_final']:
            Cosmic.audio_files.pop(message['task_id'])
            console.print('    服务端未连接，无法发送\n')
            logger.warning("服务端未连接，无法发送音频数据")
        return

    try:
        # 检查连接状态
        if hasattr(Cosmic.websocket, 'closed') and Cosmic.websocket.closed:
            if message['is_final']:
                Cosmic.audio_files.pop(message['task_id'])
                console.print('    服务端连接已关闭\n')
                logger.error("服务端连接已关闭")
            return

        await Cosmic.websocket.send(json.dumps(message))
        # logger.debug(f"发送音频片段，任务ID: {message['task_id']}, 是否最终: {message['is_final']}")

    except websockets.ConnectionClosedError:
        if message['is_final']:
            Cosmic.audio_files.pop(message['task_id'])
            console.print(f'[red]连接中断了')
            logger.error("WebSocket 连接中断")
    except websockets.ConnectionClosedOK:
        if message['is_final']:
            Cosmic.audio_files.pop(message['task_id'])
            console.print(f'[yellow]连接已正常关闭')
            logger.info("WebSocket 连接已正常关闭")
    except Exception as e:
        logger.error(f"发送音频数据时发生错误: {e}", exc_info=True)
        print('出错了')
        print(e)


async def send_audio():
    try:
        logger.debug("音频发送任务已启动")

        # 生成唯一任务 ID
        task_id = str(uuid.uuid1())
        logger.debug(f"创建新任务，任务ID: {task_id}")

        # 任务起始时间
        time_start = 0

        # 音频数据临时存放处
        cache = []
        duration = 0

        # 保存音频文件
        file_path, file = '', None

        # 开始取数据
        # task: {'type', 'time', 'data'}
        while task := await Cosmic.queue_in.get():
            Cosmic.queue_in.task_done()
            if task['type'] == 'begin':
                time_start = task['time']
                logger.debug(f"录音开始，时间戳: {time_start}")
            elif task['type'] == 'data':
                # 在阈值之前积攒音频数据
                if task['time'] - time_start < Config.threshold:
                    cache.append(task['data'])
                    continue

                # 创建音频文件
                if Config.save_audio and not file_path:
                    file_path, file = create_file(task['data'].shape[1], time_start)
                    Cosmic.audio_files[task_id] = file_path
                    logger.debug(f"创建音频文件: {file_path}")

                # 获取音频数据
                if cache:
                    data = np.concatenate(cache)
                    cache.clear()
                else:
                    data = task['data']

                # 保存音频至本地文件
                duration += len(data) / 48000
                if Config.save_audio:
                    write_file(file, data)

                # 发送音频数据用于识别
                message = {
                    'task_id': task_id,             # 任务 ID
                    'seg_duration': Config.mic_seg_duration,    # 分段长度
                    'seg_overlap': Config.mic_seg_overlap,      # 分段重叠
                    'is_final': False,              # 是否结束
                    'time_start': time_start,       # 录音起始时间
                    'time_frame': task['time'],     # 该帧时间
                    'source': 'mic',                # 数据来源：从麦克风收到的数据
                    'data': base64.b64encode(       # 数据
                                np.mean(data[::3], axis=1).tobytes()
                            ).decode('utf-8'),
                }
                task = asyncio.create_task(send_message(message))
            elif task['type'] ==  'finish':
                # 完成写入本地文件
                if Config.save_audio:
                    finish_file(file)
                    logger.debug("完成音频文件写入")

                console.print(f'任务标识：{task_id}')
                console.print(f'    录音时长：{duration:.2f}s')
                logger.info(f"录音任务完成，任务ID: {task_id}, 时长: {duration:.2f}s")

                # 告诉服务端音频片段结束了
                message = {
                    'task_id': task_id,
                    'seg_duration': 15,
                    'seg_overlap': 2,
                    'is_final': True,
                    'time_start': time_start,
                    'time_frame': task['time'],
                    'source': 'mic',
                    'data': '',
                }
                task = asyncio.create_task(send_message(message))
                break
    except Exception as e:
        logger.error(f"音频发送任务错误: {e}", exc_info=True)
        print(e)
