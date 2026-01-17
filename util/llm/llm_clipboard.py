"""
LLM 剪贴板工具

提供统一的剪贴板操作接口，包括：
1. 安全读取剪贴板（支持多种编码）
2. 安全写入剪贴板
3. 剪贴板保存/恢复上下文管理器
4. 粘贴文本（模拟 Ctrl+V）

此模块为向后兼容保留，实际实现已移至 util.client.shortcut.clipboard
"""
# 从新位置导入，保持向后兼容
from util.client.shortcut.clipboard import (
    safe_paste,
    safe_copy,
    paste_text,
    save_and_restore_clipboard,
    copy_to_clipboard,
    CLIPBOARD_ENCODINGS
)

__all__ = [
    'safe_paste',
    'safe_copy',
    'paste_text',
    'save_and_restore_clipboard',
    'copy_to_clipboard',
    'CLIPBOARD_ENCODINGS'
]
