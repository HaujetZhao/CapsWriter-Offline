"""
LLM 自定义异常

定义 LLM 模块的异常层次结构
"""
from openai import AuthenticationError, RateLimitError, APITimeoutError, APIConnectionError, APIError


# ======================================================================
# --- 基础异常 ---

class LLMException(Exception):
    """LLM 模块基础异常"""

    pass


# ======================================================================
# --- OpenAI SDK 异常包装 ---

class OpenAIErrorWrapper(LLMException):
    """OpenAI SDK 异常的包装基类"""

    def __init__(self, original_error: Exception, provider: str = 'unknown'):
        self.original_error = original_error
        self.provider = provider
        super().__init__(f"[{provider}] {type(original_error).__name__}: {str(original_error)}")


class AuthenticationErrorWrapper(OpenAIErrorWrapper):
    """认证失败异常 (401)"""
    user_message = "API 认证失败，请检查 API Key 配置"


class RateLimitErrorWrapper(OpenAIErrorWrapper):
    """速率限制异常 (429)"""
    user_message = "API 速率限制，请稍后重试"


class TimeoutErrorWrapper(OpenAIErrorWrapper):
    """请求超时异常"""
    user_message = "API 请求超时，请检查网络连接"


class ConnectionErrorWrapper(OpenAIErrorWrapper):
    """连接失败异常"""
    user_message = "API 连接失败，请检查网络和 API 地址"


class APIResponseErrorWrapper(OpenAIErrorWrapper):
    """API 响应错误异常 (4xx, 5xx)"""
    user_message = "API 响应错误，请检查配置和参数"


# OpenAI 异常映射表
OPENAI_EXCEPTION_MAP = {
    AuthenticationError: AuthenticationErrorWrapper,
    RateLimitError: RateLimitErrorWrapper,
    APITimeoutError: TimeoutErrorWrapper,
    APIConnectionError: ConnectionErrorWrapper,
    APIError: APIResponseErrorWrapper,
}


def wrap_openai_error(error: Exception, provider: str = 'unknown') -> LLMException:
    """
    将 OpenAI SDK 异常包装为自定义异常

    Args:
        error: OpenAI SDK 原生异常
        provider: API 提供商名称

    Returns:
        包装后的自定义异常
    """
    error_type = type(error)
    wrapper_class = OPENAI_EXCEPTION_MAP.get(error_type)

    if wrapper_class:
        return wrapper_class(error, provider)
    else:
        # 未知异常类型，使用通用包装
        return OpenAIErrorWrapper(error, provider)


# ======================================================================
# --- 角色相关异常 ---

class RoleException(LLMException):
    """角色配置异常"""

    pass


class RoleNotFoundError(RoleException):
    """角色未找到异常"""

    def __init__(self, role_name: str):
        self.role_name = role_name
        super().__init__(f"角色未找到: {role_name}")


class RoleLoadError(RoleException):
    """角色加载失败异常"""

    def __init__(self, file_path: str, reason: str):
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"角色加载失败: {file_path}, 原因: {reason}")


class InvalidRoleConfigError(RoleException):
    """无效的角色配置异常"""

    def __init__(self, role_name: str, missing_fields: list):
        self.role_name = role_name
        self.missing_fields = missing_fields
        super().__init__(f"无效的角色配置 '{role_name}'，缺少字段: {', '.join(missing_fields)}")


# ======================================================================
# --- 上下文相关异常 ---

class ContextException(LLMException):
    """上下文管理异常"""

    pass


class ContextExpiredError(ContextException):
    """上下文已过期异常"""

    pass


# ======================================================================
# --- API 相关异常 ---

class APIException(LLMException):
    """API 调用异常"""

    pass


class APIConnectionError(APIException):
    """API 连接失败异常"""

    def __init__(self, provider: str, api_url: str, reason: str):
        self.provider = provider
        self.api_url = api_url
        self.reason = reason
        super().__init__(f"API 连接失败 ({provider}): {api_url}, 原因: {reason}")


class APIResponseError(APIException):
    """API 响应错误异常"""

    def __init__(self, provider: str, status_code: int = None, reason: str = None):
        self.provider = provider
        self.status_code = status_code
        self.reason = reason
        msg = f"API 响应错误 ({provider})"
        if status_code:
            msg += f", 状态码: {status_code}"
        if reason:
            msg += f", 原因: {reason}"
        super().__init__(msg)


class StreamInterruptedError(APIException):
    """流式输出被中断异常"""

    def __init__(self, chunks_received: int = 0):
        self.chunks_received = chunks_received
        super().__init__(f"流式输出被中断，已接收 {chunks_received} 个 chunks")


# ======================================================================
# --- RAG 相关异常 ---

class RAGException(LLMException):
    """RAG 检索异常"""

    pass


class HotwordsLoadError(RAGException):
    """热词加载失败异常"""

    def __init__(self, file_path: str, reason: str):
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"热词加载失败: {file_path}, 原因: {reason}")
