from config import ClientConfig as Config
import keyboard
import pyclip
import platform
import asyncio
from util.client.client_strip_punc import strip_punc


async def typing_result(text: str, paste: bool = None):
    """
    输出结果（带标点消除）

    Args:
        text: 要输出的文本
        paste: 是否使用 paste 方式（None 表示使用 Config.paste）
    """
    # 消除末尾标点
    text = strip_punc(text)


    # 模拟粘贴
    if paste:

        # 保存剪切板
        try:
            temp = pyclip.paste().decode('utf-8')
        except:
            temp = ''

        # 复制结果
        pyclip.copy(text)

        # 粘贴结果
        if platform.system() == 'Darwin':
            keyboard.press(55)
            keyboard.press(9)
            keyboard.release(55)
            keyboard.release(9)
        else:
            keyboard.send('ctrl + v')

        # 还原剪贴板
        if Config.restore_clip:
            await asyncio.sleep(0.1)
            pyclip.copy(temp)

    # 模拟打印
    else:
        keyboard.write(text)
