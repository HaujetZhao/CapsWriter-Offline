import os
import asyncio
import signal
import atexit
from multiprocessing import Process, Manager
from platform import system

import websockets
from config import ServerConfig as Config, __version__
from util.server.server_cosmic import Cosmic, console
from util.server.server_ws_recv import ws_recv
from util.server.server_ws_send import ws_send
from util.server.server_init_recognizer import init_recognizer
from util.tools.empty_working_set import empty_current_working_set
from util.logger import setup_logger
from util.common.lifecycle import lifecycle
from util.server.state import get_state
from util.server.cleanup import setup_tray, print_banner, cleanup_server_resources

BASE_DIR = os.path.dirname(__file__); os.chdir(BASE_DIR)    # 确保 os.getcwd() 位置正确，用相对路径加载模型

# 初始化日志系统 (配置 root logger，同时写入 server_xxx.log)
logger = setup_logger('', log_filename='server', level=Config.log_level)
# websockets 日志会自动传播到 root logger，这里只需设置级别
import logging
logging.getLogger('websockets.server').setLevel(logging.WARNING)




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
    import queue
    try:
        while not lifecycle.is_shutting_down:
            try:
                Cosmic.queue_out.get(timeout=0.1)
                break
            except queue.Empty:
                continue
    except KeyboardInterrupt:
        logger.warning("在加载模型时收到停止信号")
        recognize_process.terminate()
        raise

    if lifecycle.is_shutting_down:
        logger.warning("在加载模型时收到退出请求")
        recognize_process.terminate()
        # 这里需要引发一个异常或者直接退出，防止继续执行 run_websocket_server
        # 由于外层 init 捕获 KeyboardInterrupt 并清理，我们可以模拟一个
        raise KeyboardInterrupt

    logger.info("模型加载完成，开始服务")
    console.rule('[green3]开始服务')
    console.line()
    return recognize_process


async def run_websocket_server():
    """运行 WebSocket 服务器"""
    loop = asyncio.get_running_loop()
    
    # 1. 初始化生命周期管理器 & 设置 Daemon Executor
    lifecycle.initialize(loop, logger=logger, exit_on_signal=False)
    from util.concurrency.daemon_executor import SimpleDaemonExecutor
    loop.set_default_executor(SimpleDaemonExecutor())

    # 清空物理内存工作集
    if system() == 'Windows':
        empty_current_working_set()

    # 2. 启动服务器
    logger.info(f"WebSocket 服务器正在启动，监听地址: {Config.addr}:{Config.port}")
    async with websockets.serve(ws_recv,
                                Config.addr,
                                Config.port,
                                subprotocols=["binary"],
                                max_size=None):
        
        send_task = asyncio.create_task(ws_send())
        
        # 3. 等待退出信号
        wait_shutdown_task = asyncio.create_task(lifecycle.wait_for_shutdown())

        done, pending = await asyncio.wait(
            [send_task, wait_shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        if wait_shutdown_task in done:
            logger.info("收到退出信号，正在关闭服务...")
        
        # 4. 取消所有相关任务
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        if send_task in done and not send_task.cancelled():
            try:
                await send_task
            except Exception as e:
                logger.error(f"发送任务异常退出: {e}")


def init():
    """初始化并启动服务"""
    lifecycle.register_on_shutdown(cleanup_server_resources)

    logger.info("=" * 50)
    logger.info("CapsWriter Offline Server 正在启动")
    logger.info(f"版本: {__version__}")
    logger.info(f"日志级别: {Config.log_level}")

    setup_tray()
    print_banner()

    try:
        start_recognizer_process()
        asyncio.run(run_websocket_server())
        # 正常退出后的显式清理
        lifecycle.cleanup()

    except KeyboardInterrupt:
        logger.warning("收到停止信号，正在停止服务...")
        console.print('\n[yellow]正在停止服务...')
        lifecycle.cleanup()
    except OSError as e:
        logger.error(f"OSError 错误: {e}")
        console.print(f'出错了：{e}', style='bright_red'); console.input('...')
        lifecycle.cleanup()
    except Exception as e:
        logger.error(f"未处理的异常: {e}", exc_info=True)
        print(e)
        lifecycle.cleanup()
        raise
     
        
if __name__ == "__main__":
    init()
