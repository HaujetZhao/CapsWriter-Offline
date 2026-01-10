# coding: utf-8
"""
识别结果处理模块

提供 ResultProcessor 类用于处理服务端返回的识别结果。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from config import ClientConfig as Config
from util.client.state import console
from util.client.websocket_manager import WebSocketManager
from util.client.processing.hotword import HotwordManager
from util.client.processing.output import TextOutput
from util.tools.window_detector import get_active_window_info
from util.logger import get_logger

if TYPE_CHECKING:
    from util.client.state import ClientState

# 日志记录器
logger = get_logger('client')


def _estimate_tokens(text: str) -> int:
    """估算文本的 token 数"""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


class ResultProcessor:
    """
    识别结果处理器
    
    负责处理服务端返回的识别结果：
    - 接收 WebSocket 消息
    - 执行热词替换
    - 可选地调用 LLM 进行润色
    - 输出最终文本
    - 保存录音和日记
    """
    
    def __init__(self, state: 'ClientState'):
        """
        初始化结果处理器
        
        Args:
            state: 客户端状态实例
        """
        self.state = state
        self._ws_manager = WebSocketManager(state)
        self._hotword_manager = HotwordManager()
        self._text_output = TextOutput()
    
    def _format_llm_result(self, llm_result) -> str:
        """格式化 LLM 结果输出"""
        polished_text = llm_result.result
        role_name = llm_result.role_name
        processed = llm_result.processed
        token_count = llm_result.token_count
        generation_time = llm_result.generation_time  # 使用生成时间（从第一个 token 开始）

        polished_text = polished_text.replace('\n', ' ').replace('\r', ' ')
        max_display_length = 50
        if len(polished_text) > max_display_length:
            polished_text = polished_text[:max_display_length] + '...'

        role_label = f'[{role_name}]' if role_name else ''
        result_text = f'[green]{polished_text}[/green]' if processed else polished_text

        if token_count == 0 and polished_text:
            token_count = _estimate_tokens(polished_text)

        # 使用生成时间计算速度（更准确）
        if processed and generation_time > 0:
            speed = token_count / generation_time if token_count > 0 else 0
            speed_label = f'    {speed:.1f} tokens/s' if speed > 0 else ''
        else:
            speed_label = ''

        return f'    模型结果{role_label}：{result_text}{speed_label}'
    
    async def process_loop(self) -> None:
        """主处理循环"""
        if not await self._ws_manager.connect():
            logger.warning("WebSocket 连接检查失败")
            return
        
        console.print('[green]连接成功\n')
        logger.info("WebSocket 连接成功")
        
        try:
            while True:
                await self._process_one_message()
                
        except ConnectionClosedError:
            console.print('[red]连接断开\n')
            logger.error("WebSocket 连接断开")
        except ConnectionClosedOK:
            console.print('[yellow]连接已正常关闭\n')
            logger.info("WebSocket 连接已正常关闭")
        except Exception as e:
            logger.error(f"接收结果时发生错误: {e}", exc_info=True)
            print(e)
        finally:
            self._cleanup()
    
    async def _process_one_message(self) -> None:
        """处理单条消息"""
        # 接收消息
        message = await self.state.websocket.recv()
        message = json.loads(message)
        
        # 使用 text 字段（简单拼接结果，用于语音输入）
        text = message['text']
        delay = message['time_complete'] - message['time_submit']
        
        logger.debug(
            f"接收到识别结果，文本: {text[:50]}{'...' if len(text) > 50 else ''}, "
            f"时延: {delay:.2f}s"
        )
        
        # 如果非最终结果，继续等待
        if not message['is_final']:
            return
        
        # 热词替换
        text = self._hotword_manager.substitute(text)
        text = TextOutput.strip_punc(text)
        
        logger.debug(f"热词替换后: {text[:50]}{'...' if len(text) > 50 else ''}")
        
        # 控制台输出
        console.print(f'    转录时延：{delay:.2f}s')
        console.print(f'    识别结果：[green]{text}')
        
        # 窗口兼容性检测
        window_info = get_active_window_info()
        paste = Config.paste
        
        if window_info:
            window_title = window_info.get('title', '')
            compatibility_apps = ['weixin', '微信', 'wechat', 'WeChat']
            if window_title in compatibility_apps:
                paste = True
                logger.debug(f"检测到兼容性应用: {window_title}，使用粘贴模式")
        
        # LLM 处理和输出
        llm_result = None
        if Config.llm_enabled:
            from util.llm.llm_process_text import llm_process_text
            llm_result = await llm_process_text(
                text,
                return_result=True,
                window_info=window_info,
                paste=paste
            )
        else:
            await self._text_output.output(text, paste=paste)
        
        # 保存录音与写入 md 文件
        file_audio = None
        if Config.save_audio:
            from util.client.diary.diary_writer import DiaryWriter
            
            # 重命名音频文件
            file_path = self.state.pop_audio_file(message['task_id'])
            if file_path:
                from util.client.audio.file_manager import AudioFileManager
                file_manager = AudioFileManager()
                file_manager.file_path = file_path
                file_audio = file_manager.rename(text, message['time_start'])
                logger.debug(f"保存录音文件: {file_audio}")
            
            # 写入日记
            diary_writer = DiaryWriter()
            diary_writer.write(text, message['time_start'], file_audio)
            logger.debug("写入 MD 文件")
        
        # LLM 结果显示和保存
        if Config.llm_enabled and llm_result and llm_result.processed:
            console.print(self._format_llm_result(llm_result))
            from util.llm.llm_write_md import write_llm_md
            write_llm_md(
                llm_result.input_text,
                llm_result.result,
                llm_result.role_name,
                message['time_start'],
                file_audio
            )
            logger.debug("写入 LLM MD 文件")
        
        console.line()
    
    def _cleanup(self) -> None:
        """清理资源"""
        if self.state.websocket is not None:
            try:
                if self.state.websocket.closed:
                    self.state.websocket = None
                    logger.debug("WebSocket 连接已清理")
            except Exception:
                self.state.websocket = None
