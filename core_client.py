# coding: utf-8

from os import path, sep, mkdir; 
if 'BASE_DIR' not in globals():
    BASE_DIR = path.dirname(__file__); 
print(f'当前基文件夹：{BASE_DIR}')
import time
import re
import wave
import asyncio
import queue
from threading import Event, current_thread

import colorama; colorama.init()
import keyboard
import numpy as np
import sounddevice as sd
import websockets

import hot_sub_zh   # 中文热词替换模块
import hot_sub_en   # 英文热词替换模块
import hot_sub_rule   # 自定义规则替换



# ============================全局变量和检查区====================================

addr = '127.0.0.1'          # Server 地址
port = '6006'               # Server 端口

shortcut  = 'caps lock'     # 控制录音的快捷键，默认是 CapsLock
threshold = 0.3             # 按下快捷键后，触发语音识别的时间阈值
restore   = True            # 录音完成，松开按键后，是否自动再按一遍，以恢复 CapsLock 或 Shift 等之前的状态

save_audio = True           # 是否保存录音文件
trash_punc = '，。,.'        # 识别结果要消除的末尾标点

hot_zh = True              # 是否启用中文热词替换，中文热词存储在 hot_zh.txt 文件里
hot_sub_zh.多音字 = True    # True 表示多音字匹配
hot_sub_zh.声调  = False    # False 表示忽略声调区别，这样「黄章」就能匹配「慌张」

hot_en = True              # 是否启用英文热词替换，英文热词存储在 hot_en.txt 文件里

hot_rule = True            # 是否启用自定义规则替换，自定义规则存储在 hot_rule.txt 文件里

# ============================快捷键名字参考====================================

'''
如果你想修改快捷键，又不确定按键的拼写，可以从这里参考：

    'escape': 'esc',
    'return': 'enter',
    'del': 'delete',
    'control': 'ctrl',

    'left arrow': 'left',
    'up arrow': 'up',
    'down arrow': 'down',
    'right arrow': 'right',

    ' ': 'space', # Prefer to spell out keys that would be hard to read.
    '\x1b': 'esc',
    '\x08': 'backspace',
    '\n': 'enter',
    '\t': 'tab',
    '\r': 'enter',

    'scrlk': 'scroll lock',
    'prtscn': 'print screen',
    'prnt scrn': 'print screen',
    'snapshot': 'print screen',
    'ins': 'insert',
    'pause break': 'pause',
    'ctrll lock': 'caps lock',
    'capslock': 'caps lock',
    'number lock': 'num lock',
    'numlock': 'num lock',
    'space bar': 'space',
    'spacebar': 'space',
    'linefeed': 'enter',
    'win': 'windows',

    # Mac keys
    'command': 'windows',
    'cmd': 'windows',
    'control': 'ctrl',
    'option': 'alt',

    'app': 'menu',
    'apps': 'menu',
    'application': 'menu',
    'applications': 'menu',

    'pagedown': 'page down',
    'pageup': 'page up',
    'pgdown': 'page down',
    'pgup': 'page up',

    'play/pause': 'play/pause media',

    'num multiply': '*',
    'num divide': '/',
    'num add': '+',
    'num plus': '+',
    'num minus': '-',
    'num sub': '-',
    'num enter': 'enter',
    'num 0': '0',
    'num 1': '1',
    'num 2': '2',
    'num 3': '3',
    'num 4': '4',
    'num 5': '5',
    'num 6': '6',
    'num 7': '7',
    'num 8': '8',
    'num 9': '9',

    'left win': 'left windows',
    'right win': 'right windows',
    'left control': 'left ctrl',
    'right control': 'right ctrl',
    'left menu': 'left alt', # Windows...
    'altgr': 'alt gr',

'''

# ========================================================================



async def connect_server():
    global websocket, addr, port
    if websocket is None or websocket.closed:
        try:
            websocket = await websockets.connect(f"ws://{addr}:{port}") 
        except ConnectionRefusedError as e:
            print(f'\r\x9b2K\x9b31m 无法连接服务端，请检查服务端是否运行，端口是否正确 \x9b0m')
            return False
    return True



async def recognize():
    global addr, port, websocket            # 服务端地址、端口
    global container_in, container_out      # 这是录音容器
    global save_audio                       # 是否保存录音文件
    global finish_event                     # 用于接收录音结束的通知
    global trash_punc                       # 用于消除识别结果末尾标点

    # 开始接收音频片段
    container_in = container_out      
    print(f'开始录音...', end="", flush=True)

    # 等待录音结束的事件
    await finish_event.wait()  

    # 不再接受新片段，取出音频片段，连接音频片段
    container_in = None
    samples = container_out.copy(); container_out.clear()
    samples = np.concatenate([k.reshape(-1) for k in samples])

    # 构造比特流
    buf = (16000).to_bytes(4, byteorder="little")  # 4 bytes
    buf += (samples.size * 4).to_bytes(4, byteorder="little")
    buf += samples.tobytes()

    
    retry_time = 3
    while True:
        # 确保服务端连接
        if not await connect_server():
            return False

        # 转录音频
        try:
            t1 = time.time()
            await websocket.send(buf)                           # 发送音频
            decoding_results = await websocket.recv()           # 接收结果
            decoding_results = decoding_results.strip(trash_punc)  # 消除末尾标点
            t2 = time.time()
        
        # 如果中途连接中断了，那就要重试几次
        except websockets.exceptions.ConnectionClosedError: 
            print(f'\r\x9b2K\x9b31m 连接中断了，剩余重试次数：{retry_time} \x9b0m')
            retry_time -= 1
            if retry_time <= 0:
                return False
            continue
        
        break

    # 热词替换
    if hot_zh: 
        decoding_results = hot_sub_zh.热词替换(decoding_results)
    if hot_en: 
        decoding_results = hot_sub_en.热词替换(decoding_results)
    if hot_rule: 
        decoding_results = hot_sub_rule.热词替换(decoding_results)
        
    # 打印结果
    keyboard.write(decoding_results)
    print(f'\r\x9b2K识别结果：\x9b32m{decoding_results}\x9b0m')
    print(f'    录音时长：{len(samples) / 16000: >8.2f}s')
    print(f'    识别时长：{t2 - t1: >8.2f}s')
    print(f'    Real Time Factor: {(t2-t1) / (len(samples)/16000): >5.2f}\n')

    # 保存录音文件，方便用户检查录音质量、识别效果
    if not save_audio:  return
    if not path.exists(f'{BASE_DIR}/audios'): mkdir(f'{BASE_DIR}/audios')
    filename = f'({time.strftime("%Y%m%d-%H%M%S")}){decoding_results[:20]}.wav'.replace(':', '_')
    with wave.open(f'{BASE_DIR}/audios/{filename}', 'wb') as f:
        f.setframerate(16000)
        f.setnchannels(1)
        f.setsampwidth(2)
        f.writeframes((samples * 32768).astype(np.int16))
    
def shortcut_handler(e: keyboard.KeyboardEvent) -> None:
    # 在我的 Windows 电脑上，left ctrl 和 right ctrl 的 keycode 都是一样的，
    # keyboard 库按 keycode 判断触发
    # 即便设置 right ctrl 触发，在按下 left ctrl 时也会触发
    # 不过，虽然两个按键的 keycode 一样，但事件 e.name 是不一样的
    # 在这里加一个判断，如果 e.name 不是我们期待的按键，就返回
    global shortcut
    if keyboard.normalize_name(shortcut).replace('left ', '') != e.name.replace('left ', ''): return False    
        
    global on           # 用于判断是否已开始录音、记录录音开始的时间
    global threshold    # 按下快捷键后，触发语音识别的时间阈值
    global restore      # 用于标识在用户松开按键后，再自动发送一下按键，以恢复 CapsLock 或 Shift 状态

    global loop_main    # 这是主线程的事件循环
    global coro_queue   # 主线程从这个队列中获取识别任务后，放入主事件循环
    global task_queue   # 主线程把识别任务放入主事件循环后，返回 Task，通过这个 Queue 传递
    global task     # 指向记录识别任务的 Task 对象，可调用 cancel() 终止任务

    global container_in, container_out    # 这是录音片段容器，当它指向 None 时，录音片段就不再写入
    global finish_event # 用于通知识别任务：录音结束了，可以开始识别了

    if e.event_type == 'down' and not on:
        on = time.time()                # 记录开始录音时间
        finish_event = asyncio.Event()  # 创建用于标志录音结束的 Event

        # 把识别任务放入主线程的队列，让主线程创建协程 Task
        asyncio.run_coroutine_threadsafe(coro_queue.put(recognize()), loop_main)
        # 主线程创建识别任务后，得到 Task，通过队列返回
        task = task_queue.get()

    elif e.event_type == 'up': 
        if time.time() - on < threshold:  # 如果持续按下 CapsLock 的时长小于 threshold 秒
            task.cancel()       # 取消识别任务
            container_in = None    # 删除录音，并停止接收录音
            print('\r\x9b2K', end='', flush=True)
        elif restore:
            time.sleep(0.01)    
            keyboard.send(shortcut)  # 松开快捷键后，再按一次，恢复 CapsLock 或 Shift 等按键的状态
        
        loop_main.call_soon_threadsafe(finish_event.set) # 通知识别任务：录音停止了，可以识别了
        on = False              # 全局标识已停止录音



def record_callback(indata, frame_count, time_info, status):
    global container_in
    if container_in is None:    # 若容器不可用，就算了
        return None
    container_in.append(indata.copy())

def record_open():
    # 显示录音所用的音频设备
    try:
        device = sd.query_devices(kind='input')
        print(f'\n使用默认音频设备：{device["name"]}')
    except UnicodeDecodeError:
        print("\n由于编码问题，暂时无法获得麦克风设备名字")

    # 打开音频流
    stream = sd.InputStream(
        callback=record_callback,
        channels=1,
        dtype="float32",
        samplerate=16000,
        blocksize=int(0.05 * 16000),  # 0.05 seconds
    ); stream.start()

    return stream

def init_hot_words():
    global BASE_DIR, hot_zh, hot_en, hot_rule

    path_zh = BASE_DIR + sep + "hot-zh.txt"
    path_en = BASE_DIR + sep + "hot-en.txt"
    path_rule = BASE_DIR + sep + "hot-rule.txt"

    if hot_zh:
        if not path.exists(path_zh):
            with open(path_zh, "w", encoding="utf-8") as f:
                f.write('# 在此文件放置中文热词，每行一个，开头带井号表示注释，会被省略')
        with open(path_zh, "r", encoding="utf-8") as f: 
            num_hot_zh = hot_sub_zh.更新热词词典(f.read())
        print(f'\n\x9b32m已载入 {num_hot_zh:5} 条中文热词\x9b0m')
    if hot_en:
        if not path.exists(path_en):
            with open(path_en, "w", encoding='utf-8') as f:
                f.write('# 在此文件放置英文热词 \n# Put English hot words here, one per line. Line starts with # will be ignored. ')
        with open(path_en, "r", encoding="utf-8") as f: 
            num_hot_en = hot_sub_en.更新热词词典(f.read())
        print(f'\x9b32m已载入 {num_hot_en:5} 条英文热词\x9b0m')
    if hot_rule:
        if not path.exists(path_rule):
            with open(path_rule, "w", encoding='utf-8') as f:
                f.write('# 在此文件放置自定义规则，规则是每行一条的文本，以 # 开头的会被忽略，将查找和匹配用等号隔开，文本两边的空格会被省略。例如：\n\n毫安时 = mAh\n赫兹 = Hz')
        with open(path_rule, "r", encoding="utf-8") as f: 
            num_hot_rule = hot_sub_rule.更新热词词典(f.read())
        print(f'\x9b32m已载入 {num_hot_rule:5} 条自定义替换规则\x9b0m\n')



def show_tips():
    print(f'服务端地址：\x9b33m{addr}:{port}\x9b0m')
    print(f'''
当前所用快捷键：{shortcut}

项目地址：\x9b36mhttps://github.com/HaujetZhao/CapsWriter-Offline\x9b0m

你好，这是 \x9b33mCapsWriter 简陋的离线版\x9b0m，一个语音输入工具。
使用步骤：
    1. 运行 Server 端，它会载入 Paraformer 模型识别模型（这会占用1GB的内存）
    2. 运行 Client 端，它会打开系统默认麦克风
    3. 按住 {shortcut} 键，录音开始，松开 {shortcut} 键，录音结束，识别结果立马被输入（录音时长短于0.3秒不算）

注意事项：
    1. 目前使用的模型是 Paraformer 非实时模型，即录完再转，因此录音时间越长，上屏延迟越大。
    2. 主流性能的 Windows 笔记本，RTF 大约 0.06，即大约每10s 录音需 0.6s 转录时长。
    3. 本地模型对算力要求非常低，基本无需担心性能问题
    4. 为方便用户检查录音质量、识别效果，脚本默认开启了保存录音，所有都被保存在了 audios 文件夹
    5. 默认的快捷键是 {shortcut}，你可以打开 core_client.py 进行修改
    6. 你可以在  hot-en.txt  hot-zh.txt  hot-rule.txt  中添加热词，客户端会在启动时载入热词
    ''')


async def main():
    global loop_main;       loop_main = asyncio.get_event_loop()
    global coro_queue;      coro_queue = asyncio.Queue()    # 用于存放录音 coroutine
    global task_queue;      task_queue = queue.Queue()      # 用于存放录音 Task
    global websocket;       websocket = None    # 全局连接对象
    global on;              on = False          # 录音开关标识
    global shortcut                             # 快捷键
    global container_in,    container_out       # 音频容器
    container_in, container_out = None, []

    # 打开音频流
    stream = record_open()

    # 快捷键绑定到函数
    keyboard.hook_key(shortcut, shortcut_handler)

    # 载入热词
    try:
        init_hot_words()
    except Exception as e:
        print(f'载入热词失败，常见原因一般是热词文件没有使用 UTF-8 编码\n{e}')

    # 打印说明
    show_tips()

    # 不断从队列获取识别任务，提交到事件循环执行，用队列返回 Task 对象
    while True:
        recog_coro = await coro_queue.get()
        task_queue.put(loop_main.create_task(recog_coro))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f'再见！')
        exit()
