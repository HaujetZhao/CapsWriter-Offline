
from os import path, sep, mkdir, makedirs
import sys
if 'BASE_DIR' not in globals():
    BASE_DIR = path.dirname(__file__); 
import rich
from rich.console import Console 
console = Console(highlight=False)
console.line(2)
console.rule('[bold #d55252]CapsWriter Offline Server'); console.line()
console.print(f'当前基文件夹：[cyan underline]{BASE_DIR}', end='\n\n')

from pathlib import Path
import time
import asyncio
import re
from string import digits, ascii_letters

import numpy as np
import websockets
import sherpa_onnx
from funasr_onnx import CT_Transformer

from util.chinese_itn import chinese_to_num


# ============================全局变量和检查区====================================

addr = '0.0.0.0'
port = '6006'

format_num      = True      # 输出时是否将中文数字转为阿拉伯数字
format_punc     = True      # 输出时是否启用标点符号引擎（在 MacOS 上标点引擎似乎有问题，应当改为 False）
format_spell    = True      # 输出时是否调整中英之间的空格

model_dir = Path(BASE_DIR) / 'models'
paraformer_path = Path(BASE_DIR) / 'models' / 'paraformer-offline-zh' / 'model.onnx'
tokens_path = Path(BASE_DIR) / 'models' / 'paraformer-offline-zh' / 'tokens.txt'
punc_model_dir = Path(BASE_DIR) / 'models' / 'punc_ct-transformer_zh-cn' 

class args:
    paraformer = f'{paraformer_path}' 
    tokens = f'{tokens_path}'
    num_threads = 3
    num_threads = 3
    sample_rate = 16000
    feature_dim = 80
    decoding_method = 'greedy_search'
    debug = False


for path in (paraformer_path, tokens_path, punc_model_dir,):
    if path.exists(): continue
    console.print(f'''
    未能找到模型文件 

    未找到：{path}

    本服务端需要 paraformer-offline-zh 模型和 punc_ct-transformer_zh-cn 模型，
    请下载模型并放置到： {model_dir} 
    
    下载地址在： https://github.com/HaujetZhao/CapsWriter-Offline/releases/tag/v0.3 

    ''', style='bright_red'); input('按回车退出'); sys.exit()

# ========================================================================

en_in_zh = re.compile(r"""(?ix)    # i 表示忽略大小写，x 表示开启注释模式
    ([\u4e00-\u9fa5]|[a-z0-9]+\s)?      # 左侧是中文，或者英文加空格
    ([a-z0-9 ]+)                    # 中间是一个或多个「英文数字加空格」
    ([\u4e00-\u9fa5]|[a-z0-9]+)?       # 右是中文，或者英文加空格
""")

def adjust_space(original: re.Match):
    left : str = original.group(1)
    center : str = original.group(2)
    right : str = original.group(3)
    # 如果拼写字母中间有空格，就把空格都去掉
    if center:
        final = re.sub(r'((\d) )?(\b\w) ?(?!\w{2})', r'\2\3', center).strip()
        # 测试地址 https://regex101.com/r/1Vtu7V/1
        # final = re.sub(r'(\b\w) (?!\w{2})', r'\1', original.group(2)).strip()
    
    # 如果英文的左边有汉字或英文，给两组之间加上空格
    if left :
        if left.strip(digits) == left and center.lstrip(digits) == center :  # 左侧结尾不是数字，中间开头不是数字
            final = ' ' + final
        final = left.rstrip() + final
    
    # 如果英文左边的汉字被前一个组消费了，就要手动去看一下前一个字是不是中文
    elif re.match(r'[\u4e00-\u9fa5]', original.string[original.start(2) - 1]): 
        if center.lstrip(digits) == center:     # 确保中间开头不是数字
            final = ' ' + final
        
    # 如果英文的右边有汉字，给中英之间加上空格
    if right:
        if center.rstrip(digits) == center:     # 确保中间结尾不是数字
            final += ' '
        final += right.lstrip()

    return final

async def ws_serve(websocket, path):
    global loop
    global format_num, format_punc, format_spell

    console.print(f'接客了：{websocket}', style='yellow')
    try:
        async for data in websocket:
            samples = np.frombuffer(data, dtype=np.float32)

            # 投喂音频
            s = recognizer.create_stream()
            s.accept_waveform(16000, samples)

            # 识别结果
            await loop.run_in_executor(None, recognizer.decode_streams, [s])
            result_final = result_0 = s.result.text
            result_1 = result_2 = result_3 = result_4 = '未实施'

            # 转数字
            if format_num:
                result_final = result_1 = chinese_to_num(result_final)

            # 去掉拼写空格
            if format_spell:
                result_final = result_2 = en_in_zh.sub(adjust_space, result_final)

            # 添加标点
            if format_punc:
                try:
                    result_final = result_3 = await loop.run_in_executor(None, punc_model, result_final)
                    result_final = result_3 = result_3[0]
                except Exception as e:
                    console.print(f'标点引擎出错：{e}', style='bright_red')

            # 调整中英空格排版
            if format_spell:
                result_final = result_4 = en_in_zh.sub(adjust_space, result_final)

            await websocket.send(result_final)
            console.print(f'''
    识别粗结果：{result_0}
    转数字后后：{result_1}
    去拼写空格：{result_2}
    加标点结果：{result_3}
    调中英空格：[green4]{result_4}[/]
            ''')
     
    except websockets.ConnectionClosed:
        console.print("ConnectionClosed...", )
    except websockets.InvalidState:
        console.print("InvalidState...")
    except Exception as e:
        console.print("Exception:", e)


async def main():
    global addr, port
    global args, punc_model_dir
    global recognizer, punc_model
    global loop; loop = asyncio.get_event_loop()

    console.print(f'绑定的服务地址：[cyan underline]{addr}:{port}', end='\n\n')

    console.print(f'项目地址：[cyan underline]https://github.com/HaujetZhao/CapsWriter-Offline', end='\n\n')

    t1 = time.time()
    rich.print('[yellow]语音模型载入中', end='\r')
    recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
        paraformer=args.paraformer,
        tokens=args.tokens,
        num_threads=args.num_threads,
        sample_rate=args.sample_rate,
        feature_dim=args.feature_dim,
        decoding_method=args.decoding_method,
        debug=args.debug,)
    rich.print(f'[green4]语音模型载入完成', end='\n');print('')

    if format_punc:
        rich.print('[yellow]标点模型载入中', end='\r')
        punc_model = CT_Transformer(punc_model_dir)
        console.print(f'[green4]标点模型载入完成', end='\n\n')
    else:
        punc_model = None

    console.print(f'加载耗时 {time.time() - t1 :.2f}s', end='\n\n')


    console.rule('[green3]开始服务'); console.line()
    start_server = websockets.serve(ws_serve, 
                                addr, 
                                port, 
                                subprotocols=["binary"], 
                                max_size=None)
    try:
        await start_server
    except OSError as e:            # 有时候可能会因为端口占用而报错，捕获一下
        console.print(f'出错了：{e}', style='bright_red'); console.input('...')
        sys.exit()
    await asyncio.Event().wait()    # 持续运行



def init():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print('再见！')
        sys.exit()
        
if __name__ == "__main__":
    init()
