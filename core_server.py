import asyncio
import os
import sys
from multiprocessing import Manager, Process
from platform import system

from websockets.legacy.server import serve
from websockets.typing import Subprotocol

from config import ServerConfig as Config
from util.empty_working_set import empty_current_working_set
from util.server_check_model import check_model
from util.server_cosmic import ServerAppState, console
from util.server_init_recognizer import init_recognizer
from util.server_ws_recv import ws_recv
from util.server_ws_send import ws_send

BASE_DIR = os.path.dirname(__file__)
os.chdir(BASE_DIR)  # 确保 os.getcwd() 位置正确，用相对路径加载模型


async def main():

    # 检查模型文件
    check_model()

    console.line(2)
    console.rule("[bold #d55252]CapsWriter Offline Server")
    console.line()
    console.print(
        "项目地址：[cyan underline]"
        + "https://github.com/HaujetZhao/CapsWriter-Offline",
        end="\n\n",
    )
    console.print(f"当前基文件夹：[cyan underline]{BASE_DIR}", end="\n\n")
    console.print(
        f"绑定的服务地址：[cyan underline]{Config.addr}:{Config.port}",
        end="\n\n",
    )

    # 跨进程列表，用于保存 socket 的 id，用于让识别进程查看连接是否中断
    ServerAppState.sockets_id = Manager().list()

    # 负责识别的子进程
    recognize_process = Process(
        target=init_recognizer,
        args=(
            ServerAppState.queue_in,
            ServerAppState.queue_out,
            ServerAppState.sockets_id,
        ),
        daemon=True,
    )
    recognize_process.start()
    ServerAppState.queue_out.get()
    console.rule("[green3]开始服务")
    console.line()

    # 清空物理内存工作集
    if system() == "Windows":
        empty_current_working_set()

    # 负责接收客户端数据的 coroutine
    recv = serve(
        ws_recv,
        Config.addr,
        Config.port,
        subprotocols=[Subprotocol("binary")],
        max_size=None,
    )

    # 负责发送结果的 coroutine
    send = ws_send()
    await asyncio.gather(recv, send)


def init():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:  # Ctrl-C 停止
        console.print("\n再见！")
    except OSError as e:  # 端口占用
        console.print(f"出错了：{e}", style="bright_red")
        console.input("...")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print("!!! Unexpected Exception !!! in core_server.py")
        print(e)
    finally:
        ServerAppState.queue_out.put(None)
        sys.exit(0)
        # os._exit(0)


if __name__ == "__main__":
    init()
