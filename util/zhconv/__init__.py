# coding: utf-8
"""
中文简繁转换模块

基于 MediaWiki 的转换表实现简繁转换。
原库 zhconv 使用了废弃的 pkg_resources，此版本已修复。

使用方法：
    from util.zhconv import convert
    print(convert('我干什么不干你事。', 'zh-tw'))
    # 输出: 我幹什麼不幹你事。
"""

from .zhconv import convert, convert_for_mw, issimp, tokenize, loaddict

__all__ = ['convert', 'convert_for_mw', 'issimp', 'tokenize', 'loaddict']
