import json 
import base64 
import asyncio
import websockets
from base64 import b64decode

from util.server_cosmic import console, connections, queue_in
from util.server_classes import Task


async def ws_recv(websocket):
    status = console.status('正在接收音频', spinner='point')

    # 登记 socket 到字典，以 socket id 字符串为索引
    connections[str(websocket.id)] = websocket
    console.print(f'接客了：{websocket}\n', style='yellow')

    # 设定分段长度
    seg_duration = 15
    seg_overlap = 2
    seg_threshold = seg_duration + seg_overlap + 3

    # 片段缓冲区、偏移时长
    chunks = b''
    offset = 0

    try:
        # 接收数据
        async for message in websocket:
            # json 解码字符串
            # base64 解码音频数据
            # 音频数据是 float32、单声道、16000采样率
            message = json.loads(message)
            data = b64decode(message['data'])
            task_id = message['task_id']
            socket_id = str(websocket.id)

            match message['is_final']:
                case False:
                    status.start()
                    # 将音频片段加入缓冲区
                    chunks += data

                    # 若未达分段长度，则继续接收
                    if len(chunks) / 4 / 16000 < seg_threshold:
                        continue

                    # 若达到分段长度，将片段作为任务提交
                    data = chunks[:4*16000*(seg_duration+seg_overlap)]
                    chunks = chunks[4*16000*seg_duration:]
                    task = Task(data=data, offset=offset,
                                task_id=task_id, socket_id=socket_id,
                                overlap=seg_overlap, is_final=False,
                                time_start=message['time_start'],
                                time_submit=message['time_frame'])
                    offset += seg_duration
                    queue_in.put(task)

                case True:
                    status.stop()
                    # 客户端说片段结束，将缓冲区音频识别
                    task = Task(data=chunks[0:], offset=offset,
                                task_id=task_id, socket_id=socket_id,
                                overlap=seg_overlap, is_final=True,
                                time_start=message['time_start'],
                                time_submit=message['time_frame'])
                    queue_in.put(task)

                    # 还原缓冲区、偏移时长
                    chunks = b''
                    offset = 0

    except websockets.ConnectionClosed:
        console.print("ConnectionClosed...", )
    except websockets.InvalidState:
        console.print("InvalidState...")
    except Exception as e:
        console.print("Exception:", e)
    finally:
        status.stop()
        connections.pop(str(websocket.id))










    # global format_num, format_punc, format_spell
    # loop = asyncio.get_event_loop()


    # sample_rate = args.sample_rate
    # chunk_seconds = 15      # 以多少秒为一段
    # overlap_seconds = 2     # 两段之间重叠多少秒
    # frames_per_chunk = int(sample_rate * chunk_seconds) 
    # index = 0
    # timestamps = []
    # tokens = []
    # progress = 0  # 记录已经识别了多少秒 
    # data = b''
    # # try:
    # async for message in websocket:
    #     message = json.loads(message)
    #     match message['is_final']:
    #         case False: 
    #             # 接收数据，若数据不够长，则继续等数据
    #             data += base64.b64decode(message['data'])
    #             if len(data) - index < frames_per_chunk * 4: continue
    #         case True:
    #             # 发送数据，并清空缓存

    #             # token 合并为文本
    #             text = text_0 = ' '.join(tokens).replace('@@ ', '')
    #             text_1 = text_2 = text_3 = text_4 = '未实施'

    #             # 转数字
    #             if format_num: text = text_1 = chinese_to_num(text)
    #             # 去掉拼写空格
    #             if format_spell: text = text_2 = adjust_space(text)
    #             # 添加标点
    #             if format_punc: text = text_3 = await loop.run_in_executor(None, punc_model, text)[0]
    #             # 调整中英空格排版
    #             if format_spell: text = text_4 = adjust_space(text)

    #             # 发送结果
    #             message_out = {'text': text}
    #             await websocket.send(json.dumps(message_out))

    #             # 打印结果
    #             console.print(f'''
    #     识别粗结果：{text_0}
    #     转数字后后：{text_1}
    #     去拼写空格：{text_2}
    #     加标点结果：{text_3}
    #     调中英空格：[green4]{text_4}[/]
    #             ''')

    #             # 清空缓存
    #             data = b''
    #             index = 0
    #             timestamps = []
    #             tokens = []
    #             progress = 0  # 记录已经识别了多少秒 

    #             ...

    #     # Float32 格式，每一采样 4 Byte
    #     start = index
    #     end = index + (frames_per_chunk * 4) + (overlap_seconds * sample_rate * 4)
    #     chunk = data[start : end]
    #     index += frames_per_chunk * 4

    #     # 转换音频片段
    #     samples = np.frombuffer(chunk, dtype=np.float32)
        
    #     # 识别
    #     stream = recognizer.create_stream()
    #     stream.accept_waveform(args.sample_rate, samples)
    #     recognizer.decode_stream(stream); 

    #     # 粗去重
    #     for i, timestamp in enumerate(stream.result.timestamps):
    #         if timestamp > overlap_seconds / 2: 
    #             m = i; break 
    #     for i, timestamp in enumerate(stream.result.timestamps):
    #         n = i
    #         if timestamp > chunk_seconds + overlap_seconds / 2: break 
    #     if start == 0: m = 0
    #     if index >= len(data): n = len(stream.result.timestamps)

    #     # 细去重
    #     if tokens and tokens[-2:] == stream.result.tokens[m:n][:2]: m += 2
    #     elif tokens and tokens[-1:] == stream.result.tokens[m:n][:1]: m += 1

    #     # 收集结果
    #     timestamps += [t + progress for t in stream.result.timestamps[m:n]]
    #     tokens += [token for token in stream.result.tokens[m:n]]

    #     # 更新进度
    #     progress += chunk_seconds
    #     print(f'\r识别进度：{progress}s', end='', flush=True)
            


    #         samples = np.frombuffer(message_in, dtype=np.float32)

    #         # 投喂音频
    #         s = recognizer.create_stream()
    #         s.accept_waveform(16000, samples)

    #         # 识别结果
    #         await loop.run_in_executor(None, recognizer.decode_streams, [s])
    #         text = text_0 = s.result.text
    #         text_1 = text_2 = text_3 = text_4 = '未实施'

    #         # 转数字
    #         if format_num:
    #             text = text_1 = chinese_to_num(text)

    #         # 去掉拼写空格
    #         if format_spell:
    #             text = text_2 = adjust_space(text)

    #         # 添加标点
    #         if format_punc:
    #             try:
    #                 text = text_3 = await loop.run_in_executor(None, punc_model, text)
    #                 text = text_3 = text_3[0]
    #             except Exception as e:
    #                 console.print(f'标点引擎出错：{e}', style='bright_red')

    #         # 调整中英空格排版
    #         if format_spell:
    #             text = text_4 = adjust_space(text)

    #         await websocket.send(text)
    #         console.print(f'''
    # 识别粗结果：{text_0}
    # 转数字后后：{text_1}
    # 去拼写空格：{text_2}
    # 加标点结果：{text_3}
    # 调中英空格：[green4]{text_4}[/]
    #         ''')
    
