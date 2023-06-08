# coding: utf-8
'''
用于把语音识别出的中文数字转为阿拉伯数字形式，
使用正则表达式进行匹配和替换，
可能不是那么精准，但足够应付大部分情景了。

用法示例：

from chinese_itn import chinese_to_num

res = chinese_to_num('幺九二点幺六八点幺点幺')  
print(res)  # 192.168.1.1

'''

__all__ = ['chinese_to_num']

import re
from string import ascii_letters


# 常见的跟在数字后面的单位
common_units = r'个只分万亿秒'       

# 以空格分隔开的常用语，如成语、日常短语，用于避免误转
idioms = '''
正经八百  五零二落 五零四散 
五十步笑百步 乌七八糟 污七八糟 四百四病 思绪万千 
十有八九 十之八九 三十而立 三十六策 三十六计 三十六行
三五成群 三百六十行 三六九等 
七老八十 七零八落 七零八碎 七七八八 乱七八遭 乱七八糟 略知一二 零零星星 零七八碎 
九九归一 二三其德 二三其意 无银三百两 八九不离十 
百分之百 年三十 烂七八糟 一点一滴 路易十六 九三学社 五四运动 入木三分 三十六计 
'''

idioms = [x.strip() for x in idioms.split() ]

# 总模式，筛选出可能需要替换的内容
# 测试链接  https://regex101.com/r/tFqg9S/3
pattern = re.compile(f"""(?ix)          # i 表示忽略大小写，x 表示开启注释模式
([a-z]\s*)?
(
  (
    [零幺一二两三四五六七八九十百千万点比]
    |[零一二三四五六七八九十][ ]
    |(?<=[一二两三四五六七八九十])[年月日号分]
    |(分之)
  )+
  (
    (?<=[一二两三四五六七八九十])[a-zA-Z年月日号{common_units}]
    |(?<=[一二两三四五六七八九十]\s)[a-zA-Z]
  )?
  (?(1)
  |(?(5)
    |(
      [零幺一二两三四五六七八九十百千万亿点比]
      |(分之)
    )
  )+
  )
)

""")


# 细分匹配不同的数字类型

# 纯数字序号
pure_num = re.compile(f'[零幺一二三四五六七八九]+(点[零幺一二三四五六七八九]+)* *[a-zA-Z{common_units}]?')

# 数值
value_num = re.compile(f"十?(零?[一二两三四五六七八九十][十百千万]{{1,2}})*零?[一二三四五六七八九]?(点[零一二三四五六七八九]+)? *[a-zA-Z{common_units}]?")

# 百分值
percent_value = re.compile('(?<![一二三四五六七八九])(百分之)[零一二三四五六七八九十百千万]+(点)?(?(2)[零一二三四五六七八九]+)')

# 分数
fraction_value = re.compile('([零一二三四五六七八九十百千万]+(点)?(?(2)[零一二三四五六七八九]+))分之([零一二三四五六七八九十百千万]+(点)?(?(4)[零一二三四五六七八九]+))')

# 比值
ratio_value = re.compile('([零一二三四五六七八九十百千万]+(点)?(?(2)[零一二三四五六七八九]+))比([零一二三四五六七八九十百千万]+(点)?(?(4)[零一二三四五六七八九]+))')

# 时间
time_value = re.compile("[零一二三四五六七八九十]+点([零一二三四五六七八九十]+分)([零一二三四五六七八九十]+秒)?")

# 日期
data_value = re.compile("([零一二三四五六七八九]+年)?([一二三四五六七八九十]+月)([一二三四五六七八九十]+[日号])")

# 中文数字对阿拉伯数字的映射
num_mapper = {
    '零': '0', 
    '一': '1', 
    '幺': '1', 
    '二': '2', 
    '两': '2', 
    '三': '3', 
    '四': '4', 
    '五': '5', 
    '六': '6', 
    '七': '7', 
    '八': '8', 
    '九': '9', 
    '点': '.', 
}

# 中文数字对数值的映射
value_mapper = {
    '零': 0, 
    '一': 1, 
    '二': 2, 
    '两': 2, 
    '三': 3, 
    '四': 4, 
    '五': 5, 
    '六': 6, 
    '七': 7, 
    '八': 8, 
    '九': 9, 
    "十": 10,
    "百": 100,
    "千": 1000,
    "万": 10000,
}


def strip_unit(original):
    '''把数字后面跟着的单位剥离开'''
    unit = ''       
    stripped = original.strip(common_units + ascii_letters).strip()
    if stripped != original: 
        unit = original[len(stripped):]
    return stripped, unit

def convert_pure_num(original, strict=False):
    '''把中文数字转为对应的阿拉伯数字'''
    stripped, unit = strip_unit(original)
    if stripped in ['一'] and not strict:
        return original
    converted = []
    for c in stripped:
        converted.append(num_mapper[c])
    final = ''.join(converted) + unit
    return final

def convert_value_num(original):
    '''把中文数值转为阿拉伯数字'''
    stripped, unit = strip_unit(original)   # 剥除单位
    if '点' not in stripped: stripped += '点'
    int_part, decimal_part = stripped.split("点")   # 分离小数
    if not int_part: return original        # 如果没有整数部分，表面匹配到的是「点一」这样的形式，应当不处理

    # 计算整数部分的值
    value, temp, base = 0, 0, 1
    for c in int_part:
        if c == '十' : 
            temp = 10 if temp==0 else value_mapper[c]*temp
            base = 1
        elif c == '零':
            base = 1
        elif c in '一二两三四五六七八九':
            temp += value_mapper[c]
        elif c in '万':
            value += temp 
            value *= value_mapper[c]
            base = value_mapper[c] // 10
            temp = 0
        elif c in '百千':
            value += temp * value_mapper[c]
            base = value_mapper[c] // 10
            temp = 0
    value += temp * base; 
    final = str(value)
    
    # 小数部分，就是纯数字，直接映射即可
    decimal_str = convert_pure_num(decimal_part, strict=True)
    if decimal_str: final += '.' + decimal_str
    final += unit
    
    return final

def convert_fraction_value(original):
    denominator, numerator = original.split('分之')
    final = convert_value_num(numerator) + '/' + convert_value_num(denominator)
    return final

def convert_percent_value(original):
    final = convert_value_num(original[3:]) + '%'
    return final

def convert_ratio_value(original):
    num1, num2 = original.split("比")
    final = convert_value_num(num1) + ':' + convert_value_num(num2)
    return final

def convert_time_value(original):
    res = [x for x in re.split('[点分秒]', original) if x]
    final = ''
    final += convert_value_num(res[0])
    final += ':' + convert_value_num(res[1])
    if len(res) > 2: 
        final += ':' + convert_value_num(res[2])
    if len(res) > 3: 
        final += '.' + convert_pure_num(res[3])
    return final
    ...

def convert_date_value(original):
    final = ''
    if '年' in original:
        year, original = original.split('年')
        final += convert_pure_num(year) + '年'
    if '月' in original:
        month, original = original.split('月')
        final += convert_value_num(month) + '月'
    if '日' in original:
        day, original = original.split('日')
        final += convert_value_num(day) + '日'
    elif '号' in original:
        day, original = original.split('号')
        final += convert_value_num(day) + '号'
    return final
    ...


def replace(original):
    string = original.string
    l_pos, r_pos = original.regs[2]; l_pos = max(l_pos-2, 0)
    head = original.group(1)
    original = original.group(2)
    try:
        if idioms and any([string.find(idiom) in range(l_pos, r_pos) for idiom in idioms]):
            final = original
        elif pure_num.fullmatch(original.strip(common_units)):
            num_type = '纯数字'
            final = convert_pure_num(original)
        elif value_num.fullmatch(original.strip(common_units)):
            num_type = '数值'
            final = convert_value_num(original)
        elif percent_value.fullmatch(original):
            num_type = '百分之数值'
            final = convert_percent_value(original)
        elif fraction_value.fullmatch(original):
            num_type = '分数'
            final = convert_fraction_value(original)
        elif ratio_value.fullmatch(original):
            num_type = '比值'
            final = convert_ratio_value(original)
        elif time_value.fullmatch(original):
            num_type = '时间'
            final = convert_time_value(original)
        elif data_value.fullmatch(original):
            num_type = '日期'
            final = convert_date_value(original)
        else:
            final = original

        if head:
            final = head + final
    except:
        num_type = '未知'
        final = original
    return final


def chinese_to_num(original):
    return pattern.sub(replace, original)

if __name__ == "__main__":

    # groups = []
    # with open('./old/测试集.txt', 'r', encoding="utf-8", newline='') as f:
    #     lines = f.readlines()
    #     for i in range(0, len(lines), 5):
    #         original = lines[i].split(maxsplit=2)[1]
    #         reult = lines[i+1].split(maxsplit=2)[1]
    #         groups.append([original, reult])

    # for g in groups:
    #     original = g[0]
    #     reference = g[1]
    #     answer = chinese_to_num(original)
    #     print(f'\n{original=}')
    #     print(f'{reference=}') 
    #     print(f'{answer=   }') 

    # file = './old/汉语词语.txt'
    # with open(file, 'r', encoding='utf-8') as f:
    #     words = f.readlines()

    # for word in words: 
    #     new = chinese_to_num(word)
    #     if re.match(r'.*\d.+', new):
    #         print(word, new)
    print(chinese_to_num('二零二五年十月'))
    print(chinese_to_num('乱七八糟'))

