# coding: utf-8
"""
文本格式化工具

提供中英文混排文本的空格调整功能。
主要用于调整识别结果中中英文之间的空格。
"""

import re
from typing import Match

# 匹配中文字符包围的英文/数字序列
# i 忽略大小写，x 开启注释模式
_EN_IN_ZH_PATTERN = re.compile(r"""(?ix)
    ([\u4e00-\u9fa5])?                  # 左侧：中文
    ([a-z0-9][a-z0-9\s'.,!?-]*)        # 中间：英文数字序列（含常见标点和内部空格）
    ([\u4e00-\u9fa5])?                  # 右侧：中文
""")


def _replacer(match: Match) -> str:
    """
    替换匹配的中英混排文本，调整空格
    """
    left: str = match.group(1) or ''
    center: str = match.group(2) or ''
    right: str = match.group(3) or ''
    
    # 不再对 center 内部进行任何破坏性的“单字母合并”
    # 保持原有的空格和标点
    final = center.strip()
    
    # 判断是否包含英文字体，决定是否加空格
    has_alpha = bool(re.search(r'[a-zA-Z]', final))
    
    # 处理左侧：中文 + 英文 -> 中文 + 空格 + 英文
    if left and has_alpha:
        final = left + ' ' + final
    else:
        final = left + final
        
    # 处理右侧：英文 + 中文 -> 英文 + 空格 + 中文
    if right and has_alpha:
        final = final + ' ' + right
    else:
        final = final + right

    return final



def adjust_space(text: str) -> str:
    """
    调整中英文之间的空格
    
    在中文和英文之间插入适当的空格，使文本排版更美观。
    同时会将连续的单个英文字母（如 "A B C"）合并为 "ABC"。
    
    Args:
        text: 输入文本
        
    Returns:
        调整空格后的文本
        
    Example:
        >>> adjust_space("这是hello世界")
        "这是 hello 世界"
    """
    return _EN_IN_ZH_PATTERN.sub(_replacer, text)