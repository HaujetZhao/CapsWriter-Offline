# coding: utf-8
"""
识别结果处理模块

提供 ResultProcessor 类用于处理服务端返回的识别结果。
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Optional

from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from config_client import ClientConfig as Config
from util.client.state import console
from util.client.websocket_manager import WebSocketManager
from util.hotword import get_hotword_manager
from util.client.output.text_output import TextOutput
from util.tools.window_detector import get_active_window_info
from . import logger
from util.common.lifecycle import lifecycle
from util.client.state import get_state

if TYPE_CHECKING:
    from util.client.state import ClientState



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
        self._hotword_manager = get_hotword_manager()
        self._text_output = TextOutput()
        self._exit_event = asyncio.Event()
        self._loop = asyncio.get_running_loop()  # 保存事件循环引用

    def request_exit(self):
        """请求退出处理循环（线程安全）"""
        logger.info("收到退出请求，设置退出事件")

        # 线程安全地设置事件
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._exit_event.set)
            logger.debug("已通过 call_soon_threadsafe 设置退出事件")
        else:
            self._exit_event.set()
            logger.debug("已直接设置退出事件")
    
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
    
    def _log_modifier_key_state(self) -> None:
        """
        检测并记录当前按下的所有键
        
        用于调试按键卡住问题。
        """
        try:
            import keyboard
            
            # 获取所有当前按下的键
            pressed_keys = keyboard._pressed_events
            
            # if pressed_keys:
            key_names = list(pressed_keys.keys())
            logger.debug(f"当前按下的键: {key_names}")
                
        except Exception as e:
            logger.debug(f"检测按键状态失败: {e}")
    
    async def process_loop(self) -> None:
        """主处理循环"""
        if not await self._ws_manager.connect():
            logger.warning("WebSocket 连接检查失败")
            return

        console.print('[green]连接成功\n')
        logger.info("WebSocket 连接成功")

        try:
            while True:
                # 检查退出事件
                if self._exit_event.is_set():
                    logger.info("检测到退出事件，停止处理循环")
                    break

                # 创建一个任务来接收消息
                recv_task = asyncio.create_task(self.state.websocket.recv())
                logger.debug("已创建接收消息任务")

                # 创建一个任务来等待退出事件
                exit_wait_task = asyncio.create_task(self._exit_event.wait())
                logger.debug("已创建退出等待任务")

                # 等待任意一个任务完成
                done, pending = await asyncio.wait(
                    [recv_task, exit_wait_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                logger.debug(f"任务完成: done={len(done)}, pending={len(pending)}")

                # 取消未完成的任务
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

                # 检查是否是退出请求
                if exit_wait_task in done:
                    logger.info("收到退出请求，停止处理循环")
                    # 取消接收任务
                    if recv_task not in done and not recv_task.done():
                        recv_task.cancel()
                        try:
                            await recv_task
                        except asyncio.CancelledError:
                            pass
                    break

                # 如果是接收任务完成，处理消息
                if recv_task in done:
                    try:
                        message = recv_task.result()
                        # 再次检查退出标志
                        if lifecycle.is_shutting_down:
                            logger.info("处理消息前检测到退出请求")
                            break
                        logger.debug("开始处理消息")
                        await self._handle_message(message)
                        logger.debug("消息处理完成")
                    except asyncio.CancelledError:
                        raise
                    except ConnectionClosedError:
                        logger.warning("WebSocket 连接已关闭")
                        break
                    except Exception as e:
                        logger.error(f"处理消息时发生错误: {e}", exc_info=True)
                        raise

        except ConnectionClosedError:
            console.print('[red]连接断开\n')
            logger.error("WebSocket 连接断开")
        except ConnectionClosedOK:
            console.print('[yellow]连接已正常关闭\n')
            logger.info("WebSocket 连接已正常关闭")
        except asyncio.CancelledError:
            logger.info("处理循环被取消")
            raise
        except Exception as e:
            logger.error(f"接收结果时发生错误: {e}", exc_info=True)
            print(e)
        finally:
            self._cleanup()

    async def _handle_message(self, message: str) -> None:
        """处理接收到的消息"""
        import json
        
        # 再次检查退出标志
        if lifecycle.is_shutting_down:
            return

        message = json.loads(message)

        # 使用 text 字段（简单拼接结果，用于语音输入）
        text = message['text']
        original_text = text  # 保存原始识别结果
        delay = message['time_complete'] - message['time_submit']

        if message['is_final']:
            logger.info(f"收到最终识别结果: {text}, 时延: {delay:.2f}s")
        else:
            logger.debug(
                f"接收到识别结果，文本: {text[:50]}{'...' if len(text) > 50 else ''}, "
                f"时延: {delay:.2f}s"
            )

        # 如果非最终结果，继续等待
        if not message['is_final']:
            return

        # 繁体转换
        if Config.traditional_convert:
            try:
                from util.zhconv import convert as zhconv_convert
                text = zhconv_convert(text, Config.traditional_locale)
                logger.debug(f"繁体转换后: {text[:50]}{'...' if len(text) > 50 else ''}")
            except Exception as e:
                logger.warning(f"繁体转换失败: {e}")

        # 1. 音素检索，热词替换
        correction_result = self._hotword_manager.get_phoneme_corrector().correct(text, k=10)
        if Config.hot:
            text = correction_result.text

        # 2. 规则纠错
        text = self._hotword_manager.get_rule_corrector().substitute(text)
        text = TextOutput.strip_punc(text)

        # 保存最近一次识别结果
        self.state.last_recognition_text = text

        # 控制台输出
        console.print(f'    转录时延：{delay:.2f}s')

        # 先显示原始识别结果
        original_text_stripped = TextOutput.strip_punc(original_text)
        console.print(f'    识别结果：[green]{original_text_stripped}')

        # 如果发生了热词替换，显示替换后的结果
        if original_text_stripped != text:
            console.print(f'    热词替换：[cyan]{text}')
            logger.debug(f"热词替换后: {text[:50]}{'...' if len(text) > 50 else ''}")

        # 热词匹配情况
        matched_hotwords = correction_result.matchs
        potential_hotwords = correction_result.similars

        # 1. 显示完全匹配/已替换的热词
        if matched_hotwords and Config.hot:
            # 提取热词文本 (现为 (原词, 热词, 分数))
            replaced_info = [f"{origin}->[green4]{hw}[/]" for origin, hw, score in matched_hotwords]
            console.print(f'    完全匹配：{", ".join(replaced_info)}')

        # 2. 显示潜在热词（从上下文热词中排除已替换的）
        if potential_hotwords and Config.hot:
            replaced_set = {hw for origin, hw, score in matched_hotwords}
            potential_matches = [(origin, hw, score) for origin, hw, score in potential_hotwords if hw not in replaced_set]
            
            if potential_matches:
                # 格式化潜在匹配列表，显示分数
                potential_str = ", ".join([f"{origin}->{hw}({score:.2f})" for origin, hw, score in potential_matches[:5]])
                if len(potential_matches) > 5:
                    potential_str += f" ... (共{len(potential_matches)}个)"
                console.print(f'    潜在热词：[yellow]{potential_str}')

        # 窗口兼容性检测
        paste = Config.paste
        window_info = get_active_window_info()

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
                paste=paste,
                matched_hotwords=potential_hotwords  # 传递上下文热词给 LLM
            )
        else:
            await self._text_output.output(text, paste=paste)
            get_state().set_output_text(text)

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

        # 检测修饰键状态（调试用）
        self._log_modifier_key_state()

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
