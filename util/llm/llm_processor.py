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
from . import logger


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
        
        try:
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
        except Exception as e:
            # 处理已包装的 OpenAI 异常
            if isinstance(e, (OpenAIErrorWrapper, APIException)):
                raise

            # 捕获 Ollama SDK 原生异常
            if role_config.provider == 'ollama':
                try:
                    import ollama
                    if isinstance(e, (ollama.ResponseError, ollama.RequestError)):
                        error_msg = f"Ollama API 调用失败: {e}"
                        logger.error(error_msg)
                        raise APIException(error_msg, role_config.provider) from e
                except ImportError:
                    pass

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
        """统一构建请求参数"""
        params = {
            'model': role_config.model,
            'messages': messages,
            'temperature': role_config.temperature,
            'top_p': role_config.top_p,
        }

        if role_config.max_tokens > 0:
            params['max_tokens'] = role_config.max_tokens
            # 为 Ollama 映射 num_predict
            if role_config.provider == 'ollama':
                params['num_predict'] = role_config.max_tokens

        # 处理停止序列
        if role_config.stop:
            stop_list = role_config.stop
            if isinstance(stop_list, str):
                stop_list = [s.strip() for s in stop_list.split(',')]
            params['stop'] = stop_list

        # 合并额外选项
        if role_config.extra_options:
            params.update(role_config.extra_options)

        return params

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
        """执行流式请求并协调不同处理引擎"""
        
        if role_config.provider == 'ollama':
            result = self._process_ollama_stream(
                client, role_config, messages, callback, should_stop_check
            )
        else:
            result = self._process_openai_stream(
                client, request_params, callback, should_stop_check
            )

        full_response, total_tokens, generation_time = result

        # Token 估算兜底（针对 Ollama 等不返回 usage 的提供商）
        if total_tokens == 0 and full_response:
            from util.llm.llm_constants import estimate_tokens
            total_tokens = estimate_tokens(full_response)
            result = (full_response, total_tokens, generation_time)

        # 更新历史
        if role_config.enable_history and context_manager:
            context_manager.add_message('user', messages[-1]['content'])
            context_manager.add_message('assistant', full_response)
            logger.debug(f"已更新历史记录")

        return result

    def _process_ollama_stream(
        self,
        client: Any,
        role_config: RoleConfig,
        messages: List[Dict[str, str]],
        callback: Optional[Callable[[str], None]],
        should_stop_check: Optional[Callable[[], bool]]
    ) -> Tuple[str, int, float]:
        """专门处理 Ollama 原生流响应"""
        
        # 1. 统一构建参数并提取 Ollama 选项
        params = self._build_request_params(role_config, messages)
        ollama_options = {
            k: v for k, v in params.items() 
            if k in ['temperature', 'top_p', 'stop', 'num_predict']
        }
        
        # 2. 发起请求
        stream = client.chat(
            model=role_config.model,
            messages=messages,
            stream=True,
            options=ollama_options,
            think=role_config.enable_thinking
        )

        # 3. 迭代处理
        full_response, total_tokens, generation_start_time = "", 0, None
        
        for chunk in stream:
            if should_stop_check and should_stop_check():
                break

            if hasattr(chunk, 'message') and chunk.message.content:
                content = chunk.message.content
                full_response += content
                if generation_start_time is None:
                    generation_start_time = time.time()
                if callback:
                    callback(content)

            if hasattr(chunk, 'done') and chunk.done:
                total_tokens = getattr(chunk, 'eval_count', 0)

        generation_time = time.time() - generation_start_time if generation_start_time else 0.0
        return full_response.strip(), total_tokens, generation_time

    def _process_openai_stream(
        self,
        client: Any,
        params: Dict[str, Any],
        callback: Optional[Callable[[str], None]],
        should_stop_check: Optional[Callable[[], bool]]
    ) -> Tuple[str, int, float]:
        """专门处理 OpenAI 兼容 API 流响应"""
        
        # 排除 Ollama 专用的参数
        openai_params = {k: v for k, v in params.items() if k != 'num_predict'}
        openai_params['stream'] = True
        
        stream = client.chat.completions.create(**openai_params)

        full_response, total_tokens, generation_start_time = "", 0, None

        for chunk in stream:
            if should_stop_check and should_stop_check():
                try: stream.close()
                except: pass
                break

            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                if generation_start_time is None:
                    generation_start_time = time.time()
                if callback:
                    callback(content)

            if hasattr(chunk, 'usage') and chunk.usage:
                total_tokens = getattr(chunk.usage, 'completion_tokens', 0)

        generation_time = time.time() - generation_start_time if generation_start_time else 0.0
        return full_response.strip(), total_tokens, generation_time
