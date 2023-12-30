
import websockets 
from util.client_cosmic import Cosmic, console
from config import ClientConfig as Config


async def check_websocket() -> bool:
    if Cosmic.websocket and not Cosmic.websocket.closed:
        return True
    for _ in range(3):
        try:
            Cosmic.websocket = await websockets.connect(f"ws://{Config.addr}:{Config.port}", max_size=None)
            return True
        except ConnectionRefusedError as e:
            continue
        except TimeoutError:
            continue
        except Exception as e:
            print(e)

    else:
        return False
