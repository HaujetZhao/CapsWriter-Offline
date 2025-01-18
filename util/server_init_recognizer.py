from __future__ import annotations  # Queue[Task], ListProxy[str] needs this
import logging
from multiprocessing.managers import ListProxy
import queue
import signal
import sys
import time
from multiprocessing import Queue
from platform import system


import jieba  # pyright: ignore[reportMissingTypeStubs]
import sherpa_onnx  # pyright: ignore[reportMissingTypeStubs]
from funasr_onnx import (  # pyright: ignore[reportMissingTypeStubs]
    CT_Transformer,
)

from config import ModelPaths, ParaformerArgs
from config import ServerConfig as Config
from util.empty_working_set import empty_current_working_set
from util.server_classes import Result, Task
from util.server_cosmic import console
from util.server_recognize import recognize


def disable_jieba_debug():
    # 关闭 jieba 的 debug
    jieba.setLogLevel(logging.INFO)  # pyright: ignore[reportUnknownMemberType]


def init_recognizer(
    queue_in: Queue[Task],
    queue_out: Queue[bool | Result],
    sockets_id: ListProxy[str],
):

    # Ctrl-C 退出
    signal.signal(signal.SIGINT, lambda _signum, _frame: sys.exit())

    # 导入模块
    with console.status(
        "载入模块中…", spinner="bouncingBall", spinner_style="yellow"
    ):

        disable_jieba_debug()
    console.print("[green4]模块加载完成", end="\n\n")

    # 载入语音模型
    console.print("[yellow]语音模型载入中", end="\r")
    t1 = time.time()
    recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
        **{
            key: value
            for key, value in ParaformerArgs.__dict__.items()
            if not key.startswith("_")
        }
    )
    console.print("[green4]语音模型载入完成", end="\n\n")

    # 载入标点模型
    punc_model = None
    if Config.format_punc:
        console.print("[yellow]标点模型载入中", end="\r")
        punc_model = CT_Transformer(ModelPaths.punc_model_dir, quantize=True)
        console.print("[green4]标点模型载入完成", end="\n\n")

    console.print(f"模型加载耗时 {time.time() - t1 :.2f}s", end="\n\n")

    # 清空物理内存工作集
    if system() == "Windows":
        empty_current_working_set()

    queue_out.put(True)  # 通知主进程加载完了

    while True:
        # 从队列中获取任务消息
        # 阻塞最多1秒，便于中断退出
        try:
            task = queue_in.get(timeout=1)
        except queue.Empty:
            # Handle the case where the queue is empty after the timeout
            continue
        except Exception as e:  # pylint: disable=broad-exception-caught
            print("!!! Unexpected Exception !!! in server_init_recognizer.py")
            print(type(e))
            print(e)
            continue

        if task.socket_id not in sockets_id:  # 检查任务所属的连接是否存活
            continue

        result = recognize(recognizer, punc_model, task)  # 执行识别
        queue_out.put(result)  # 返回结果
