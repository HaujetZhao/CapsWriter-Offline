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



# 常见的跟在数字后面的单位
common_units = '个只分万秒'       

# 总模式，筛选出可能需要替换的内容
pattern = re.compile(f"""(?ix)          # i 表示忽略大小写，x 表示开启注释模式
    (
        (
            [零幺一二两三四五六七八九十百千万亿点比]
            |(分之)
            |(?<=[一二两三四五六七八九十])[年月日号{common_units}]
        ){{2,}}
    )
""")

# 细分匹配不同的数字类型

# 纯数字序号
pure_num = re.compile(f'[零幺一二三四五六七八九]+(点[零幺一二三四五六七八九]+)*[{common_units}]?')

# 数值
value_num = re.compile(f"十?(零?[一二两三四五六七八九十][十百千万]{{1,2}})*零?[一二三四五六七八九]?(点[零一二三四五六七八九]+)?[{common_units}]?")

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
    stripped = original.strip(common_units)
    if stripped != original: 
        unit = original[len(stripped):]
    return stripped, unit

def convert_pure_num(original):
    '''把中文数字转为对应的阿拉伯数字'''
    stripped, unit = strip_unit(original)
    if stripped in ['一']:
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

    # 计算整数部分的值
    value, temp = 0, 0
    for c in int_part:
        if c == '十' : 
            temp = 10 if temp==0 else value_mapper[c]*temp
        elif c in '一二两三四五六七八九':
            temp += value_mapper[c]
        elif c in '万':
            value += temp 
            value *= value_mapper[c]
            temp = 0
        elif c in '百千':
            value += temp * value_mapper[c]
            temp = 0
    value += temp; 
    final = str(value)
    
    # 小数部分，就是纯数字，直接映射即可
    decimal_str = convert_pure_num(decimal_part)
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
    original = original.group()
    try:
        if pure_num.fullmatch(original.strip('个只分万')):
            num_type = '纯数字'
            final = convert_pure_num(original)
        elif value_num.fullmatch(original.strip('个只分万')):
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
    except:
        num_type = '未知'
        final = original
    return final


def chinese_to_num(original):
    return pattern.sub(replace, original)

if __name__ == "__main__":

    # groups = []
    # with open('./测试集.txt', 'r', encoding="utf-8", newline='') as f:
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
    print(chinese_to_num('一个'))
