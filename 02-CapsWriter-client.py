from os import path, mkdir; BASE_PATH = path.dirname(__file__)

import time
import wave
import asyncio
import queue
from threading import Event, current_thread

import keyboard
import numpy as np
import sounddevice as sd
import websockets
import colorama; colorama.init()

addr = '127.0.0.1'
port = '6006'
save_audio = True


async def recognize():
    global addr, port      # 服务端地址、端口
    global save_audio       # 是否保存录音文件

    global container    # 这是录音片段容器，将它指向列表时，会有音频片段涌入
    global finish_event # 用于接收通知：录音结束了，可以开始识别了

    container = []      # 开始使用列表接受录音片段
    print(f'开始录音...', end="", flush=True)

    await finish_event.wait()  # 等待录音结束的事件

    # 取出录音，删除旧的录音容器，不再接受录音
    clips_list, container = container, None

    # 将录音片段连接
    samples = np.concatenate([k.reshape(-1) for k in clips_list])

    # 构造比特流
    buf = (16000).to_bytes(4, byteorder="little")  # 4 bytes
    buf += (samples.size * 4).to_bytes(4, byteorder="little")
    buf += samples.tobytes()

    try:
        # 向 socket 端发送音频，得到识别结果
        async with websockets.connect(
            f"ws://{addr}:{port}"
        ) as websocket:
            t1 = time.time()
            await websocket.send(buf)
            decoding_results = await websocket.recv()
            t2 = time.time()
    except ConnectionRefusedError as e:
        print(f'\x9b31m 无法连接服务端，请检查服务端是否运行，端口是否正确 \x9b0m')
        return False
        
    # 打印结果
    keyboard.write(decoding_results)
    print(f'\r\x9b2K识别结果：\x9b32m{decoding_results}\x9b0m')
    print(f'    录音时长：{len(samples) / 16000: >8.2f}s')
    print(f'    识别时长：{t2 - t1: >8.2f}s')
    print(f'    Real Time Factor: {(t2-t1) / (len(samples)/16000): >5.2f}\n')

    # 保存录音文件，方便用户检查录音质量、识别效果
    if not save_audio: 
        return
    if not path.exists(f'{BASE_PATH}/audios'):
        mkdir(f'{BASE_PATH}/audios')
    filename = f'({time.strftime("%Y%m%d-%H%M%S")}){decoding_results[:20]}.wav'
    with wave.open(f'{BASE_PATH}/audios/{filename}', 'wb') as f:
        f.setframerate(16000)
        f.setnchannels(1)
        f.setsampwidth(2)
        f.writeframes((samples * 32768).astype(np.int16))
    
def caps_handler(e: keyboard.KeyboardEvent) -> None:
    global on       # 用于判断是否已开始录音、记录录音开始的时间

    global loop_main    # 这是主线程的事件循环
    global coroutine_queue  # 主线程从这个队列中获取识别任务后，放入主事件循环
    global task_queue       # 主线程把识别任务放入主事件循环后，返回 Task，通过这个 Queue 传递
    global task     # 指向记录识别任务的 Task 对象，可调用 cancel() 终止任务

    global container    # 这是录音片段容器，当它指向 None 时，录音片段就不再写入
    global finish_event # 用于通知识别任务：录音结束了，可以开始识别了

    if e.event_type == 'down' and not on:
        on = time.time()                # 记录开始录音时间
        finish_event = asyncio.Event()  # 创建用于标志录音结束的 Event

        # 把识别任务放入主线程的队列，让主线程创建协程 Task
        asyncio.run_coroutine_threadsafe(coroutine_queue.put(recognize()), loop_main)
        # 主线程创建识别任务后，得到 Task，通过队列返回
        task = task_queue.get()

    elif e.event_type == 'up': 
        if time.time() - on < 0.3:  # 如果持续按下 CapsLock 的时长小于 0.3 秒
            task.cancel()       # 取消识别任务
            container = None    # 删除录音，并停止接收录音
            print('\r\x9b2K', end='', flush=True)
        else:
            time.sleep(0.01)    
            keyboard.send('caps lock')  # 恢复 CapsLock 状态
        
        loop_main.call_soon_threadsafe(finish_event.set) # 通知识别任务：录音停止了，可以识别了
        on = False              # 全局标识已停止录音

async def main():
    global on; on = False
    
    # 全局的列表，存放音频容器
    global container; container = None

    global loop_main;    loop_main = asyncio.get_event_loop()
    global coroutine_queue;   coroutine_queue = asyncio.Queue()
    global task_queue;   task_queue = queue.Queue()

    def record_callback(indata, frame_count, time_info, status):
        if container is None:    # 若容器不可用，就算了
            return None
        container.append(indata.copy())

    devices = sd.query_devices()
    default_input_device_idx = sd.default.device[0]
    print(f'使用默认音频设备：{devices[default_input_device_idx]["name"]}\n')

    # 打开音频流
    stream = sd.InputStream(
        callback=record_callback,
        channels=1,
        dtype="float32",
        samplerate=16000,
        blocksize=int(0.05 * 16000),  # 0.05 seconds
    )
    stream.start()

    # 快捷键 Caps 绑定到函数
    keyboard.hook_key('caps lock', caps_handler)

    print(f'服务端地址：{addr}:{port}')
    print('''
你好，这是 \x9b33mCapsWriter 简陋的离线版\x9b0m，一个语音输入工具。
使用步骤：
    1. 运行 sherpa-onnx-server 脚本，它会载入 Paraformer 模型识别模型（这会占用1GB的内存）
    2. 运行本脚本，脚本会打开系统默认麦克风
    3. 按住 CapsLock 键，录音开始，松开 CapsLock 键，录音结束，识别结果立马被输入（录音时长短于0.3秒不算）

注意事项：
    1. 目前使用的模型是 Paraformer 非实时模型，即录完再转，因此录音时间越长，上屏延迟越大。
    2. 主流性能的 Windows 笔记本，RTF 大约 0.06，即大约每10s 录音需 0.6s 转录时长。
    3. 本地模型对算力要求非常低，基本无需担心性能问题
    4. 暂不支持标点符号，暂不支持逆标准化（如把中文数字转阿拉伯数字）
    5. 为方便用户检查录音质量、识别效果，脚本默认开启了保存录音，所有都被保存在了 audios 文件夹
    ''')

    # 不断从队列获取识别任务，提交到事件循环执行，用队列返回 Task 对象
    while True:
        recog_coro = await coroutine_queue.get()
        task_queue.put(loop_main.create_task(recog_coro))
    
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f'用户停止了客户端，再见！')
