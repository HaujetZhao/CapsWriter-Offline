import os
import asyncio
from multiprocessing import Process, Manager
from platform import system

import websockets
from config import ServerConfig as Config, __version__
from util.server.server_cosmic import Cosmic, console
from util.server.server_ws_recv import ws_recv
from util.server.server_ws_send import ws_send
from util.server.server_init_recognizer import init_recognizer
from util.tools.empty_working_set import empty_current_working_set

BASE_DIR = os.path.dirname(__file__); os.chdir(BASE_DIR)    # 确保 os.getcwd() 位置正确，用相对路径加载模型


def setup_tray():
    """启用托盘图标"""
    if Config.enable_tray:
        from util.ui.tray import enable_min_to_tray
        icon_path = BASE_DIR + '/assets/icon.ico'
        enable_min_to_tray('CapsWriter Server', icon_path)


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
    # 跨进程列表，用于保存 socket 的 id，用于让识别进程查看连接是否中断
    Cosmic.sockets_id = Manager().list()

    # 负责识别的子进程
    recognize_process = Process(target=init_recognizer,
                                args=(Cosmic.queue_in,
                                      Cosmic.queue_out,
                                      Cosmic.sockets_id),
                                daemon=False)  # 改为非守护进程，可以优雅退出
    recognize_process.start()
    Cosmic.queue_out.get()  # 等待模型加载完成
    console.rule('[green3]开始服务')
    console.line()

    return recognize_process


async def run_websocket_server():
    """运行 WebSocket 服务器"""
    # 清空物理内存工作集
    if system() == 'Windows':
        empty_current_working_set()

    # 负责接收客户端数据的 coroutine
    recv = websockets.serve(ws_recv,
                            Config.addr,
                            Config.port,
                            subprotocols=["binary"],
                            max_size=None)

    # 负责发送结果的 coroutine
    send = ws_send()
    await asyncio.gather(recv, send)


def init():
    """初始化并启动服务"""
    # 1. 启用托盘图标
    setup_tray()

    # 2. 打印启动信息
    print_banner()

    # 3. 启动识别子进程
    recognize_process = start_recognizer_process()

    try:
        # 4. 运行 WebSocket 服务器
        asyncio.run(run_websocket_server())

    except KeyboardInterrupt:           # Ctrl-C 停止
        console.print('\n[yellow]正在停止服务...')
    except OSError as e:                # 端口占用
        console.print(f'出错了：{e}', style='bright_red'); console.input('...')
    except Exception as e:
        print(e)
    finally:
        # 通知识别进程退出
        Cosmic.queue_in.put(None)

        # 等待识别进程结束（最多等待5秒）
        if recognize_process.is_alive():
            recognize_process.join(timeout=5)
            if recognize_process.is_alive():
                console.print('[red]识别进程未能在5秒内退出，强制终止')
                recognize_process.terminate()
            else:
                # console.print('[green4]识别进程已正常退出')
                ...

        console.print('[green4]再见！')
        # 使用 os._exit 确保立即退出，不会被 asyncio 或托盘线程阻塞
        os._exit(0)
     
        
if __name__ == "__main__":
    init()
