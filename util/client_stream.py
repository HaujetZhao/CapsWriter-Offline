
from util.client_cosmic import console, Cosmic
import numpy as np 
import sounddevice as sd
import asyncio
import sys
import time
from rich import inspect
import threading


def record_callback(indata: np.ndarray, 
                    frames: int,
                    time_info,
                    status: sd.CallbackFlags) -> None:
    if not Cosmic.on:
        return
    asyncio.run_coroutine_threadsafe(
        Cosmic.queue_in.put(
            {'type': 'data',
             'time': time.time(),
             'data': indata.copy(),
             },
        ),
        Cosmic.loop
    )


def stream_close(signum, frame):
    Cosmic.stream.close()

def stream_reopen():
    if not threading.main_thread().is_alive():
        return
    print('重启音频流')

    # 关闭旧流
    Cosmic.stream.close()

    # 重载 PortAudio，更新设备列表
    sd._terminate()
    sd._ffi.dlclose(sd._lib)
    sd._lib = sd._ffi.dlopen(sd._libname)
    sd._initialize()

    # 打开新流
    time.sleep(0.1)
    Cosmic.stream = stream_open()


def stream_open():
    # 显示录音所用的音频设备
    channels = 1
    try:
        device = sd.query_devices(kind='input')
        channels = min(2, device['max_input_channels'])
        console.print(f'使用默认音频设备：[italic]{device["name"]}，声道数：{channels}', end='\n\n')
    except UnicodeDecodeError:
        console.print("由于编码问题，暂时无法获得麦克风设备名字", end='\n\n', style='bright_red')
    except sd.PortAudioError:
        console.print("没有找到麦克风设备", end='\n\n', style='bright_red')
        input('按回车键退出'); sys.exit()

    stream = sd.InputStream(
        samplerate=48000,
        blocksize=int(0.05 * 48000),  # 0.05 seconds
        device=None,
        dtype="float32",
        channels=channels,
        callback=record_callback,
        finished_callback=stream_reopen,
    ); stream.start()

    return stream

