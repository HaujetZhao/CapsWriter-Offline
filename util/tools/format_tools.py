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
    
    # 1. 如果拼写字母中间有空格，就把空格都去掉 (如 "H E L L O" -> "HELLO")
    if center:
        # 这个正则处理 "A B C" 类型的情况，保留数字后面的空格如果是为了切分
        final = re.sub(r'((\d) )?(\b\w) ?(?!\w{2})', r'\2\3', center).strip()
    else:
        final = ''
    
    # 2. 判断该序列是否包含英文字母
    # 如果包含英文字母，则视为“英文序列”，需要与中文保持空格
    # 如果是纯数字，按用户要求，不加空格
    has_alpha = bool(re.search(r'[a-zA-Z]', final))
    
    # 3. 处理左侧边界
    if left:
        # 如果左侧是中文，且中间包含英文，补空格
        if has_alpha and re.match(r'[\u4e00-\u9fa5]', left.strip()):
            final = ' ' + final
        final = left.rstrip() + final
    elif match.start(2) > 0:
        # 处理被前一个匹配块消费掉的边界情况
        prev_char = match.string[match.start(2) - 1]
        if has_alpha and re.match(r'[\u4e00-\u9fa5]', prev_char):
            final = ' ' + final
        
    # 4. 处理右侧边界
    if right:
        # 如果右侧是中文，且中间包含英文，补空格
        if has_alpha and re.match(r'[\u4e00-\u9fa5]', right.strip()):
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