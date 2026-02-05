"""
LLM Typing 输出模式

直接打字输出，根据 paste 参数或 Config.paste 选择：
- paste=True: 等流式输出完成后一次性粘贴
- paste=False: 实时流式 write，每个字都打出来
"""
import asyncio
import keyboard

from config import ClientConfig as Config
from util.tools.asyncio_to_thread import to_thread
from util.client.output.text_output import TextOutput
from util.client.clipboard import paste_text
from util.llm.llm_stop_monitor import reset, should_stop
from . import logger


async def handle_typing_mode(text: str, paste: bool = None, matched_hotwords=None, role_config=None, content=None) -> tuple:
    """打字输出模式"""
    from util.llm.llm_handler import get_handler
    from util.llm.llm_error_handler import handle_llm_error

    handler = get_handler()
    # 如果没传，则现场检测一次（兼容性）
    if not role_config or content is None:
        role_config, content = handler.detect_role(text)
    
    if not role_config:
        # 不应发生，但作为防守
        result_text = TextOutput.strip_punc(text)
        await output_text(result_text, paste)
        return (result_text, 0, 0.0)

    reset()  # 重置停止标志

    try:
        if paste:
            # paste 方式：直接获取全文后一次性输出
            polished_text, token_count, gen_time = await to_thread(
                handler.process, role_config, content, matched_hotwords, None, should_stop
            )
            if should_stop():
                return ("", 0, 0.0)

            final_text = TextOutput.strip_punc(polished_text or content)
            await paste_text(final_text, restore_clipboard=Config.restore_clip)
            return (final_text, token_count, gen_time)
        else:
            # 流式打字方式
            chunks = []
            pending_buffer = ""

            def stream_write_chunk(chunk: str):
                nonlocal pending_buffer
                if not chunk: return
                chunks.append(chunk)

                full_current = pending_buffer + chunk
                content_to_write = full_current
                trailing = ""
                
                # 从右向左寻找第一个非 trash 字符
                for i in range(len(full_current) - 1, -1, -1):
                    char = full_current[i]
                    if char == '\n' or char in Config.trash_punc:
                        continue
                    else:
                        content_to_write = full_current[:i+1]
                        trailing = full_current[i+1:]
                        break
                else:
                    content_to_write = ""
                    trailing = full_current

                if content_to_write:
                    # 使用 customized write 处理软换行
                    # 避免与中文输入法冲突，同时防止回车直接发送
                    logger.debug(f"output_text: write '{content_to_write}'")
                    write_with_soft_newlines(content_to_write)
                    pending_buffer = trailing
                else:
                    pending_buffer = trailing

            # 执行流式处理
            polished_text, token_count, gen_time = await to_thread(
                handler.process, role_config, content, matched_hotwords, stream_write_chunk, should_stop
            )

            if should_stop():
                final_text = TextOutput.strip_punc(''.join(chunks) or content)
                return (final_text, 0, 0.0)

            if not chunks:
                # 降级
                final_text = TextOutput.strip_punc(content)
                logger.debug(f"output_text: write '{final_text}' (降级)")
                write_with_soft_newlines(final_text)
                return (final_text, 0, 0.0)
            
            # 注意：末尾的 pending_buffer 包含的是垃圾字符，按设计要求不输出
            return (TextOutput.strip_punc(polished_text), token_count, gen_time)

    except Exception as e:
        result_text, _ = handle_llm_error(e, content, role_config.name if role_config else "LLM")
        result_text = TextOutput.strip_punc(result_text)
        await output_text(result_text, paste)
        return (result_text, 0, 0.0)


async def output_text(text: str, paste: bool = None):
    """输出文本（根据 paste 或 Config.paste 选择方式）"""
    if paste:
        await paste_text(text, restore_clipboard=Config.restore_clip)
    else:
        # 使用 write_with_soft_newlines 替代 keyboard.write
        logger.debug(f"output_text: write '{text}'")
        write_with_soft_newlines(text)


def write_with_soft_newlines(text: str):
    """
    模拟打字输出，将换行符转换为 Shift+Enter (软换行)
    这样可以保留格式，同时避免在即时通讯软件中直接发送消息
    """
    if not text:
        return
        
    parts = text.split('\n')
    count = len(parts)
    
    for i, part in enumerate(parts):
        if part:
            keyboard.write(part)
        
        # 如果不是最后一部分，说明后面有一个 \n，输出软换行
        if i < count - 1:
            keyboard.send('shift+enter')
