"""
LLM 剪贴板管理

负责读取和管理剪贴板内容，避免重复读取上一次的输出
"""
import pyclip


# 全局变量：记录上一次的输出内容
_last_output_content = ""

# 全局变量：记录每个角色最后一次使用的剪贴板内容
_last_clipboard_by_role = {}


def get_clipboard_text(role_config: dict = None, role_name: str = "") -> str:
    """
    获取剪贴板内容（如果启用且不重复）

    Args:
        role_config: 角色配置字典（如果为 None，则返回空字符串）
        role_name: 角色名称

    Returns:
        剪贴板内容，如果不应该使用则返回空字符串
    """
    global _last_output_content

    if not role_config:
        return ""

    if not role_config.get('enable_clipboard_read', False):
        return ""

    try:
        current_clipboard = pyclip.paste().decode('utf-8')
    except:
        return ""

    # 如果剪贴板内容和上一次输出一样，不使用（避免重复）
    if current_clipboard == _last_output_content:
        return ""

    # 检查长度限制
    clipboard_max_length = role_config.get('clipboard_max_length', 1000)
    if len(current_clipboard) > clipboard_max_length:
        current_clipboard = current_clipboard[:clipboard_max_length]

    # 如果开启了历史记录，检查剪贴板内容是否与上一次使用的相同
    if role_config.get('enable_history', False):
        last_clipboard = _last_clipboard_by_role.get(role_name, "")
        if current_clipboard == last_clipboard:
            # 剪贴板内容没有变化，且上一次已经使用过，不再加入上下文
            return ""

    return current_clipboard


def record_clipboard_usage(role_name: str, clipboard_text: str):
    """
    记录角色使用的剪贴板内容（用于下一轮判断是否重复）

    Args:
        role_name: 角色名称
        clipboard_text: 使用的剪贴板内容（空字符串表示没有使用）
    """
    global _last_clipboard_by_role
    _last_clipboard_by_role[role_name] = clipboard_text


def set_output_content(content: str, role_name: str = ""):
    """
    记录输出内容（用于避免重复读取）并更新剪贴板使用记录

    Args:
        content: 输出的内容
        role_name: 角色名称
    """
    global _last_output_content
    _last_output_content = content

    # 如果有角色名，更新该角色的剪贴板使用记录
    if role_name and content:
        record_clipboard_usage(role_name, content)


def copy_to_clipboard(content: str, role_name: str = ""):
    """
    复制内容到剪贴板

    Args:
        content: 要复制的内容
        role_name: 角色名称（用于更新剪贴板使用记录）
    """
    if content:
        pyclip.copy(content)
        set_output_content(content, role_name)
