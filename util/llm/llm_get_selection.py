"""
LLM 获取选中文字功能

功能：
1. 获取当前剪贴板内容（用于还原）
2. 模拟 Ctrl+C 复制选中的文字
3. 读取新的剪贴板内容
4. 还原原来的剪贴板内容
5. 判断内容是否变化，返回选中的文字
"""
import time
import pyclip
import keyboard


# 全局变量：记录每个角色最后一次使用的选中文字
_last_selection_by_role = {}


def safe_paste_decode() -> str:
    """
    安全地从剪贴板读取并解码文本
    尝试多种编码方式，确保能够正确读取

    Returns:
        解码后的文本字符串，失败返回空字符串
    """
    try:
        clipboard_data = pyclip.paste()

        # 尝试多种编码方式
        encodings = ['utf-8', 'gbk', 'utf-16', 'latin1']

        for encoding in encodings:
            try:
                return clipboard_data.decode(encoding)
            except (UnicodeDecodeError, AttributeError):
                continue

        # 如果所有编码都失败，返回空字符串
        print(f"[剪贴板解码] 无法解码剪贴板内容，尝试了编码: {encodings}")
        return ""

    except Exception as e:
        print(f"[剪贴板解码] 读取失败: {e}")
        return ""


def get_selected_text(role_config) -> str:
    """
    获取用户当前选中的文字（通过模拟 Ctrl+C）

    Args:
        role_config: 角色配置 RoleConfig 对象

    Returns:
        选中的文字，如果不应该使用则返回空字符串
    """
    global _last_selection_by_role

    # 检查是否启用获取选中文字
    if not role_config.enable_read_selection:
        return ""

    role_name = role_config.name

    try:
        # 保存当前剪贴板内容
        original_clipboard = safe_paste_decode()

        # 模拟 Ctrl+C 复制选中的文字
        keyboard.press_and_release('ctrl+c')

        # 等待复制操作完成
        time.sleep(0.1)

        # 读取新的剪贴板内容
        selected_text = safe_paste_decode()

        # 还原原来的剪贴板内容
        pyclip.copy(original_clipboard)

        # 如果内容没有变化，说明没有选中文字，返回空字符串
        if selected_text == original_clipboard:
            return ""

        # 检查长度限制
        max_length = getattr(role_config, 'selection_max_length', 1000)
        if len(selected_text) > max_length:
            selected_text = selected_text[:max_length]

        # 如果开启了历史记录，检查选中文字是否与上一次使用的相同
        if role_config.enable_history:
            last_selection = _last_selection_by_role.get(role_name, "")
            if selected_text == last_selection:
                # 选中文字没有变化，且上一次已经使用过，不再加入上下文
                return ""

        # 检查是否只包含空白字符（空格、制表符、换行等）
        if not selected_text.strip():
            return ""

        return selected_text

    except Exception as e:
        print(f"[获取选中文字] 错误: {e}")
        return ""


def record_selection_usage(role_config, selection_text: str):
    """
    记录角色使用的选中文字（用于下一轮判断是否重复）

    Args:
        role_config: 角色配置 RoleConfig 对象
        selection_text: 使用的选中文字（空字符串表示没有使用）
    """
    global _last_selection_by_role
    role_name = role_config.name
    _last_selection_by_role[role_name] = selection_text

