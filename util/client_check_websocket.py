import websockets

from config import ClientConfig as Config
from util.client_cosmic import Cosmic

# #TODO-REF: move to ClientSocket.


async def check_websocket() -> bool:
    if Cosmic.websocket and not Cosmic.websocket.closed:
        return True
    for _ in range(3):
        try:
            Cosmic.websocket = await websockets.connect(
                f"ws://{Config.addr}:{Config.port}", max_size=None
            )
            return True
        except (
            ConnectionRefusedError,
            TimeoutError,
            websockets.exceptions.ConnectionClosedError,
        ) as e:
            print("Can't connect to server")
            print(type(e))
            print(e)
            continue
        except Exception as e:
            print("!!!Unexpected error!!! in client_check_websocket.py")
            print(type(e))
            print(e)
            continue
    return False
