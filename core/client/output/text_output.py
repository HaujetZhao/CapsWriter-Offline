# coding: utf-8
"""
文本输出模块

提供 TextOutput 类用于将识别结果输出到当前窗口。
"""

from __future__ import annotations

import asyncio
import platform
from typing import Optional
import re

import keyboard
import pyclip
from pynput import keyboard as pynput_keyboard

from config_client import ClientConfig as Config
from core.tools.window_detector import get_active_window_info
from . import logger


# 语义字符计数模式：匹配中文字、英文单词、数字
# 中文字（含日韩等）各算 1 个语义单元，英文连续字母算 1 个，连续数字算 1 个
_SEMANTIC_UNIT_RE = re.compile(
    r'[一-鿿㐀-䶿豈-﫿]'
    r'|[a-zA-Z]+'
    r'|\d+'
)


def count_semantic_units(text: str) -> int:
    """计算语义字符数：中文字=1，英文单词=1，数字=1"""
    return len(_SEMANTIC_UNIT_RE.findall(text))



class TextOutput:
    """
    文本输出器
    
    提供文本输出功能，支持模拟打字和粘贴两种方式。
    """
    
    @staticmethod
    def strip_punc(text: str) -> str:
        """
        消除末尾最后一个标点

        语义字符数不超过 trash_punc_thresh 时去除末尾标点，
        超过时保留标点（长句正常说话场景）。
        在 trash_punc_apps 指定的应用中，不受阈值限制，必定去除。

        Args:
            text: 原始文本

        Returns:
            处理后的文本
        """
        if not text or not Config.trash_punc:
            return text

        # 检查是否在强制去标点的应用中
        force_strip = False
        if Config.trash_punc_apps:
            process_name = get_active_window_info().get('process_name', '').lower()
            if any(app.lower() == process_name for app in Config.trash_punc_apps):
                force_strip = True

        if not force_strip and Config.trash_punc_thresh > 0 and count_semantic_units(text) > Config.trash_punc_thresh:
            return text

        clean_text = re.sub(f"(?<=.)[{Config.trash_punc}]$", "", text)
        return clean_text
    
    async def output(self, text: str, paste: Optional[bool] = None) -> None:
        """
        输出识别结果
        
        根据配置选择使用模拟打字或粘贴方式输出文本。
        
        Args:
            text: 要输出的文本
            paste: 是否使用粘贴方式（None 表示使用配置值）
        """
        if not text:
            return
        
        # 确定输出方式
        if paste is None:
            paste = Config.paste
        
        if paste:
            await self._paste_text(text)
        else:
            self._type_text(text)
    
    async def _paste_text(self, text: str) -> None:
        """
        通过粘贴方式输出文本
        
        Args:
            text: 要粘贴的文本
        """
        logger.debug(f"使用粘贴方式输出文本，长度: {len(text)}")
        
        # 保存剪贴板
        try:
            temp = pyclip.paste().decode('utf-8')
        except Exception:
            temp = ''
        
        # 复制结果
        pyclip.copy(text)
        
        # 粘贴结果（使用 pynput 模拟 Ctrl+V）
        controller = pynput_keyboard.Controller()
        if platform.system() == 'Darwin':
            # macOS: Command+V
            with controller.pressed(pynput_keyboard.Key.cmd):
                controller.tap('v')
        else:
            # Windows/Linux: Ctrl+V
            with controller.pressed(pynput_keyboard.Key.ctrl):
                controller.tap('v')
        
        logger.debug("已发送粘贴命令 (Ctrl+V)")
        
        # 还原剪贴板
        if Config.restore_clip:
            await asyncio.sleep(0.1)
            pyclip.copy(temp)
            logger.debug("剪贴板已恢复")
    
    def _type_text(self, text: str) -> None:
        """
        通过模拟打字方式输出文本

        使用 keyboard.write 替代 pynput.keyboard.Controller.type()，
        避免与中文输入法冲突。

        Args:
            text: 要输出的文本
        """
        logger.debug(f"使用打字方式输出文本，长度: {len(text)}")
        keyboard.write(text)
