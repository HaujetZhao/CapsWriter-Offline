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

BASE_DIR = os.path.dirname(__file__); os.chdir(BASE_DIR)    # 确保 os.getcwd() 位置正确，用相对路径加载模型

# 初始化日志系统
logger = setup_logger('server', level=Config.log_level)

# 全局变量，用于跟踪进程状态
_recognize_process = None
_is_shutting_down = False
_main_loop = None
_shutdown_event = None


def request_exit_from_tray():
    """从托盘请求退出"""
    global _main_loop, _shutdown_event
    logger.info("托盘请求退出...")
    if _main_loop and _shutdown_event:
        try:
            _main_loop.call_soon_threadsafe(_shutdown_event.set)
        except RuntimeError as e:
            logger.warning(f"无法设置退出事件: {e}")
    else:
        logger.warning("主循环或退出事件未初始化，尝试强制退出")
        cleanup_resources()
        os._exit(0)


def cleanup_resources():
    """
    清理服务端资源的函数

    这个函数会被 atexit.register 注册，在程序退出时自动调用。
    也可以手动调用来执行清理操作。
    """
    global _is_shutting_down

    # 防止重复清理
    if _is_shutting_down:
        logger.debug("清理已经在进行中，跳过重复清理")
        return

    _is_shutting_down = True
    logger.info("=" * 50)
    logger.info("开始清理服务端资源...")

    # 1. 关闭所有 WebSocket 连接
    try:
        sockets = Cosmic.sockets
        socket_count = len(sockets)
        if socket_count > 0:
            logger.info(f"正在关闭 {socket_count} 个活跃的 WebSocket 连接...")
            for ws_id, ws in list(sockets.items()):
                try:
                    if not ws.closed:
                        # 在新的事件循环中关闭连接
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(ws.close())
                        loop.close()
                        logger.debug(f"已关闭连接: {ws_id}")
                except Exception as e:
                    logger.warning(f"关闭连接 {ws_id} 时发生错误: {e}")
            logger.debug("所有 WebSocket 连接已关闭")
    except Exception as e:
        logger.warning(f"关闭 WebSocket 连接时发生错误: {e}")

    # 2. 通知识别进程退出
    logger.debug("正在通知识别子进程退出...")
    try:
        Cosmic.queue_in.put(None, timeout=2)
        logger.debug("已向识别子进程发送退出信号")
    except Exception as e:
        logger.warning(f"通知识别进程时发生错误: {e}")

    # 3. 等待识别进程结束（最多等待5秒）
    global _recognize_process
    if _recognize_process and _recognize_process.is_alive():
        logger.info("等待识别子进程退出...")
        _recognize_process.join(timeout=5)
        if _recognize_process.is_alive():
            logger.warning("识别进程未能在5秒内退出，强制终止")
            console.print('[red]识别进程未能在5秒内退出，强制终止')
            _recognize_process.terminate()
            # 再等待1秒确保进程终止
            _recognize_process.join(timeout=1)
        else:
            logger.info("识别进程已正常退出")
    elif _recognize_process:
        logger.info("识别进程已退出")

    logger.info("服务端资源清理完成")
    console.print('[green4]再见！')


def signal_handler(signum, frame):
    """
    信号处理器

    处理 SIGINT (Ctrl+C) 和 SIGTERM 信号，优雅地退出程序。
    """
    signal_name = signal.Signals(signum).name
    print(f"\n[DEBUG] 信号处理器被触发: {signal_name} ({signum})", flush=True)
    logger.info(f"收到信号 {signal_name} ({signum})，准备退出...")

    global _main_loop, _shutdown_event
    if _main_loop and _shutdown_event and _main_loop.is_running():
        logger.info("正在触发异步关闭事件...")
        _main_loop.call_soon_threadsafe(_shutdown_event.set)
    else:
        # 如果循环没运行，直接强制退出
        logger.info("主循环未运行，直接退出")
        cleanup_resources()
        os._exit(0)


def register_signal_handlers():
    """注册信号处理器"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    logger.debug("信号处理器已注册")


def setup_tray():
    """启用托盘图标"""
    if Config.enable_tray:
        from util.ui.tray import enable_min_to_tray
        icon_path = BASE_DIR + '/assets/icon.ico'
        enable_min_to_tray('CapsWriter Server', icon_path, logger=logger, exit_callback=request_exit_from_tray)
        logger.info("托盘图标已启用")


def print_banner():
    """打印启动信息"""
    console.line(2)
    console.rule('[bold #d55252]CapsWriter Offline Server'); console.line()
    console.print(f'版本：[bold green]{__version__}', end='\n\n')
    console.print(f'项目地址：[cyan underline]https://github.com/HaujetZhao/CapsWriter-Offline', end='\n\n')
    console.print(f'当前基文件夹：[cyan underline]{BASE_DIR}', end='\n\n')
    console.print(f'绑定的服务地址：[cyan underline]{Config.addr}:{Config.port}', end='\n\n')


def start_recognizer_process():
    """启动识别子进程并等待模型加载完成"""
    global _recognize_process

    # 跨进程列表，用于保存 socket 的 id，用于让识别进程查看连接是否中断
    Cosmic.sockets_id = Manager().list()

    # 负责识别的子进程
    _recognize_process = Process(target=init_recognizer,
                                args=(Cosmic.queue_in,
                                      Cosmic.queue_out,
                                      Cosmic.sockets_id),
                                daemon=False)  # 改为非守护进程，可以优雅退出
    _recognize_process.start()
    logger.info("识别子进程已启动")
    Cosmic.queue_out.get()  # 等待模型加载完成
    logger.info("模型加载完成，开始服务")
    console.rule('[green3]开始服务')
    console.line()

    return _recognize_process


async def run_websocket_server():
    """运行 WebSocket 服务器"""
    global _main_loop, _shutdown_event

    # 获取当前运行的循环和创建退出事件
    _main_loop = asyncio.get_running_loop()
    
    # 设置默认执行器为 Daemon 模式，解决 queue.get 阻塞无法退出的问题
    from util.tools.daemon_executor import SimpleDaemonExecutor
    _main_loop.set_default_executor(SimpleDaemonExecutor())
    
    _shutdown_event = asyncio.Event()

    # 清空物理内存工作集
    if system() == 'Windows':
        empty_current_working_set()

    # 启动 WebSocket 服务器
    # 使用 async with 管理服务器生命周期
    logger.info(f"WebSocket 服务器正在启动，监听地址: {Config.addr}:{Config.port}")
    async with websockets.serve(ws_recv,
                                Config.addr,
                                Config.port,
                                subprotocols=["binary"],
                                max_size=None):
        
        # 启动发送协程
        send_task = asyncio.create_task(ws_send())
        # 创建等待退出事件的任务
        wait_shutdown_task = asyncio.create_task(_shutdown_event.wait())

        # 等待发送任务结束（异常）或收到退出信号
        done, pending = await asyncio.wait(
            [send_task, wait_shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        if wait_shutdown_task in done:
            logger.info("收到退出信号，正在关闭服务...")
        
        # 取消所有待处理的任务
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # 确保发送任务如果出错也能被捕获
        if send_task in done and not send_task.cancelled():
            try:
                await send_task
            except Exception as e:
                logger.error(f"发送任务异常退出: {e}")


def init():
    """初始化并启动服务"""
    # 注册信号处理器
    register_signal_handlers()
    # 注册 atexit 处理器（作为后备，如果信号处理器没被调用）
    atexit.register(cleanup_resources)

    logger.info("=" * 50)
    logger.info("CapsWriter Offline Server 正在启动")
    logger.info(f"版本: {__version__}")
    logger.info(f"日志级别: {Config.log_level}")

    # 1. 启用托盘图标（传入退出函数）
    setup_tray()

    # 2. 打印启动信息
    print_banner()

    # 3. 启动识别子进程
    recognize_process = start_recognizer_process()

    try:
        # 4. 运行 WebSocket 服务器
        asyncio.run(run_websocket_server())
        # 正常退出后的清理
        cleanup_resources()

    except KeyboardInterrupt:           # Ctrl-C 停止或托盘退出
        logger.warning("收到停止信号，正在停止服务...")
        console.print('\n[yellow]正在停止服务...')
        cleanup_resources()
    except OSError as e:                # 端口占用
        logger.error(f"OSError 错误: {e}")
        console.print(f'出错了：{e}', style='bright_red'); console.input('...')
        cleanup_resources()
    except Exception as e:
        logger.error(f"未处理的异常: {e}", exc_info=True)
        print(e)
        cleanup_resources()
        raise
     
        
if __name__ == "__main__":
    init()
