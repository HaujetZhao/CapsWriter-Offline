# coding: utf-8
"""
剪贴板工具模块

提供统一的剪贴板操作接口，包括：
1. 安全读取剪贴板（支持多种编码）
2. 安全写入剪贴板
3. 剪贴板保存/恢复上下文管理器
4. 粘贴文本（模拟 Ctrl+V）
"""
import asyncio
import platform
from contextlib import contextmanager
import pyclip
from pynput import keyboard
from . import logger


# 支持的编码列表
CLIPBOARD_ENCODINGS = ['utf-8', 'gbk', 'utf-16', 'latin1']


def safe_paste() -> str:
    """
    安全地从剪贴板读取并解码文本

    尝试多种编码方式，确保能够正确读取

    Returns:
        解码后的文本字符串，失败返回空字符串
    """
    try:
        clipboard_data = pyclip.paste()

        # 尝试多种编码方式
        for encoding in CLIPBOARD_ENCODINGS:
            try:
                return clipboard_data.decode(encoding)
            except (UnicodeDecodeError, AttributeError):
                continue

        # 如果所有编码都失败，返回空字符串
        logger.debug(f"剪贴板解码失败，尝试了编码: {CLIPBOARD_ENCODINGS}")
        return ""

    except Exception as e:
        logger.warning(f"剪贴板读取失败: {e}")
        return ""


def safe_copy(content: str) -> bool:
    """
    安全地复制内容到剪贴板

    Args:
        content: 要复制的内容

    Returns:
        是否成功
    """
    if not content:
        return False

    try:
        pyclip.copy(content)
        logger.debug(f"剪贴板写入成功，长度: {len(content)}")
        return True
    except Exception as e:
        logger.warning(f"剪贴板写入失败: {e}")
        return False


def copy_to_clipboard(content: str):
    """
    复制内容到剪贴板（兼容旧 API）

    Args:
        content: 要复制的内容
    """
    safe_copy(content)


@contextmanager
def save_and_restore_clipboard():
    """
    剪贴板保存/恢复上下文管理器

    用法:
        with save_and_restore_clipboard():
            # 在这里操作剪贴板
            pyclip.copy("临时内容")
        # 退出后剪贴板恢复原内容
    """
    original = safe_paste()
    try:
        yield
    finally:
        if original:
            pyclip.copy(original)
            logger.debug("剪贴板已恢复")


async def paste_text(text: str, restore_clipboard: bool = True):
    """
    通过模拟 Ctrl+V 粘贴文本

    Args:
        text: 要粘贴的文本
        restore_clipboard: 粘贴后是否恢复原剪贴板内容
    """
    # 保存剪切板
    original = ''
    if restore_clipboard:
        try:
            original = safe_paste()
        except:
            pass

    # 复制要粘贴的文本
    pyclip.copy(text)
    logger.debug(f"已复制文本到剪贴板，长度: {len(text)}")

    # 粘贴结果（使用 pynput 模拟 Ctrl+V）
    controller = keyboard.Controller()
    if platform.system() == 'Darwin':
        # macOS: Command+V
        with controller.pressed(keyboard.Key.cmd):
            controller.tap('v')
    else:
        # Windows/Linux: Ctrl+V
        with controller.pressed(keyboard.Key.ctrl):
            controller.tap('v')
    
    logger.debug("已发送粘贴命令 (Ctrl+V)")

    # 还原剪贴板
    if restore_clipboard and original:
        await asyncio.sleep(0.1)
        pyclip.copy(original)
        logger.debug("剪贴板已恢复")
