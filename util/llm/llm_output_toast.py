"""
LLM Toast 输出模式

流式显示在浮动窗口中，完成后停留 3 秒
"""
import asyncio
import logging

from util.client.processing.output import TextOutput
from util.llm.llm_stop_monitor import reset, should_stop, create_stop_callback

logger = logging.getLogger(__name__)


async def handle_toast_mode(text: str, role_config = None, matched_hotwords=None) -> tuple:
    """
    Toast 浮动窗口模式

    Args:
        text: 待润色的文本
        role_config: 角色配置
        matched_hotwords: [(hotword, score), ...] 来自 hot_phoneme 的检索结果

    Returns:
        (润色后的文本, 输出token数, 生成时间秒)
    """
    from util.llm.llm_handler import polish_text
    from util.ui.toast import ToastMessageManager, ToastMessage

    reset()  # 重置停止标志

    # 为这个任务创建独立的停止事件
    task_stop_event = create_stop_callback()

    toast_manager = ToastMessageManager()
    msg_id = None  # 初始化为 None，避免异常处理时未定义

    # 从角色配置获取 toast 参数
    if role_config:
        font_family = role_config.toast_font_family
        font_size = role_config.toast_font_size
        bg = role_config.toast_bg_color
        fg = role_config.toast_font_color
        duration = role_config.toast_duration
        initial_width = role_config.toast_initial_width
        initial_height = role_config.toast_initial_height
    else:
        font_family = ''
        font_size = 14
        bg = '#075077'
        fg = 'white'
        duration = 3000
        initial_width = 400
        initial_height = 0

    try:
        # 创建初始 toast（流式模式，启用 Markdown）
        msg = ToastMessage(
            text="",
            font_family=font_family,
            font_size=font_size,
            bg=bg,
            fg=fg,
            duration=duration,
            initial_width=initial_width,
            initial_height=initial_height,
            streaming=True,
            window_type='text',  # 使用 text 版本（支持流式输出）
            markdown=True,  # 启用 Markdown 渲染
            stop_callback=lambda: task_stop_event.set()  # 仅停止这个任务
        )

        # 添加消息并获取唯一标识符
        msg_id = toast_manager.add_message(msg)

        # 异步等待窗口创建完成
        toast_window = await toast_manager.wait_for_window(msg_id, timeout=1.0)

        if not toast_window:
            # 窗口创建失败，清理消息
            logger.error("Toast 窗口创建失败")
            if msg_id:
                toast_manager.close_toast(msg_id)
            return ("", 0, 0.0)

        chunks = []
        full_text = ""

        def stream_toast_chunk(chunk: str):
            """流式更新 toast"""
            nonlocal full_text
            chunks.append(chunk)
            full_text = ''.join(chunks)
            # 使用消息 ID 更新，精确匹配
            toast_manager.update_toast(msg_id, full_text)

        # 流式调用 LLM
        polished_text, token_count, generation_time = await asyncio.to_thread(
            polish_text, text, matched_hotwords, stream_toast_chunk, should_stop
        )

        if should_stop():
            # 被中断，关闭我们创建的 toast
            toast_manager.close_toast(msg_id)
            # 使用已生成的部分，处理方式与完成时相同
            if not full_text:
                full_text = text
            return (TextOutput.strip_punc(full_text), token_count, generation_time)
        else:
            # 完成，启动销毁计时器（3秒）
            toast_manager.finish_toast(msg_id)

            if not polished_text:
                polished_text = text

            return (TextOutput.strip_punc(polished_text), token_count, generation_time)

    except Exception as e:
        # 关闭我们创建的 toast（使用 msg_id）
        if msg_id:
            toast_manager.close_toast(msg_id)

        # 处理 LLM 异常（显示错误通知）
        from util.llm.llm_error_handler import show_error_notification
        show_error_notification(e, "LLM")

        # 返回空字符串表示失败
        return ("", 0, 0.0)