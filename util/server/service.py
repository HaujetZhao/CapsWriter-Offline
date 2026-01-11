
import asyncio
from multiprocessing import Process, Manager
import queue
from util.server.server_cosmic import Cosmic, console
from util.server.server_init_recognizer import init_recognizer
from util.server.state import get_state
from util.common.lifecycle import lifecycle
from util.logger import get_logger

logger = get_logger('server')

def start_recognizer_process():
    """启动识别子进程并等待模型加载完成"""
    state = get_state()
    Cosmic.sockets_id = Manager().list()
    recognize_process = Process(target=init_recognizer,
                                args=(Cosmic.queue_in,
                                      Cosmic.queue_out,
                                      Cosmic.sockets_id),
                                daemon=False)
    recognize_process.start()
    state.recognize_process = recognize_process
    logger.info("识别子进程已启动")

    # 轮询等待模型加载，同时响应退出请求
    import errno
    while not lifecycle.is_shutting_down:
        try:
            Cosmic.queue_out.get(timeout=0.1)
            break
        except queue.Empty:
            continue
        except (InterruptedError, OSError) as e:
            # 处理被信号中断的情况 (Errno 4 Interrupted function call)
            # 这通常发生在 Anti-Shake 触发时 (第一次 Ctrl+C)
            if isinstance(e, InterruptedError) or e.errno == errno.EINTR:
                continue
            raise

    if lifecycle.is_shutting_down:
        logger.warning("在加载模型时收到退出请求")
        recognize_process.terminate()
        # 不再抛出异常，而是优雅返回，由外层 lifecycle 状态决定流程
        return recognize_process

    logger.info("模型加载完成，开始服务")
    console.rule('[green3]开始服务')
    console.line()
    return recognize_process
