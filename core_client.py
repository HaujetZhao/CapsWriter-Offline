# coding: utf-8

import os
import sys
import platform
if platform.system() == 'Darwin' and os.getuid() != 0:
    print('在 MacOS 上需要以管理员启动客户端才能监听键盘活动，请 sudo 启动')
    input('按回车退出'); sys.exit()

from os import path, sep, makedirs, chmod
if 'BASE_DIR' not in globals():
    BASE_DIR = path.dirname(__file__); 
import rich.status
from rich.console import Console 
from rich.markdown import Markdown
from rich.theme import Theme
my_theme = Theme({'markdown.code':'cyan', 'markdown.item.number':'yellow'})
console = Console(highlight=False, soft_wrap=False, theme=my_theme)
console.line(2)
console.rule('[bold #d55252]CapsWriter Offline Client'); console.line()
console.print(f'当前基文件夹：[cyan underline]{BASE_DIR}', end='\n\n')

with console.status("载入模块中…", spinner="bouncingBall", spinner_style="yellow"):
    from pathlib import Path
    import time
    import re
    import wave
    import asyncio
    import queue
    import shutil
    from subprocess import Popen, PIPE
    from threading import Event, current_thread, Thread

    import keyboard
    import numpy as np
    import sounddevice as sd
    import websockets
    import pyclip
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    from util import hot_sub_zh     # 中文热词替换模块
    from util import hot_sub_en     # 英文热词替换模块
    from util import hot_sub_rule   # 自定义规则替换
console.print('[green4]模块加载完成', end='\n\n')




# ============================全局变量和检查区====================================

addr = '127.0.0.1'          # Server 地址
port = '6006'               # Server 端口

shortcut     = 'caps lock'  # 控制录音的快捷键，默认是 CapsLock
threshold    = 0.3          # 按下快捷键后，触发语音识别的时间阈值
restore_key  = True         # 录音完成，松开按键后，是否自动再按一遍，以恢复 CapsLock 或 Shift 等之前的状态
paste        = True         # 是否以写入剪切板然后模拟 Ctrl-V 粘贴的方式输出结果
restore_clip = True         # 模拟粘贴后是否恢复剪贴板

save_audio = True           # 是否保存录音文件
audio_root = BASE_DIR       # 保存录音文件保存的根目录
audio_name_len = 20         # 将录音识别结果的前多少个字存储到录音文件名中，建议不要超过200

trash_punc = '，。,.'        # 识别结果要消除的末尾标点

hot_zh = True               # 是否启用中文热词替换，中文热词存储在 hot_zh.txt 文件里
hot_sub_zh.多音字 = True     # True 表示多音字匹配
hot_sub_zh.声调  = False    # False 表示忽略声调区别，这样「黄章」就能匹配「慌张」

hot_en   = True             # 是否启用英文热词替换，英文热词存储在 hot_en.txt 文件里
hot_rule = True             # 是否启用自定义规则替换，自定义规则存储在 hot_rule.txt 文件里
hot_kwd  = True             # 是否启用关键词日记功能，自定义关键词存储在 keyword.txt 文件里

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





def do_save_audio(data:np.array, text:str, start_time:float):
    '''
    把录音保存到文件

    data:       np.array 格式的录音数据
    text:       语音识别文字结果
    start_time: 开始录音的时间戳

    如果用户安装了 FFmpeg，就保存为 mp3 格式
    '''
    header_md = r'''```txt
正则表达式 Tip

匹配到音频文件链接：\[(.+)\]\((.{10,})\)[\s]*
替换为 HTML 控件：<audio controls><source src="$2" type="audio/mpeg">$1</audio>\n\n

匹配 HTML 控件：<audio controls><source src="(.+)" type="audio/mpeg">(.+)</audio>\n\n
替换为文件链接：[$2]($1) 
```


'''

    time_year = time.strftime('%Y', time.localtime(start_time))
    time_month = time.strftime('%m', time.localtime(start_time))
    time_day = time.strftime('%d', time.localtime(start_time))
    time_hms = time.strftime('%H:%M:%S', time.localtime(start_time))
    time_ymdhms = time.strftime("%Y%m%d-%H%M%S", time.localtime(start_time))

    global audio_root
    folder_root = Path(audio_root)
    folder_path = folder_root / time_year / time_month
    folder_assets = folder_path / 'assets'

    for i in [] if folder_assets.exists() else [1]:
        # 创建路径
        makedirs(folder_assets, exist_ok=True)

        # 复制用于清理无用附件的 py 脚本
        clean_src = Path(BASE_DIR) / 'util' / 'clean-assets.py'
        clean_dst = Path(folder_path) / 'clean-assets.py'
        if clean_src.exists() and not clean_dst.exists():
            shutil.copy(clean_src, clean_dst)
            

        # 如果 Unix 以 root 身份运行客户端，会导致创建的文件不能被普通用户程序访问，要修改权限
        if platform.system() not in ['Darwin', 'Linux']: break
        from os import chown, chmod, geteuid, stat
        chown(folder_root, stat(BASE_DIR).st_uid, stat(BASE_DIR).st_gid)
        chmod(folder_root, stat(BASE_DIR).st_mode)
        for child in folder_root.glob('**'):
            if not child.is_dir(): continue
            chown(child, stat(BASE_DIR).st_uid, stat(BASE_DIR).st_gid)
            chmod(child, stat(BASE_DIR).st_mode)
        chown(clean_dst, stat(BASE_DIR).st_uid, stat(BASE_DIR).st_gid)
        break
    

    file_wav = folder_assets / f'({time_ymdhms}){text[:audio_name_len]}.wav'
    file_mp3 = file_wav.with_suffix('.mp3')
    file_audio = None

    if shutil.which('ffmpeg'):  # 用户已安装 ffmpeg，则输出为 mp3 格式
        file_audio = file_mp3
        # 将数据转换为字节形式
        data = data.tobytes()

        # 调用ffmpeg命令行
        ffmpeg_command = [
            'ffmpeg', '-y',
            '-f', 'f32le',      # 输入数据格式为有浮点32位小端字节序
            '-ar', '48000',     # 采样率为 48000 Hz
            '-ac', '2',         # 双声道
            '-i', '-',          # 从标准输入读取数据
            '-b:a', '192k',      # 输出比特率 192kbps
            file_audio
        ]

        # 执行ffmpeg命令行并将数据传递给标准输入
        process = Popen(ffmpeg_command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        process.communicate(input=data)
    else:                       # 用户未安装 ffmpeg，则输出为 wav 格式
        file_audio = file_wav   
        data = (data * (2**15-1)).astype(np.int16).tobytes()
        with wave.open(str(file_audio), 'w') as f:
            f.setnchannels(2)
            f.setsampwidth(2)
            f.setframerate(48000)
            f.setnchannels(2)
            f.setnchannels(2)
            f.writeframes(data)
    
    

    global kwd_list

    # 列表内的元素是元组，元组内包含了：关键词、md路径
    md_list = [(kwd, folder_path / f'{kwd + "-" if kwd else ""}{time_day}.md') for kwd in kwd_list if text.startswith(kwd)]
    
    # 为 md 文件写入识别记录
    for kwd, file_md in md_list:
        if not file_md.exists():    # 若文件还不存在，则创建并写入开头的提示性文字
            with open(file_md, 'w', encoding="utf-8") as f: f.write(header_md)
        with open(file_md, 'a', encoding="utf-8") as f: 
            f.write(f'[{time_hms}]({file_audio.relative_to(file_md.parent).as_posix().replace(" ", "%20")}) {text[len(kwd):].lstrip("，。,.")}\n\n')

    # 如果 Unix 以 root 身份运行客户端，会导致创建的文件不能被普通用户程序访问，要修改权限
    if platform.system() in ['Darwin', 'Linux']:
        from os import chown, chmod, geteuid, stat
        path_list = [file_audio]; path_list.extend([md[1] for md in md_list])
        for p in path_list: 
            chown(p, stat(BASE_DIR).st_uid, stat(BASE_DIR).st_gid)
            chmod(p, stat(BASE_DIR).st_mode)


async def do_connect_server():
    global websocket, addr, port
    if websocket is None or websocket.closed:
        try:
            websocket = await websockets.connect(f"ws://{addr}:{port}", max_size=None) 
        except ConnectionRefusedError as e:
            console.print(f'[bright_red]无法连接服务端，请检查服务端是否运行，端口是否正确 ')
            return False
    return True


async def do_recognize():
    global addr, port, websocket            # 服务端地址、端口
    global container0_in, container0_out    # 这是双声道高质量录音容器
    global container1_in, container1_out    # 这是单声道16000采样率录音容器
    global save_audio                       # 是否保存录音文件
    global finish_event                     # 用于接收录音结束的通知
    global trash_punc                       # 用于消除识别结果末尾标点
    global paste, restore_clip, restore_key
    global t1, t2
    
    # 记录开始时间
    start_time = time.time()      

    # 开始接收音频片段
    container0_in, container1_in = container0_out, container1_out

    # 等待录音结束的事件
    with console.status('开始录音', spinner='point') as status:
        await finish_event.wait()  

    # 不再接受新片段，取出音频片段，连接音频片段
    container0_in = container1_in  = None
    samples0 = container0_out.copy(); container0_out.clear()
    samples1 = container1_out.copy(); container1_out.clear()
    samples0 = np.concatenate(samples0)
    samples1 = np.concatenate(samples1)
    
    # 构造比特流
    buf = samples1.tobytes()

    retry_time = 3
    while True:
        # 确保服务端连接
        if not await do_connect_server():
            return False

        # 转录音频
        try:
            t1 = time.time()
            await websocket.send(buf)                           # 发送音频
            decoding_results = await websocket.recv()           # 接收结果
            decoding_results = decoding_results.strip(trash_punc)  # 消除末尾标点
            t2 = time.time()
        
        # 如果中途连接中断了，那就要重试几次
        except websockets.exceptions.ConnectionClosedError as e: 
            print(f'\r\033[2K 连接中断了，剩余重试次数：{retry_time} ')
            retry_time -= 1
            if retry_time < 0:
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
    if paste:   
        try: temp = pyclip.paste().decode('utf-8')
        except: temp = ''
        pyclip.copy(decoding_results);  # 复制
        if platform.system() == 'Darwin':      # 粘贴
            keyboard.press(55);keyboard.press(9);keyboard.release(55);keyboard.release(9)
        else:  keyboard.send('ctrl + v')    
        if restore_clip: await asyncio.sleep(0.1); pyclip.copy(temp)         # 还原剪贴板
    else:       # 模拟打印
        keyboard.write(decoding_results)
    
    # 终端显示结果
    console.print(f'识别结果：[green4]{decoding_results}')
    console.print(f'    录音时长：{len(samples1) / 16000: >8.2f}s')
    console.print(f'    识别时长：{t2 - t1: >8.2f}s')
    console.print(f'    Real Time Factor: {(t2-t1) / (len(samples1)/16000): >5.2f}')
    console.line()

    # 保存录音文件，方便用户检查录音质量、识别效果
    if save_audio:  
        do_save_audio(samples0, decoding_results, start_time)
    






def shortcut_handler(e: keyboard.KeyboardEvent) -> None:
    # 在我的 Windows 电脑上，left ctrl 和 right ctrl 的 keycode 都是一样的，
    # keyboard 库按 keycode 判断触发
    # 即便设置 right ctrl 触发，在按下 left ctrl 时也会触发
    # 不过，虽然两个按键的 keycode 一样，但事件 e.name 是不一样的
    # 在这里加一个判断，如果 e.name 不是我们期待的按键，就返回
    global shortcut
    key_expect = keyboard.normalize_name(shortcut).replace('left ', '')
    key_actual = e.name.replace('left ', '')
    if key_expect != key_actual: return False    
        
    global on           # 用于判断是否已开始录音、记录录音开始的时间
    global threshold    # 按下快捷键后，触发语音识别的时间阈值
    global restore_key      # 用于标识在用户松开按键后，再自动发送一下按键，以恢复 CapsLock 或 Shift 状态

    global loop_main    # 这是主线程的事件循环
    global coro_queue   # 主线程从这个队列中获取识别任务后，放入主事件循环
    global task_queue   # 主线程把识别任务放入主事件循环后，返回 Task，通过这个 Queue 传递
    global task     # 指向记录识别任务的 Task 对象，可调用 cancel() 终止任务

    global container1_in, container1_out    # 这是录音片段容器，当它指向 None 时，录音片段就不再写入
    global finish_event # 用于通知识别任务：录音结束了，可以开始识别了

    if e.event_type == 'down' and not on:
        on = time.time()                # 记录开始录音时间
        finish_event = asyncio.Event()  # 创建用于标志录音结束的 Event

        # 把识别任务放入主线程的队列，让主线程创建协程 Task
        asyncio.run_coroutine_threadsafe(coro_queue.put(do_recognize()), loop_main)
        # 主线程创建识别任务后，得到 Task，通过队列返回
        task = task_queue.get()

    elif e.event_type == 'up': 
        if time.time() - on < threshold:  # 如果持续按下 CapsLock 的时长小于 threshold 秒
            task.cancel()       # 取消识别任务
            container1_in = None    # 删除录音，并停止接收录音
            print('', end='\r', flush=True)
        elif restore_key:
            time.sleep(0.01)    
            keyboard.send(shortcut)  # 松开快捷键后，再按一次，恢复 CapsLock 或 Shift 等按键的状态
        
        loop_main.call_soon_threadsafe(finish_event.set) # 通知识别任务：录音停止了，可以识别了
        on = False              # 全局标识已停止录音







def record():
    global container0_in, container1_in
    global stream, t1, t2
    global to_exit

    while not to_exit:
        data = stream.read(int(0.05 * 48000))[0]
        data2 = np.mean(data[::3], axis=1)
        if not any(x is None for x in (container0_in, container1_in)): 
            try:
                container0_in.append(data)
                container1_in.append(data2)
            except: ...

    stream.close()


def stream_open():
    # 显示录音所用的音频设备
    channels = 1
    try:
        device = sd.query_devices(kind='input')
        channels = device['max_input_channels']
        console.print(f'使用默认音频设备：[italic]{device["name"]}', end='\n\n')
    except UnicodeDecodeError:
        console.print("由于编码问题，暂时无法获得麦克风设备名字", end='\n\n', style='bright_red')
        

    # 打开音频流
    # 由于 sounddevice 在 MacOS 上使用 callback 的方法会导致闪退
    # 所以打开一个新的线程，用于收集音频
    global stream
    stream = sd.InputStream(
        channels=channels,
        dtype="float32",
        samplerate=48000,
        blocksize=int(0.05 * 48000),  # 0.05 seconds
    ); stream.start()
    Thread(target=record, daemon=True).start()

    return stream






def do_updata_kwd(kwd_text: str):
    '''
    把关键词文本中的每一行去除多余空格后添加到列表，
    '''
    global kwd_list
    kwd_list.clear(); kwd_list.append('')
    for kwd in kwd_text.splitlines():
        kwd = kwd.strip()
        if not kwd or kwd.startswith('#'): continue
        kwd_list.append(kwd)
    return len(kwd_list)


def do_update_hot_words(hot_zh=False, hot_en=False, hot_rule=False, hot_kwd=False):
    global BASE_DIR, path_zh, path_en, path_rule, path_kwds

    path_zh = BASE_DIR + sep + "hot-zh.txt"
    path_en = BASE_DIR + sep + "hot-en.txt"
    path_rule = BASE_DIR + sep + "hot-rule.txt"
    path_kwds = BASE_DIR + sep + "keywords.txt"

    if hot_zh:
        if not path.exists(path_zh):
            with open(path_zh, "w", encoding="utf-8") as f:
                f.write('# 在此文件放置中文热词，每行一个，开头带井号表示注释，会被省略')
        with open(path_zh, "r", encoding="utf-8") as f: 
            num_hot_zh = hot_sub_zh.更新热词词典(f.read())
        console.print(f'已载入 [green4]{num_hot_zh:5}[/] 条中文热词')
    if hot_en:
        if not path.exists(path_en):
            with open(path_en, "w", encoding='utf-8') as f:
                f.write('# 在此文件放置英文热词 \n# Put English hot words here, one per line. Line starts with # will be ignored. ')
        with open(path_en, "r", encoding="utf-8") as f: 
            num_hot_en = hot_sub_en.更新热词词典(f.read())
        console.print(f'已载入 [green4]{num_hot_en:5}[/] 条英文热词')
    if hot_rule:
        if not path.exists(path_rule):
            with open(path_rule, "w", encoding='utf-8') as f:
                f.write('# 在此文件放置自定义规则，规则是每行一条的文本，以 # 开头的会被忽略，将查找和匹配用等号隔开，文本两边的空格会被省略。例如：\n\n毫安时 = mAh\n赫兹 = Hz')
        with open(path_rule, "r", encoding="utf-8") as f: 
            num_hot_rule = hot_sub_rule.更新热词词典(f.read())
        console.print(f'已载入 [green4]{num_hot_rule:5}[/] 条自定义替换规则')
    if hot_kwd:
        if not path.exists(path_kwds):
            with open(path_kwds, "w", encoding='utf-8') as f:
                f.write('# 在此文件放置日记关键词，每行一个，开头带井号表示注释，会被省略\n# 当识别结果以关键词开头时，会被记录到 「年份/月份/关键词-日期.md」文件中\n重要\n健康\n学习')
        with open(path_kwds, "r", encoding="utf-8") as f: 
            num_kwd = do_updata_kwd(f.read())
        console.print(f'已载入 [green4]{num_kwd:5}[/] 条日记关键词')


class HotHandler(FileSystemEventHandler):
    '''用于动态更新热词的处理器'''
    last_time = 0
    def on_modified(self, event):
        if time.time() - self.last_time < 1:  # 事件间隔小于2秒就取消
            return
        try:
            if event.src_path not in [path_zh, path_en, path_rule]: return
            time.sleep(0.2)     # 延迟0.2秒，避免编辑器还没有将热词文件更新完成导致读空

            console.print('[green4]检测到配置文件更新，[/]', end='')
            if event.src_path == path_zh :
                self.last_time = time.time()
                do_update_hot_words(hot_zh=hot_zh)
            elif event.src_path == path_en:
                self.last_time = time.time()
                do_update_hot_words(hot_en=hot_en)
            elif event.src_path == path_rule:
                self.last_time = time.time()
                do_update_hot_words(hot_rule=hot_rule)
            elif event.src_path == path_kwds:
                self.last_time = time.time()
                do_update_hot_words(hot_kwd=hot_kwd)
            console.line()
        except Exception as e:
            console.print(f'更新热词失败：{e}', style='bright_red')







def show_tips():
    console.print(f'\n服务端地址： [cyan underline]{addr}:{port}')
    console.print(f'\n当前所用快捷键：[green4]{shortcut}')
    console.print(f'\n项目地址：[cyan underline]https://github.com/HaujetZhao/CapsWriter-Offline', end='\n\n')
    MARKDOWN = (f'''

你好，这是 **CapsWriter** 简陋的离线版，一个好用的语音输入工具。

使用步骤：
                
1. 运行 Server 端，它会载入语音和标点模型（共占用约 1.5GB 的内存）
2. 运行 Client 端，它会打开系统默认麦克风
3. 按住 `{shortcut}` 键，录音开始，松开 `{shortcut}` 键，录音结束，识别结果立刻被输入

功能特性：

1. 完全离线、低延迟、高准确率、中英混输、自动阿拉伯数字、自动调整中英间隔
2. 热词功能：可以在 `hot-en.txt hot-zh.txt hot-rule.txt` 中添加三种热词，客户端动态载入
3. 日记功能：默认每次录音识别后，识别结果记录在 `年份/月份/日期.md` ，录音文件保存在 `年份/月份/assets` 
4. 关键词日记：识别结果若以关键词开头，会被记录在 `年份/月份/关键词-日期.md`，关键词在 `keywords.txt` 中定义
5. 服务端、客户端分离，可以服务多台客户端
6. 编辑 `core_client.py` ，可以配置服务端地址、快捷键、录音开关……

注意事项：

1. 语音模型为 `Paraformer` 非流式，录完再转，录得越长，上屏延迟越大。主流性能电脑每 10s 录音需约 0.5s 转录。
2. 当用户安装了 `FFmpeg` 时，会以 `mp3` 格式保存录音；当用户没有装 `FFmpeg` 时，会以 `wav` 格式保存录音
3. 默认的快捷键是 {shortcut}，你可以打开 `core_client.py` 进行修改
4. MacOS 无法监测到 `caps lock` 按键，可改为 `right shift` 按键
    ''')
    console.print(Markdown(MARKDOWN), highlight=1); console.line()
    
    console.rule('[green3]现在可以开始识别了'); console.line()


async def main():
    global loop_main;       loop_main = asyncio.get_event_loop()
    global coro_queue;      coro_queue = asyncio.Queue()    # 用于存放录音 coroutine
    global task_queue;      task_queue = queue.Queue()      # 用于存放录音 Task
    global websocket;       websocket = None    # 全局连接对象
    global on;              on = False          # 录音开关标识
    global to_exit;         to_exit = False     # 用于提醒录音线程该关闭了
    global kwd_list;        kwd_list = []       # 用于存储日记快捷键
    global shortcut                             # 快捷键
    global container0_in, container0_out    # 这是双声道高质量录音容器
    global container1_in, container1_out    # 这是单声道16000采样率录音容器
    global observer         # 将文件监控器设为全局变量，方便退出时回收资源
    global stream           # 将麦克风音频流设为全局变量，方便退出时回收资源
    container0_in, container0_out = None, []
    container1_in, container1_out = None, []

    # 打开音频流
    stream = stream_open()

    # 快捷键绑定到函数
    keyboard.hook_key(shortcut, shortcut_handler)

    # 载入热词，并监控热词文件的修改，动态更新热词
    try:
        do_update_hot_words(hot_zh, hot_en, hot_rule, hot_kwd=hot_kwd)
    except Exception as e:
        console.print(f'载入热词失败，常见原因一般是热词文件没有使用 UTF-8 编码\n{e}', style = 'bright_red')
    observer = Observer()
    observer.schedule(HotHandler(), BASE_DIR, recursive=False)
    observer.start()


    # 打印说明
    show_tips()

    # 不断从队列获取识别任务，提交到事件循环执行，用队列返回 Task 对象
    while True:
        recog_coro = await coro_queue.get()
        task_queue.put(loop_main.create_task(recog_coro))


def init():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print(f'再见！')
        to_exit = True      # 提醒录音线程，该关闭了
        keyboard.unhook_all()
        observer.stop()     # 关闭文件监控
        sys.exit()

if __name__ == "__main__":
    init()