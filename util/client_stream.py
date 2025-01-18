import asyncio
import sys
import threading
import time
from types import FrameType
from typing import Any, TypedDict, no_type_check

import sounddevice as sd  # pyright: ignore[reportMissingTypeStubs]

from util.client_cosmic import ClientAppState, DataClientTask, console
from util.types import RecordingData


@no_type_check
def restart_port_audio() -> None:
    sd._terminate()
    sd._ffi.dlclose(sd._lib)
    sd._lib = sd._ffi.dlopen(sd._libname)
    sd._initialize()


def record_callback(
    indata: RecordingData,
    _frames: int,
    _time_info: Any,
    _status: sd.CallbackFlags,
) -> None:
    if not ClientAppState.on:
        return
    asyncio.run_coroutine_threadsafe(
        ClientAppState.queue_in.put(
            DataClientTask(
                {
                    "type": "data",
                    "time": time.time(),
                    "data": indata.copy(),
                }
            ),
        ),
        ClientAppState.loop,
    )


def stream_close(_signum: int, _frame: FrameType | None) -> None:
    assert ClientAppState.stream is not None  # #TODO-REF-APP_CLASS: remove
    ClientAppState.stream.close()


def stream_reopen() -> None:
    if not threading.main_thread().is_alive():
        return
    print("重启音频流")

    # 关闭旧流
    assert ClientAppState.stream is not None  # #TODO-REF-APP_CLASS: remove
    ClientAppState.stream.close()

    # 重载 PortAudio，更新设备列表
    restart_port_audio()

    # 打开新流
    time.sleep(0.1)
    ClientAppState.stream = stream_open()


class DeviceDict(TypedDict):
    """
    # #TODO: Find stubfile for sounddevice
    'name': name,
    'index': device,
    'hostapi': info.hostApi,
    'max_input_channels': info.maxInputChannels,
    'max_output_channels': info.maxOutputChannels,
    'default_low_input_latency': info.defaultLowInputLatency,
    'default_low_output_latency': info.defaultLowOutputLatency,
    'default_high_input_latency': info.defaultHighInputLatency,
    'default_high_output_latency': info.defaultHighOutputLatency,
    'default_samplerate': info.defaultSampleRate,
    """

    name: str
    index: int
    hostapi: int
    max_input_channels: int
    max_output_channels: int
    default_low_input_latency: float
    default_low_output_latency: float
    default_high_input_latency: float
    default_high_output_latency: float
    default_samplerate: float


def stream_open() -> sd.InputStream:
    # 显示录音所用的音频设备
    channels = 1
    try:
        device = DeviceDict(
            sd.query_devices(  # pyright: ignore[reportArgumentType,reportUnknownMemberType]
                kind="input"
            )
        )
        channels = int(device["max_input_channels"])
        console.print(
            f'使用默认音频设备：[italic]{device["name"]}，声道数：{channels}',
            end="\n\n",
        )
    except UnicodeDecodeError:
        console.print(
            "由于编码问题，暂时无法获得麦克风设备名字",
            end="\n\n",
            style="bright_red",
        )
    except sd.PortAudioError:
        console.print("没有找到麦克风设备", end="\n\n", style="bright_red")
        input("按回车键退出")
        sys.exit()

    stream = sd.InputStream(
        samplerate=48000,
        blocksize=int(0.05 * 48000),  # 0.05 seconds
        device=None,
        dtype="float32",
        channels=channels,
        callback=record_callback,
        finished_callback=stream_reopen,
    )
    stream.start()

    return stream
