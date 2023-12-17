format_spell    = True      # 输出时是否调整中英之间的空格

import re
from string import digits, ascii_letters

# ========================================================================

en_in_zh = re.compile(r"""(?ix)    # i 表示忽略大小写，x 表示开启注释模式
    ([\u4e00-\u9fa5]|[a-z0-9]+\s)?      # 左侧是中文，或者英文加空格
    ([a-z0-9 ]+)                    # 中间是一个或多个「英文数字加空格」
    ([\u4e00-\u9fa5]|[a-z0-9]+)?       # 右是中文，或者英文加空格
""")

def adjust_space(original: re.Match):
    left : str = original.group(1)
    center : str = original.group(2)
    right : str = original.group(3)
    # 如果拼写字母中间有空格，就把空格都去掉
    if center:
        final = re.sub(r'((\d) )?(\b\w) ?(?!\w{2})', r'\2\3', center).strip()
        # 测试地址 https://regex101.com/r/1Vtu7V/1
        # final = re.sub(r'(\b\w) (?!\w{2})', r'\1', original.group(2)).strip()
    
    # 如果英文的左边有汉字或英文，给两组之间加上空格
    if left :
        if left.strip(digits) == left and center.lstrip(digits) == center :  # 左侧结尾不是数字，中间开头不是数字
            final = ' ' + final
        final = left.rstrip() + final
    
    # 如果英文左边的汉字被前一个组消费了，就要手动去看一下前一个字是不是中文
    elif re.match(r'[\u4e00-\u9fa5]', original.string[original.start(2) - 1]): 
        if center.lstrip(digits) == center:     # 确保中间开头不是数字
            final = ' ' + final
        
    # 如果英文的右边有汉字，给中英之间加上空格
    if right:
        if center.rstrip(digits) == center:     # 确保中间结尾不是数字
            final += ' '
        final += right.lstrip()

    return final