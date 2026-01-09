"""
LLM Toast 输出模式

流式显示在浮动窗口中，完成后停留 3 秒
"""
import asyncio

from util.client_strip_punc import strip_punc
from util.llm_stop_monitor import reset, should_stop


async def handle_toast_mode(text: str, role_config = None) -> tuple:
    """
    Toast 浮动窗口模式

    Args:
        text: 待润色的文本
        role_config: 角色配置

    Returns:
        (润色后的文本, 输出token数)
    """
    from util.llm_handler import polish_text
    from util.toast import ToastMessageManager, ToastMessage

    reset()  # 重置停止标志

    toast_manager = ToastMessageManager()

    # 从角色配置获取 toast 参数
    if role_config:
        font_size = role_config.toast_font_size
        bg = role_config.toast_bg_color
        fg = role_config.toast_font_color
        duration = role_config.toast_duration
        initial_width = role_config.toast_initial_width
        initial_height = role_config.toast_initial_height
    else:
        font_size = 14
        bg = '#075077'
        fg = 'white'
        duration = 3000
        initial_width = 400
        initial_height = 0

    # 创建初始 toast（流式模式）
    msg = ToastMessage(
        text="",
        font_size=font_size,
        bg=bg,
        fg=fg,
        duration=duration,
        initial_width=initial_width,
        initial_height=initial_height,
        streaming=True,
        window_type='label'  # 使用 label 版本
    )
    toast_manager.add_message(msg)

    chunks = []
    full_text = ""

    def stream_toast_chunk(chunk: str):
        """流式更新 toast"""
        nonlocal full_text
        chunks.append(chunk)
        full_text = ''.join(chunks)
        toast_manager.update_last_toast(full_text)

    # 流式调用 LLM
    polished_text, token_count = await asyncio.to_thread(
        polish_text, text, stream_toast_chunk, should_stop
    )

    if should_stop():
        # 被中断，关闭 toast
        toast_manager.close_last_toast()
        return ("", 0)
    else:
        # 完成，启动销毁计时器（3秒）
        toast_manager.finish_last_toast()

        if not polished_text:
            polished_text = text

        return (strip_punc(polished_text), token_count)