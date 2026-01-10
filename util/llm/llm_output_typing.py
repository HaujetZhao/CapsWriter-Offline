"""
LLM Typing 输出模式

直接打字输出，根据 paste 参数或 Config.paste 选择：
- paste=True: 等流式输出完成后一次性粘贴
- paste=False: 实时流式 write，每个字都打出来
"""
import asyncio
import keyboard

from config import ClientConfig as Config
from util.client.processing.output import TextOutput
from util.llm.llm_clipboard import paste_text
from util.llm.llm_stop_monitor import reset, should_stop


async def handle_typing_mode(text: str, paste: bool = None) -> tuple:
    """
    打字输出模式

    Args:
        text: 待润色的文本
        paste: 是否使用 paste 方式（None 表示使用 Config.paste）

    Returns:
        (润色后的文本, 输出token数, 生成时间秒)
    """
    from util.llm.llm_handler import polish_text
    from util.llm.llm_error_handler import handle_llm_error

    reset()  # 重置停止标志

    try:
        if paste:
            # paste 方式：等完成后再处理
            polished_text, token_count, generation_time = await asyncio.to_thread(
                polish_text, text, None, should_stop
            )
            if should_stop():
                return ("", 0, 0.0)  # 被中断

            if not polished_text:
                polished_text = text
            polished_text = TextOutput.strip_punc(polished_text)
            await paste_text(polished_text, restore_clipboard=Config.restore_clip)
            return (polished_text, token_count, generation_time)
        else:
            # 非 paste 方式：实时流式 write
            chunks = []

            def stream_write_chunk(chunk: str):
                """实时写入每个 chunk"""
                chunks.append(chunk)
                keyboard.write(chunk)

            # 流式调用 LLM，实时输出
            polished_text, token_count, generation_time = await asyncio.to_thread(
                polish_text, text, stream_write_chunk, should_stop
            )

            if should_stop():
                return ("", 0, 0.0)  # 被中断

            if not chunks:
                # 如果没有输出，使用原文本
                original_text = TextOutput.strip_punc(text)
                keyboard.write(original_text)
                return (original_text, 0, 0.0)
            else:
                # 合并所有 chunks
                full_text = ''.join(chunks)

                # 处理最后一段的标点
                trash_count = 0
                last_chunk = chunks[-1] if chunks else ''

                # 计算末尾有多少个需要删除的标点
                for char in reversed(last_chunk):
                    if char in Config.trash_punc:
                        trash_count += 1
                    else:
                        break

                # 如果有标点需要删除，模拟退格键
                if trash_count > 0:
                    for _ in range(trash_count):
                        keyboard.press_and_release('backspace')

                # 返回去标点后的文本
                return (TextOutput.strip_punc(full_text), token_count, generation_time)

    except Exception as e:
        # 处理 LLM 异常
        result_text, success = handle_llm_error(e, text, "LLM")
        if success:
            # 降级策略：输出原文本
            result_text = TextOutput.strip_punc(result_text)
            await output_text(result_text, paste)
        return (result_text, 0, 0.0)


async def output_text(text: str, paste: bool = None):
    """输出文本（根据 paste 或 Config.paste 选择方式）"""
    if paste:
        await paste_text(text, restore_clipboard=Config.restore_clip)
    else:
        keyboard.write(text)
