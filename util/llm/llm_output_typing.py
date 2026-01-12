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


async def handle_typing_mode(text: str, paste: bool = None, matched_hotwords=None) -> tuple:
    """
    打字输出模式

    Args:
        text: 待润色的文本
        paste: 是否使用 paste 方式（None 表示使用 Config.paste）
        matched_hotwords: [(hotword, score), ...] 来自 hot_phoneme 的检索结果

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
                polish_text, text, matched_hotwords, None, should_stop
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
            pending_buffer = ""  # 用于缓存末尾的换行符和 trash 标点

            def stream_write_chunk(chunk: str):
                """实时写入每个 chunk，但保留末尾换行符和 trash 标点，直到下一个非空内容到达"""
                nonlocal pending_buffer
                if not chunk:
                    return
                chunks.append(chunk)

                # 1. 将 pending_buffer 与当前 chunk 结合处理
                full_current = pending_buffer + chunk
                
                # 2. 从结合后的内容末尾提取所有需要拦截的字符（换行符和 trash 标点）
                content = full_current
                trailing = ""
                
                # 从右向左找第一个“有效字符”
                for i in range(len(full_current) - 1, -1, -1):
                    char = full_current[i]
                    if char == '\n' or char in Config.trash_punc:
                        continue
                    else:
                        # 找到了有效字符，它及其左边的都是 content
                        content = full_current[:i+1]
                        trailing = full_current[i+1:]
                        break
                else:
                    # 全是拦截字符
                    content = ""
                    trailing = full_current

                # 3. 写入有效内容，更新缓冲区
                if content:
                    keyboard.write(content)
                    pending_buffer = trailing
                else:
                    # 如果全是拦截字符，则全部存入缓冲区，不执行写入
                    pending_buffer = trailing

            # 流式调用 LLM，实时输出
            polished_text, token_count, generation_time = await asyncio.to_thread(
                polish_text, text, matched_hotwords, stream_write_chunk, should_stop
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

                # 返回去标点后的文本（由于 pending_buffer 里的东西没打出来，所以不需要退格）
                return (TextOutput.strip_punc(full_text), token_count, generation_time)

    except Exception as e:
        # 处理 LLM 异常：降级到原文本
        result_text, _ = handle_llm_error(e, text, "LLM")
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
