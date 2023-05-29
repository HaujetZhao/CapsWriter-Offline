
from os import path, mkdir; 
if 'BASE_DIR' not in globals():
    BASE_DIR = path.dirname(__file__); 
print(f'当前基文件夹：{BASE_DIR}')
from pathlib import Path
import time
import asyncio

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


async def ws_serve(websocket, path):
    global loop
    print(f'\n接客了：{websocket}')
    try:
        async for data in websocket:
            samples = np.frombuffer(data, dtype=np.float32)

            # 投喂音频
            s = recognizer.create_stream()
            s.accept_waveform(16000, samples)

            # 识别音频得到结果
            await loop.run_in_executor(None, recognizer.decode_streams, [s])
            result_raw = s.result.text

            # 添加标点
            result_punc = await loop.run_in_executor(None, punc_model, result_raw)
            result_punc = result_punc[0]

            # 中文数字转阿拉伯数字
            result_final = chinese_to_num(result_punc)

            await websocket.send(result_final)
            print(f'\n识别结果：{result_raw}\n加标点结果：{result_punc}\nITN结果：\x9b32m{result_final}\x9b0m')
     
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
    await start_server
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('再见！')
