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
    ([\u4e00-\u9fa5]|[a-z0-9]+\s)?      # 左侧：中文，或英文加空格
    ([a-z0-9 ]+)                        # 中间：一个或多个「英文数字加空格」
    ([\u4e00-\u9fa5]|[a-z0-9]+)?        # 右侧：中文，或英文加空格
""")


def _replacer(match: Match) -> str:
    """
    替换匹配的中英混排文本，调整空格
    
    Args:
        match: 正则匹配对象
        
    Returns:
        调整空格后的文本
    """
    left: str = match.group(1) or ''
    center: str = match.group(2) or ''
    right: str = match.group(3) or ''
    
    # 如果拼写字母中间有空格，就把空格都去掉
    if center:
        final = re.sub(r'((\d) )?(\b\w) ?(?!\w{2})', r'\2\3', center).strip()
    else:
        final = ''
    
    # 如果英文的左边有汉字或英文，给两组之间加上空格
    if left:
        # 左侧结尾不是数字，中间开头不是数字
        if left.strip('0123456789') == left and center.lstrip('0123456789') == center:
            final = ' ' + final
        final = left.rstrip() + final
    
    # 如果英文左边的汉字被前一个组消费了，需要手动检查
    elif match.start(2) > 0 and re.match(r'[\u4e00-\u9fa5]', match.string[match.start(2) - 1]):
        if center.lstrip('0123456789') == center:  # 确保中间开头不是数字
            final = ' ' + final
        
    # 如果英文的右边有汉字，给中英之间加上空格
    if right:
        if center.rstrip('0123456789') == center:  # 确保中间结尾不是数字
            final += ' '
        final += right.lstrip()

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