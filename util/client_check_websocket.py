import websockets

from config import ClientConfig as Config
from util.client_cosmic import Cosmic


# #TODO: look deeper into this
class Handler:
    def __enter__(self): ...

    def __exit__(self, exc_type, e, exc_tb):
        if (
            e is None
            or isinstance(e, websockets.exceptions.ConnectionClosedError)
            or isinstance(e, ConnectionRefusedError)
            or isinstance(e, TimeoutError)
            or isinstance(e, Exception)
        ):
            return True
        print(e)


async def check_websocket() -> bool:
    if Cosmic.websocket and not Cosmic.websocket.closed:
        return True
    for _ in range(3):
        with Handler():
            Cosmic.websocket = await websockets.connect(
                f"ws://{Config.addr}:{Config.port}", max_size=None
            )
            return True
    return False
