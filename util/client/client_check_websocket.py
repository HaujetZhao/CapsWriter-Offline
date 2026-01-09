
import websockets 
from util.client.client_cosmic import Cosmic, console
from config import ClientConfig as Config


class Handler:
    def __enter__(self):...

    def __exit__(self, exc_type, e, exc_tb):
        if e == None:
            return True
        if isinstance(e, ConnectionRefusedError):
            return True
        elif isinstance(e, TimeoutError):
            return True
        elif isinstance(e, Exception):
            return True
        else:
            print(e)


async def check_websocket() -> bool:
    # 检查 websocket 是否存在且处于打开状态
    if Cosmic.websocket is not None:
        try:
            # 在新版本 websockets 中，使用 closed 属性检查状态
            if not Cosmic.websocket.closed:
                return True
            # 如果已关闭，清理连接对象
            else:
                Cosmic.websocket = None
        except AttributeError:
            # 兼容旧版本，如果 websocket 对象存在就尝试使用
            pass

    # 尝试建立新连接
    for _ in range(3):
        with Handler():
            Cosmic.websocket = await websockets.connect(f"ws://{Config.addr}:{Config.port}", subprotocols=["binary"], max_size=None)
            return True
    else:
        return False

    # for _ in range(3):
    #     try:
    #         Cosmic.websocket = await websockets.connect(f"ws://{Config.addr}:{Config.port}", subprotocols=["binary"], max_size=None)
    #         return True
    #     except ConnectionRefusedError as e:
    #         continue
    #     except TimeoutError:
    #         continue
    #     except Exception as e:
    #         print(e)
    #
    # else:
    #     return False
