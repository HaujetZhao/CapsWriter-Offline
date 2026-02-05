# coding: utf-8
"""
文本格式化工具

提供中英文混排文本的空格调整功能。
主要用于调整识别结果中中英文之间的空格。
"""

import re
from typing import Match

# 匹配中文字符包围的英文/数字/符号序列
_EN_IN_ZH_PATTERN = re.compile(r"""(?ix)
    ([\u4e00-\u9fa5])?                  # 左侧：中文
    (                                   # 中间：英文数字及常用技术符号序列
        [a-z0-9+#]                      # 起头：字母、数字、+、#
        [a-z0-9\s'.,!+#/_:@%&?-]*       # 中间：允许空格和更多符号 (将 - 移至末尾)
        [a-z0-9+#%]                     # 结尾：字母、数字、+、#、%
        |
        [a-z0-9]                        # 或者：单个字母或数字
    )
    ([\u4e00-\u9fa5])?                  # 右侧：中文
""")


def _replacer(match: Match) -> str:
    """
    替换匹配的中英混排文本，调整空格
    """
    left: str = match.group(1) or ''
    center: str = match.group(2) or ''
    right: str = match.group(3) or ''
    
    # 1. 预处理：去除前后空格
    final = center.strip()
    
    # 2. 合并拼读序列（如 "F P 32" -> "FP32", "C O M F Y" -> "COMFY"）
    # 规则：如果拆分后每一部分都是单字符 OR 纯数字，则合并
    parts = final.split()
    if len(parts) > 1 and all(len(p) == 1 or p.isdigit() for p in parts):
        final = "".join(parts)
    
    # 3. 判断是否包含英文字母，决定是否加空格（仅纯数字不加空格）
    has_alpha = bool(re.search(r'[a-zA-Z]', final))
    
    # 处理左侧：中文 + 英文/英数 -> 中文 + 空格 + 英文/英数
    if left and has_alpha:
        final = left + ' ' + final
    else:
        final = left + final
        
    # 处理右侧：英文/英数 + 中文 -> 英文/英数 + 空格 + 中文
    if right and has_alpha:
        final = final + ' ' + right
    else:
        final = final + right

    return final



def adjust_space(text: str) -> str:
    """
    调整中英文/数字之间的空格
    
    1. 在中文和英文、数字之间插入空格。
    2. 将连续的单个英文字母（如 "A B C"）合并为 "ABC"。
    3. 支持常用技术符号如 C++, TCP/IP, 100%。
    
    Args:
        text: 输入文本
        
    Returns:
        优化后的文本
    """
    return _EN_IN_ZH_PATTERN.sub(_replacer, text)


if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "这是hello世界",
        "hello世界",
        "这是hello",
        "这是   hello   ",
        "这是一个iPhone手机",
        "这是一个iPhone15手机",
        "尝试一下 C O M F Y U I",
        "尝试一下 C O M F Y U I怎么样",
        "你可以试一下 F P 32 和 F P 16 如何",
        "I have a phone",
        "C++是非常强的语言",
        "数字123也会测试",
        "Mixed中文English测试",
        "TCP/IP协议",
        "100%的安全",
        "C# 也是一门语言",
    ]

    print(f"{'Original Text':<25} | {'Adjusted Text'}")
    print("-" * 60)
    for text in test_cases:
        print(f"{text:<25} | {adjust_space(text)}")

