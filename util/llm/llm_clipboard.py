"""
LLM 输出剪贴板管理

负责将 LLM 输出内容复制到剪贴板
"""
import pyclip


def copy_to_clipboard(content: str):
    """
    复制内容到剪贴板

    Args:
        content: 要复制的内容
    """
    if content:
        pyclip.copy(content)
