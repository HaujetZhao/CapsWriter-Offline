import keyboard
from util.client_cosmic import Cosmic, console
from config import ClientConfig as Config

import time
import asyncio
from util.client_send_audio import send_audio

task_send = asyncio.Future()
status = console.status('开始录音', spinner='point')


def shortcut_correct(e: keyboard.KeyboardEvent):
    # 在我的 Windows 电脑上，left ctrl 和 right ctrl 的 keycode 都是一样的，
    # keyboard 库按 keycode 判断触发
    # 即便设置 right ctrl 触发，在按下 left ctrl 时也会触发
    # 不过，虽然两个按键的 keycode 一样，但事件 e.name 是不一样的
    # 在这里加一个判断，如果 e.name 不是我们期待的按键，就返回
    key_expect = keyboard.normalize_name(Config.shortcut).replace('left ', '')
    key_actual = e.name.replace('left ', '')
    if key_expect != key_actual: return False    
    return True


def shortcut_handler(e: keyboard.KeyboardEvent) -> None:
    global task_send
    if not shortcut_correct(e):
        return

    if e.event_type == 'down' and not Cosmic.on:
        # 记录开始时间
        t1 = time.time()
        # 向队列标识时间
        asyncio.run_coroutine_threadsafe(
            Cosmic.queue_in.put({'type': 'begin', 'time': t1, 'data': None}),
            Cosmic.loop
        )
        # on 既用于全局记录时间，又用于标识「录音线程可以向队列放数据」
        Cosmic.on = t1
        # 打印动画：正在录音
        status.start()
        # 启动识别任务
        task_send = asyncio.run_coroutine_threadsafe(
            send_audio(),
            Cosmic.loop,
        )
    elif e.event_type == 'up':
        # 记录持续时间，并标识录音线程停止向队列放数据
        duration = time.time() - Cosmic.on
        Cosmic.on = False
        status.stop()
        # 若持续小于 0.3s，则取消任务
        if duration < Config.threshold:
            task_send.cancel()
        else:
            asyncio.run_coroutine_threadsafe(
                Cosmic.queue_in.put(
                    {'type': 'finish',
                     'time': time.time(),
                     'data': None
                     },
                ),
                Cosmic.loop
            )

            # 松开快捷键后，再按一次，恢复 CapsLock 或 Shift 等按键的状态
            if Config.restore_key:
                time.sleep(0.01)
                keyboard.send(Config.shortcut)