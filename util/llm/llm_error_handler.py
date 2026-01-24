"""
LLM 错误处理和用户提示

统一处理 LLM 异常，提供用户友好的错误提示
"""
from typing import Optional, Tuple
from util.llm.llm_exceptions import (
    OpenAIErrorWrapper,
    AuthenticationErrorWrapper,
    RateLimitErrorWrapper,
    TimeoutErrorWrapper,
    ConnectionErrorWrapper,
    APIResponseErrorWrapper,
)
from . import logger


def get_user_friendly_message(error: Exception) -> str:
    """
    获取用户友好的错误消息

    Args:
        error: 异常对象

    Returns:
        用户友好的错误消息
    """
    # 已包装的 OpenAI 异常
    if isinstance(error, OpenAIErrorWrapper):
        return error.user_message

    # 其他异常
    return f"处理失败: {type(error).__name__}"


def should_fallback_to_original(error: Exception) -> bool:
    """
    判断是否应该降级到原文本

    某些错误（如认证失败、连接失败）应该提示用户而不是降级
    其他错误（如超时、速率限制）可以降级

    Args:
        error: 异常对象

    Returns:
        True 表示应该降级到原文本，False 表示应该提示错误
    """
    # 认证失败：必须提示用户配置 API Key
    if isinstance(error, AuthenticationErrorWrapper):
        return False

    # 连接失败：提示用户检查网络和 API 地址
    if isinstance(error, ConnectionErrorWrapper):
        return False

    # API 响应错误：提示用户检查配置
    if isinstance(error, APIResponseErrorWrapper):
        return False

    # 超时和速率限制：可以降级到原文本
    if isinstance(error, (TimeoutErrorWrapper, RateLimitErrorWrapper)):
        return True

    # 其他异常：保守策略，降级
    return True


def show_error_notification(error: Exception, role_name: str = "LLM"):
    """
    显示错误通知（Toast 或控制台）

    Args:
        error: 异常对象
        role_name: 角色名称
    """
    user_msg = get_user_friendly_message(error)

    # 记录日志
    logger.warning(f"[{role_name}] {user_msg} - {error}")

    # 尝试显示 Toast 通知
    try:
        from util.ui.toast import ToastMessageManager, ToastMessage

        toast_manager = ToastMessageManager()

        # 错误提示使用红色背景，更大的尺寸
        msg = ToastMessage(
            text=f"❌ {role_name}: {user_msg}",
            font_size=16,           # 增大字体
            bg='#8B0000',           # 深红色
            fg='white',
            duration=5000,          # 显示 5 秒
            initial_width=0.6,      # 60% 屏幕宽度（使用百分比）
            initial_height=80,      # 固定最小高度 80 像素
            streaming=False,
            window_type='text'
        )
        toast_manager.add_message(msg)
        toast_manager.finish_last_toast()  # 自动销毁

    except Exception as e:
        # Toast 显示失败，回退到控制台
        logger.error(f"Toast 显示失败: {e}")


def handle_llm_error(error: Exception, original_text: str, role_name: str = "LLM",
                     fallback_text: Optional[str] = None) -> Tuple[str, bool]:
    """
    统一的 LLM 错误处理入口

    Args:
        error: 异常对象
        original_text: 原始输入文本
        role_name: 角色名称
        fallback_text: 降级时使用的文本（None 则使用 original_text）

    Returns:
        (输出文本, 是否成功)
    """
    # 判断是否应该降级
    if should_fallback_to_original(error):
        # 降级策略：使用原文本或 fallback_text
        result = fallback_text if fallback_text is not None else original_text
        logger.info(f"[{role_name}] 处理失败，降级到原文本: {error}")
        return (result, False)
    else:
        # 非降级策略：显示错误通知，返回空字符串
        show_error_notification(error, role_name)
        return ("", False)
