import asyncio
import platform

import keyboard
import pyclip  # pyright: ignore[reportMissingTypeStubs]

from config import ClientConfig as Config


async def type_result(text: str) -> None:

    # 模拟粘贴
    if Config.paste:

        # 保存剪切板
        try:
            pb_content: str | bytes = (
                pyclip.paste()  # pyright: ignore[reportUnknownMemberType]
            )
            if isinstance(pb_content, bytes):
                temp: str = pb_content.decode("utf-8")
            # elif isinstance(pb_content, str):
            else:
                temp = pb_content
        except UnicodeDecodeError:
            temp = ""
            print(
                "Failed to parse clipboard Unicode content, "
                + "pasteboard content is lost"
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            temp = ""
            print("!!! UNEXPECTED ERROR !!! in client_type_result.py")
            print(e)

        # 复制结果
        pyclip.copy(text)  # pyright: ignore[reportUnknownMemberType]

        # 粘贴结果
        if platform.system() == "Darwin":
            # perform cmd + v
            keyboard.press(55)
            keyboard.press(9)
            keyboard.release(55)
            keyboard.release(9)
        else:
            keyboard.send("ctrl + v")

        # 还原剪贴板
        if Config.restore_clip:
            await asyncio.sleep(0.1)
            pyclip.copy(temp)  # pyright: ignore[reportUnknownMemberType]

    # 模拟打印
    else:
        keyboard.write(text)
