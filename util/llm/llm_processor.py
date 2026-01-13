"""
LLM 处理引擎

功能：
1. 执行 LLM API 调用
2. 处理流式输出
3. 更新上下文历史
4. 统一的错误处理和包装
5. 精确的生成时间统计（从第一个 token 开始）
"""
import time
from typing import Callable, Optional, Dict, Any, List, Tuple
from util.llm.llm_role_config import RoleConfig
from util.llm.llm_interfaces import IContextManager
from util.llm.llm_client_pool import ClientPool
from util.llm.llm_exceptions import (
    APIException,
    wrap_openai_error, OpenAIErrorWrapper,
    TimeoutErrorWrapper
)
from util.logger import get_logger

logger = get_logger('client')


class LLMProcessor:
    """LLM 处理引擎 - 负责 API 调用和流式输出"""

    def __init__(self, client_pool: ClientPool):
        """
        Args:
            client_pool: 客户端池
        """
        self.client_pool = client_pool

    def process(
        self,
        role_config: RoleConfig,
        messages: List[Dict[str, str]],
        callback: Optional[Callable[[str], None]] = None,
        should_stop_check: Optional[Callable[[], bool]] = None,
        context_manager: Optional[IContextManager] = None
    ) -> Tuple[str, int, float]:
        """
        执行 LLM 处理

        Args:
            role_config: 角色配置
            messages: 消息列表
            callback: 流式输出回调函数
            should_stop_check: 检查是否应该停止的函数
            context_manager: 上下文管理器（用于更新历史）

        Returns:
            (处理后的文本, 输出token数, 生成时间秒)
        """
        logger.info(f"开始 LLM 处理，模型: {role_config.model}")

        # 获取客户端
        logger.debug(f"获取 LLM 客户端，提供商: {role_config.provider}, API: {role_config.api_url}")
        client = self.client_pool.get_client(
            provider=role_config.provider,
            api_url=role_config.api_url,
            api_key=role_config.api_key
        )

        # 构建请求参数
        request_params = self._build_request_params(role_config, messages)
        logger.debug(f"请求参数: model={role_config.model}, stream=True")

        try:
            logger.debug("开始调用 LLM API（流式）")
            return self._stream_request(
                client,
                request_params,
                callback,
                should_stop_check,
                role_config,
                context_manager,
                messages
            )

        except OpenAIErrorWrapper:
            # 已包装的 OpenAI 异常，直接重新抛出
            raise
        except APIException:
            # 其他 API 相关异常，直接重新抛出
            raise
        except Exception as e:
            # 捕获 OpenAI SDK 原生异常并包装
            import openai

            # 处理 httpx 超时异常（在流式读取时发生）
            if 'httpx' in str(type(e).__module__):
                error_type = type(e).__name__
                if 'Timeout' in error_type or 'timeout' in error_type:
                    # httpx.ReadTimeout 或 httpx.TimeoutException
                    wrapped_error = TimeoutErrorWrapper(e, role_config.provider)
                    logger.error(f"LLM API 请求超时: {wrapped_error}")
                    raise wrapped_error from e

            if isinstance(e, (
                openai.AuthenticationError,
                openai.RateLimitError,
                openai.APITimeoutError,
                openai.APIConnectionError,
                openai.APIError
            )):
                wrapped_error = wrap_openai_error(e, role_config.provider)
                logger.error(f"LLM API 调用失败: {wrapped_error}")
                raise wrapped_error from e

            # 其他未预期的异常，包装为 APIException 并抛出
            import traceback
            error_msg = f"LLM 处理失败: {e}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            raise APIException(error_msg, role_config.provider) from e

    def _build_request_params(
        self,
        role_config: RoleConfig,
        messages: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """构建请求参数"""
        request_params = {
            'model': role_config.model,
            'messages': messages,
        }

        # 添加生成参数
        if role_config.temperature is not None:
            request_params['temperature'] = role_config.temperature

        if role_config.top_p is not None:
            request_params['top_p'] = role_config.top_p

        if role_config.max_tokens > 0:
            request_params['max_tokens'] = role_config.max_tokens
            logger.debug(f"最大tokens: {role_config.max_tokens}")

        # 处理停止序列
        stop = role_config.stop
        if stop:
            if isinstance(stop, str):
                request_params['stop'] = [s.strip() for s in stop.split(',')]
            else:
                request_params['stop'] = stop
            logger.debug(f"停止序列: {request_params['stop']}")

        # 合并额外选项
        if role_config.extra_options:
            request_params.update(role_config.extra_options)

        return request_params

    def _stream_request(
        self,
        client: Any,
        request_params: Dict[str, Any],
        callback: Optional[Callable[[str], None]],
        should_stop_check: Optional[Callable[[], bool]],
        role_config: RoleConfig,
        context_manager: Optional[IContextManager],
        messages: List[Dict[str, str]]
    ) -> Tuple[str, int, float]:
        """执行流式请求

        Returns:
            (响应文本, token数, 生成时间秒)
        """
        request_params['stream'] = True
        stream = client.chat.completions.create(**request_params)

        full_response = ""
        total_tokens = 0
        chunk_count = 0

        # 计时：从第一个 token 开始
        first_token_time = None
        generation_start_time = None

        for chunk in stream:
            chunk_count += 1
            # 检查是否应该停止
            if should_stop_check and should_stop_check():
                logger.debug(f"收到停止信号，当前已接收 {chunk_count} 个 chunks")
                # 关闭流式响应，终止模型继续生成
                try:
                    stream.close()
                except:
                    pass
                # 中断循环，返回已生成的部分
                break

            if chunk.choices[0].delta.content:
                content_chunk = chunk.choices[0].delta.content
                full_response += content_chunk

                # 记录第一个 token 到达时间
                if first_token_time is None:
                    first_token_time = time.time()
                    generation_start_time = first_token_time

                if callback:
                    callback(content_chunk)

            # 统计 token 数（在最后一个 chunk 中获取）
            # 注意：某些提供商（如 Ollama）的流式响应不包含 usage
            if hasattr(chunk, 'usage') and chunk.usage:
                if hasattr(chunk.usage, 'completion_tokens'):
                    tokens = chunk.usage.completion_tokens or 0
                    if tokens > 0:
                        # 使用最后一个非零的 token 数
                        total_tokens = tokens

        # 计算生成时间（从第一个 token 到最后一个 token）
        generation_time = 0.0
        if generation_start_time is not None:
            generation_end_time = time.time()
            generation_time = generation_end_time - generation_start_time

        # 如果 API 没有返回 token 数，使用估算（针对 Ollama 等不返回 usage 的提供商）
        if total_tokens == 0 and full_response:
            from util.llm.llm_constants import estimate_tokens
            total_tokens = estimate_tokens(full_response)
            logger.debug(f"API 未返回 token 数，使用估算值: {total_tokens}")

        logger.debug(f"LLM 响应完成，接收 {chunk_count} 个 chunks, 输出tokens: {total_tokens}, 响应长度: {len(full_response)}, 生成时间: {generation_time:.3f}秒")
        # 记录响应内容（截断过长内容）
        preview_len = min(len(full_response), 500)
        logger.debug(f"LLM 响应内容: {full_response[:preview_len]}{'...' if len(full_response) > preview_len else ''}")

        # 更新历史
        if role_config.enable_history and context_manager:
            # 保存完整的用户提示词（包含剪贴板、热词等）
            context_manager.add_message('user', messages[-1]['content'])
            context_manager.add_message('assistant', full_response)
            logger.debug(f"已更新历史记录")

        return (full_response.strip(), total_tokens, generation_time)
