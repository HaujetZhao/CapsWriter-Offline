
from os import path, mkdir; 
if 'BASE_DIR' not in globals():
    BASE_DIR = path.dirname(__file__); 
print(f'当前基文件夹：{BASE_DIR}')
from pathlib import Path
import time
import asyncio
import re

import numpy as np
import websockets
import sherpa_onnx
from funasr_onnx import CT_Transformer
import colorama; colorama.init()

from chinese_itn import chinese_to_num


# ============================全局变量和检查区====================================

addr = '0.0.0.0'
port = '6006'

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
    print(f'''\x9b31m
    未能找到模型文件  

    未找到：{path}

    本服务端需要 paraformer-offline-zh 模型和 punc_ct-transformer_zh-cn 模型，
    请下载模型并放置到： {model_dir} 

    \x9b0m'''); input('按回车退出'); exit()

# ========================================================================

en_in_zh = re.compile(r"""(?ix)    # i 表示忽略大小写，x 表示开启注释模式
    ([\u4e00-\u9fa5]|[a-z0-9]+\s)?      # 左侧是中文，或者英文加空格
    ([a-z0-9 ]+)                    # 中间是一个或多个「英文数字加空格」
    ([\u4e00-\u9fa5]|[a-z0-9]+)?       # 右是中文，或者英文加空格
""")

def adjust_space(original: re.Match):
    # 如果拼写字母中间有空格，就把空格都去掉
    if original.group(2):
        final = re.sub(r'((\d) )?(\b\w) ?(?!\w{2})', r'\2\3', original.group(2)).strip()
        # 测试地址 https://regex101.com/r/1Vtu7V/1
        # final = re.sub(r'(\b\w) (?!\w{2})', r'\1', original.group(2)).strip()
    
    # 如果英文的左边有汉字或英文（不是数字），给两组之间加上空格
    if original.group(1):
        if not re.match(r'.*\d', original.group(1)):
            final = original.group(1).rstrip() + ' ' + final
    # 如果英文左边的汉字被前一个组消费了，就要手动去看一下前一个字是不是中文
    elif re.match(r'[\u4e00-\u9fa5]', original.string[original.start(2) - 1]): 
        final = ' ' + final
        

    # 如果英文的右边有汉字，给中英之间加上空格
    if original.group(3):
        final += ' ' + original.group(3).lstrip()

    return final

async def ws_serve(websocket, path):
    global loop
    print(f'\n接客了：{websocket}')
    try:
        async for data in websocket:
            samples = np.frombuffer(data, dtype=np.float32)

            # 投喂音频
            s = recognizer.create_stream()
            s.accept_waveform(16000, samples)

            # 识别结果
            await loop.run_in_executor(None, recognizer.decode_streams, [s])
            result_0 = s.result.text

            # 转数字
            result_1 = chinese_to_num(result_0)

            # 去掉拼写空格
            result_2 = en_in_zh.sub(adjust_space, result_1)

            # 添加标点
            result_3 = await loop.run_in_executor(None, punc_model, result_2)
            result_3 = result_3[0]

            # 调整中英空格排版
            result_4 = en_in_zh.sub(adjust_space, result_3)

            await websocket.send(result_4)
            print(f'''
    识别粗结果：{result_0}
    转数字后后：{result_1}
    去拼写空格：{result_2}
    加标点结果：{result_3}
    调中英空格：\x9b32m{result_4}\x9b0m
            ''')
     
    except websockets.ConnectionClosed:
        print("ConnectionClosed...", )
    except websockets.InvalidState:
        print("InvalidState...")
    except Exception as e:
        print("Exception:", e)


async def main():
    global addr, port
    global args, punc_model_dir
    global recognizer, punc_model
    global loop; loop = asyncio.get_event_loop()

    print(f'\n绑定的服务地址：\x9b33m{addr}:{port}\x9b0m')

    print(f'\n项目地址：\x9b36mhttps://github.com/HaujetZhao/CapsWriter-Offline\x9b0m')

    t1 = time.time()
    print(f'\n正在载入语音模型', end='')
    recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
        paraformer=args.paraformer,
        tokens=args.tokens,
        num_threads=args.num_threads,
        sample_rate=args.sample_rate,
        feature_dim=args.feature_dim,
        decoding_method=args.decoding_method,
        debug=args.debug,
    )
    print(f'\r\x9b2K\x9b32m语音模型载入完成\x9b0m')

    print(f'\n正在载入标点模型', end='')
    punc_model = CT_Transformer(punc_model_dir)
    print(f'\r\x9b2K\x9b32m标点模型载入完成\x9b0m')

    print(f'\n加载耗时 {time.time() - t1 :.2f}s')


    print('\n开始服务...')
    start_server = websockets.serve(ws_serve, 
                                addr, 
                                port, 
                                subprotocols=["binary"], 
                                ping_interval=None)
    try:
        await start_server
    except OSError as e:
        input(f'\x9b31m 出错了：{e} \x9b0m')
        exit()
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('再见！')
