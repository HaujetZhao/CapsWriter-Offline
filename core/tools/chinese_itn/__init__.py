"""
中文数字转阿拉伯数字 (Chinese ITN - Inverse Text Normalization)

用法：
    from chinese_itn import chinese_to_num
    res = chinese_to_num('幺九二点幺六八点幺点幺')
"""

from .replacer import chinese_to_num

__all__ = ['chinese_to_num']
