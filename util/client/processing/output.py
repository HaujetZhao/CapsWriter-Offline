# coding: utf-8
"""
文本输出模块

提供 TextOutput 类用于将识别结果输出到当前窗口。
"""

from __future__ import annotations

import asyncio
import platform
from typing import Optional

from pynput import keyboard
import pyclip

from config import ClientConfig as Config
from util.logger import get_logger

# 日志记录器
logger = get_logger('client')


class TextOutput:
    """
    文本输出器
    
    提供文本输出功能，支持模拟打字和粘贴两种方式。
    """
    
    @staticmethod
    def strip_punc(text: str) -> str:
        """
        消除末尾标点
        
        Args:
            text: 原始文本
            
        Returns:
            去除末尾标点后的文本
        """
        if not text:
            return text
        return text.rstrip('，。！？,.!?')
    
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
        
        # 消除末尾标点
        text = self.strip_punc(text)
        
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
        
        # 粘贴结果
        if platform.system() == 'Darwin':
            keyboard.press(55)
            keyboard.press(9)
            keyboard.release(55)
            keyboard.release(9)
        else:
            keyboard.send('ctrl + v')
        
        # 还原剪贴板
        if Config.restore_clip:
            await asyncio.sleep(0.1)
            pyclip.copy(temp)
            logger.debug("剪贴板已恢复")
    
    def _type_text(self, text: str) -> None:
        """
        通过模拟打字方式输出文本

        Args:
            text: 要输出的文本
        """
        logger.debug(f"使用打字方式输出文本，长度: {len(text)}")
        controller = keyboard.Controller()
        controller.type(text)
