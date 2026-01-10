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

BASE_DIR = os.path.dirname(__file__); os.chdir(BASE_DIR)    # 确保 os.getcwd() 位置正确，用相对路径加载模型

# 初始化日志系统
logger = setup_logger('server', level=Config.log_level)

# 全局变量，用于跟踪识别进程
_recognize_process = None


def request_exit_from_tray():
    """从托盘请求退出"""
    logger.info("托盘请求退出...")
    lifecycle.request_shutdown(reason="Tray Icon")


def cleanup_resources():
    """
    清理服务端资源的函数
    注册到 LifecycleManager 中
    """
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
                        # 在新的事件循环中关闭连接 (同步清理场景)
                        # 注意：如果是在 async loop 运行中调用的 cleanup，这里可能会有风险
                        # 但 LifecycleManager 的 cleanup 可能在 atexit 或 explicitly called
                        # 最好检查 loop 状态
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(ws.close())
                            loop.close()
                            logger.debug(f"已关闭连接: {ws_id}")
                        except Exception:
                            logger.debug(f"无法优雅关闭连接 {ws_id} (可能 Loop 已关闭)")
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

    # 4. 打印调试信息（如果有卡顿）
    # 可以在这里有条件地调用 shutdown_diagnostics.dump_active_stacks()
    
    # 5. 停止托盘图标 (防止主线程退出后托盘线程挂起)
    from util.ui.tray import stop_tray
    stop_tray()

    logger.info("服务端资源清理完成")
    console.print('[green4]再见！')


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
    Cosmic.sockets_id = Manager().list()
    _recognize_process = Process(target=init_recognizer,
                                args=(Cosmic.queue_in,
                                      Cosmic.queue_out,
                                      Cosmic.sockets_id),
                                daemon=False)
    _recognize_process.start()
    logger.info("识别子进程已启动")
    try:
        Cosmic.queue_out.get()
    except KeyboardInterrupt:
        logger.warning("在加载模型时收到停止信号")
        _recognize_process.terminate()
        raise
    logger.info("模型加载完成，开始服务")
    console.rule('[green3]开始服务')
    console.line()
    return _recognize_process


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
    lifecycle.register_on_shutdown(cleanup_resources)

    logger.info("=" * 50)
    logger.info("CapsWriter Offline Server 正在启动")
    logger.info(f"版本: {__version__}")
    logger.info(f"日志级别: {Config.log_level}")

    setup_tray()
    print_banner()

    try:
        recognize_process = start_recognizer_process()
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
