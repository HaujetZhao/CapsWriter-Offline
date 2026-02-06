"""
LLM Toast 输出模式

流式显示在浮动窗口中，完成后停留 3 秒
"""
import asyncio
import logging

from util.client.output.text_output import TextOutput
from util.tools.asyncio_to_thread import to_thread
from util.llm.llm_stop_monitor import reset, should_stop, create_stop_callback

logger = logging.getLogger(__name__)


async def handle_toast_mode(text: str, role_config=None, matched_hotwords=None, content=None) -> tuple:
    """Toast 浮动窗口模式"""
    from util.llm.llm_handler import get_handler
    from util.ui.toast import ToastMessageManager, ToastMessage

    handler = get_handler()
    # 兼容性检测
    if not role_config or content is None:
        role_config, content_detected = handler.detect_role(text)
        content = content_detected if content is None else content

    if not role_config:
        return ("", 0, 0.0)

    reset()  # 重置停止标志
    task_stop_event = create_stop_callback()
    toast_manager = ToastMessageManager()
    msg_id = None

    try:
        # 创建初始 toast
        msg = ToastMessage(
            text="",
            font_family=role_config.toast_font_family,
            font_size=role_config.toast_font_size,
            bg=role_config.toast_bg_color,
            fg=role_config.toast_font_color,
            duration=role_config.toast_duration,
            initial_width=role_config.toast_initial_width,
            initial_height=role_config.toast_initial_height,
            streaming=True,
            window_type='text',
            markdown=True,
            editable=role_config.toast_editable,
            stop_callback=lambda: task_stop_event.set()
        )

        msg_id = toast_manager.add_message(msg)
        toast_window = await toast_manager.wait_for_window(msg_id, timeout=1.0)

        if not toast_window:
            logger.error("Toast 窗口创建失败")
            if msg_id: toast_manager.close_toast(msg_id)
            return ("", 0, 0.0)

        chunks = []
        def stream_toast_chunk(chunk: str):
            chunks.append(chunk)
            toast_manager.update_toast(msg_id, ''.join(chunks))

        # 流式调用 LLM
        polished_text, token_count, gen_time = await to_thread(
            handler.process, role_config, content, matched_hotwords, stream_toast_chunk, should_stop
        )

        if should_stop():
            toast_manager.close_toast(msg_id)
            return (''.join(chunks) or content, token_count, gen_time)
        else:
            toast_manager.finish_toast(msg_id)
            return (polished_text or content, token_count, gen_time)

    except Exception as e:
        if msg_id: toast_manager.close_toast(msg_id)
        
        from util.llm.llm_error_handler import handle_llm_error, should_fallback_to_original
        role_name = role_config.name or RoleConfig.DEFAULT_ROLE_NAME

        if should_fallback_to_original(e):
            result_text, _ = handle_llm_error(e, content, role_name)
            result_text = TextOutput.strip_punc(result_text)
            
            from util.llm.llm_output_typing import output_text
            from config_client import ClientConfig as Config
            await output_text(result_text, Config.paste)
            return (result_text, 0, 0.0)
        else:
            from util.llm.llm_error_handler import show_error_notification
            show_error_notification(e, role_name)
            return ("", 0, 0.0)
