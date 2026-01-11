"""
LLM 模块

提供 LLM 相关的所有功能，包括角色管理、消息构建、上下文管理等"""

# 核心处理器
from .llm_handler import LLMHandler, get_handler, init_llm_system, polish_text

# 角色配置和加载
from .llm_role_config import RoleConfig
from .llm_role_loader import RoleLoader

# 上下文管理
from .llm_context import ContextManager

# 消息构建和客户端池
from .llm_message_builder import MessageBuilder
from .llm_client_pool import ClientPool

# RAG 和剪贴板/选中文字
from .llm_rag_adapter import HotwordsRAG
from .llm_clipboard import copy_to_clipboard
from .llm_get_selection import (
    get_selected_text,
    record_selection_usage
)

# 监控和输出
from .llm_watcher import LLMFileWatcher
from .llm_stop_monitor import reset, should_stop

from .llm_output_toast import handle_toast_mode
from .llm_output_typing import handle_typing_mode

from .llm_process_text import llm_process_text, LLMResult

__all__ = [
    # 核心
    'LLMHandler',
    'get_handler',
    'init_llm_system',
    'polish_text',

    # 角色管理
    'RoleConfig',
    'RoleLoader',

    # 上下文
    'ContextManager',

    # 组件
    'MessageBuilder',
    'ClientPool',
    'HotwordsRAG',

    # 剪贴板/选中文字
    'get_selected_text',
    'record_selection_usage',
    'copy_to_clipboard',

    # 监控
    'LLMFileWatcher',
    'reset',
    'should_stop',

    # 输出
    'handle_toast_mode',
    'handle_typing_mode',

    # 主入口
    'llm_process_text',
    'LLMResult',
]
