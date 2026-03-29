# coding: utf-8
"""
文本格式化处理器

负责对识别出的原始文本进行后期处理，如标点补全、ITN转换、空格调整等。
"""

from util.tools.chinese_itn import chinese_to_num
from util.tools.format_tools import adjust_space
from config_server import ServerConfig as Config


class TextFormatter:
    """
    文本格式化处理器
    
    整合多种文本处理工具，提供统一的格式化接口。
    """
    def __init__(self, punc_model=None):
        """
        初始化格式化器
        
        Args:
            punc_model: 标点预测模型实例（可选）
        """
        self.punc_model = punc_model

    def format(self, text: str) -> str:
        """
        对输入文本应用一组格式化规则
        
        流程：
        1. 调整中英文/数字间的空格 (adjust_space)
        2. 自动补全标点符号 (punc_model.add_punctuation)
        3. 处理 ITN (中文数字转阿拉伯数字)
        
        Args:
            text: 原始待处理文本
            
        Returns:
            处理完成的格式化文本
        """
        if not text:
            return ""

        # 1. 调整中英文空格
        if Config.format_spell:
            text = adjust_space(text)

        # 2. 增加标点
        if self.punc_model:
            try:
                text = self.punc_model.add_punctuation(text)
            except Exception as e:
                from . import logger
                logger.warning(f"标点补全失败: {e}")

        # 3. 中文数字转阿拉伯数字
        if Config.format_num:
            try:
                text = chinese_to_num(text)
            except Exception as e:
                from . import logger
                logger.warning(f"ITN 转换失败: {e}")

        return text
