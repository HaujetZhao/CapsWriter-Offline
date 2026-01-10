import asyncio
import json

import keyboard
import websockets
from config import ClientConfig as Config
from util.client.client_cosmic import Cosmic, console
from util.client.client_check_websocket import check_websocket
from util.client.client_hot_sub import hot_sub
from util.client.client_rename_audio import rename_audio
from util.client.client_write_md import write_md
from util.llm.llm_write_md import write_llm_md
from util.client.client_type_result import typing_result
from util.llm.llm_process_text import llm_process_text, LLMResult
from util.client.client_strip_punc import strip_punc
from util.tools.window_detector import get_active_window_info
from util.logger import get_logger

# 获取日志记录器
logger = get_logger('client')


def estimate_tokens(text: str) -> int:
    """
    估算文本的 token 数

    Args:
        text: 待估算的文本

    Returns:
        估算的 token 数
    """
    if not text:
        return 0

    # 估算：中文约 1.5 字符/token，英文约 4 字符/token
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def format_llm_result(llm_result: LLMResult) -> str:
    """
    格式化 LLM 结果输出

    Args:
        llm_result: LLMResult 对象包含结果信息

    Returns:
        格式化后的字符串
    """
    polished_text = llm_result.result
    role_name = llm_result.role_name
    processed = llm_result.processed
    token_count = llm_result.token_count
    polish_time = llm_result.polish_time

    # 处理文本：换行符替换为空格，并截断
    polished_text = polished_text.replace('\n', ' ').replace('\r', ' ')
    max_display_length = 50  # 最大显示长度
    if len(polished_text) > max_display_length:
        polished_text = polished_text[:max_display_length] + '...'

    # 构建显示的标签
    role_label = f'[{role_name}]' if role_name else ''
    result_text = f'[green]{polished_text}[/green]' if processed else polished_text

    # 计算 token 数（如果 API 没有返回，则估算）
    if token_count == 0 and polished_text:
        token_count = estimate_tokens(polished_text)

    # 计算模型速度 (tokens/s)
    if processed and polish_time > 0:
        speed = token_count / polish_time if token_count > 0 else 0
        speed_label = f'    {speed:.1f} tokens/s' if speed > 0 else ''
    else:
        speed_label = ''

    return f'    模型结果{role_label}：{result_text}{speed_label}'

async def recv_result():
    if not await check_websocket():
        logger.warning("WebSocket 连接检查失败")
        return
    console.print('[green]连接成功\n')
    logger.info("WebSocket 连接成功")
    try:
        while True:
            # 接收消息
            message = await Cosmic.websocket.recv()
            message = json.loads(message)
            text = message['text']
            delay = message['time_complete'] - message['time_submit']

            logger.debug(f"接收到识别结果，文本: {text[:50]}{'...' if len(text) > 50 else ''}, 时延: {delay:.2f}s")

            # 如果非最终结果，继续等待
            if not message['is_final']:
                continue

            # 热词替换
            text = hot_sub(text)
            text = strip_punc(text)

            logger.debug(f"热词替换后: {text[:50]}{'...' if len(text) > 50 else ''}")

            # 控制台输出
            console.print(f'    转录时延：{delay:.2f}s')
            console.print(f'    识别结果：[green]{text}')

            # 窗口兼容性检测
            window_info = get_active_window_info()
            paste = Config.paste

            # 检查是否为兼容性应用（需要使用粘贴方式）
            if window_info:
                window_title = window_info.get('title', '')
                compatibility_apps = ['weixin', '微信', 'wechat', 'WeChat']
                if window_title in compatibility_apps:
                    paste = True
                    logger.debug(f"检测到兼容性应用: {window_title}，使用粘贴模式")

            # LLM 处理和输出
            if Config.llm_enabled:
                # 使用 LLM 润色后输出（LLM 会添加标点，所以内部会消除末尾标点）
                llm_result = await llm_process_text(text, return_result=True, window_info=window_info, paste=paste)
            else:
                await typing_result(text, paste=paste)
                llm_result = None

            # 保存录音与写入 md 文件
            if Config.save_audio:
                # 重命名录音文件
                file_audio = rename_audio(message['task_id'], text, message['time_start'])
                logger.debug(f"保存录音文件: {file_audio}")

                # 写入普通 md 文件（无论是否启用 LLM）
                write_md(text, message['time_start'], file_audio)
                logger.debug("写入 MD 文件")

            # LLM 结果显示和保存
            if Config.llm_enabled and llm_result and llm_result.processed:
                console.print(format_llm_result(llm_result))
                file_audio = file_audio if Config.save_audio else None
                write_llm_md(
                    llm_result.input_text,
                    llm_result.result,
                    llm_result.role_name,
                    message['time_start'],
                    file_audio
                )
                logger.debug("写入 LLM MD 文件")


            console.line()

    except websockets.ConnectionClosedError:
        console.print('[red]连接断开\n')
        logger.error("WebSocket 连接断开")
    except websockets.ConnectionClosedOK:
        console.print('[yellow]连接已正常关闭\n')
        logger.info("WebSocket 连接已正常关闭")
    except Exception as e:
        logger.error(f"接收结果时发生错误: {e}", exc_info=True)
        print(e)
    finally:
        # 清理已关闭的 websocket 连接
        if Cosmic.websocket is not None:
            try:
                if Cosmic.websocket.closed:
                    Cosmic.websocket = None
                    logger.debug("WebSocket 连接已清理")
            except Exception:
                Cosmic.websocket = None
        return
