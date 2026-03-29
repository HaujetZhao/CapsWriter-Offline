# coding: utf-8
'''
中文数字转阿拉伯数字 (Chinese ITN - Inverse Text Normalization)

用于把语音识别出的中文数字转为阿拉伯数字形式，
使用正则表达式进行匹配和替换。

用法示例：
    from chinese_itn import chinese_to_num
    
    res = chinese_to_num('幺九二点幺六八点幺点幺')  
    print(res)  # 192.168.1.1
    
    res = chinese_to_num('三五百人')
    print(res)  # 300~500人
'''

__all__ = ['chinese_to_num']

import re


# ============================================================
# 第一部分：配置和映射表
# ============================================================

# 单位映射：中文单位 -> 映射后的单位（None表示保留原样）
unit_mapping = {
    '个': None, '只': None, '分': None, '万': None, '亿': None, '秒': None, '年': None,
    '月': None, '日': None, '天': None, '时': None, '钟': None, '人': None, '层': None,
    '楼': None, '倍': None, '块': None, '次': None, 
    '克': 'g', '千克': 'kg', 
    '米': '米', '千米': '千米', '千米每小时': 'km/h',
}

# 生成单位正则（按长度从长到短排序，确保先匹配长的）
_sorted_units = sorted(unit_mapping.keys(), key=len, reverse=True)
common_units = '|'.join(f'{u}' for u in _sorted_units)

# 中文数字映射表
num_mapper = {
    '零': '0',  '一': '1',  '幺': '1',  '二': '2', 
    '两': '2',  '三': '3',  '四': '4',  '五': '5', 
    '六': '6',  '七': '7',  '八': '8',  '九': '9', 
    '点': '.', 
}

# 中文数字对数值的映射
value_mapper = {
    '零': 0,  '一': 1,  '二': 2,  '两': 2,  '三': 3,  '四': 4,  '五': 5, 
    '六': 6,  '七': 7,  '八': 8,  '九': 9,  "十": 10,  "百": 100,  "千": 1000,  "万": 10000,  "亿": 100000000,
}

# 成语和习语黑名单
idioms = '''
正经八百  五零二落 五零四散 
五十步笑百步 乌七八糟 污七八糟 四百四病 思绪万千 
十有八九 十之八九 三十而立 三十六策 三十六计 三十六行
三五成群 三百六十行 三六九等 
七老八十 七零八落 七零八碎 七七八八 乱七八遭 乱七八糟 略知一二 零零星星 零七八碎 
九九归一 二三其德 二三其意 无银三百两 八九不离十 
百分之百 年三十 烂七八糟 一点一滴 路易十六 九三学社 五四运动 入木三分 三十六计 
九九八十一 三七二十一  
十二五 十三五 十四五 十五五 十六五 十七五 十八五
'''.split()

# 模糊表达黑名单（包含"几"的表达不转换）
fuzzy_regex = re.compile(r'几')


# ============================================================
# 第二部分：范围表达式处理
# ============================================================

def _chinese_digit_to_num(char):
    """将单个中文数字转为阿拉伯数字"""
    return value_mapper.get(char, 0)

def _parse_tens(tens):
    """解析"十"或"X十"格式的数值"""
    return 10 if tens == '十' else _chinese_digit_to_num(tens[0]) * 10

# 范围表达式模式
_range_pattern_1 = re.compile(r'([二三四五六七八九])([二三四五六七八九])([十百千万亿])([万千百亿])?')
_range_pattern_2 = re.compile(r'(十|[一二三四五六七八九十]+[十百千万])([一二三四五六七八九])([一二三四五六七八九])([万千亿])?')
_range_pattern_3 = re.compile(r'^([一二三四五六七八九])([一二三四五六七八九])$')

def _convert_range_pattern_1(match):
    """转换模式1: 三五百 → 300~500, 五六十 → 50~60, 三四十万 → 30~40万"""
    groups = match.groups()
    d1, d2, unit = groups[0], groups[1], groups[2]
    suffix_unit = groups[3] if len(groups) > 3 and groups[3] else ''
    
    v1 = _chinese_digit_to_num(d1)
    v2 = _chinese_digit_to_num(d2)
    
    if unit == '十':
        v1, v2 = v1 * 10, v2 * 10
        return f"{v1}~{v2}{suffix_unit}"
    elif unit in ['万', '亿']:
        return f"{v1}~{v2}{unit}{suffix_unit}"
    elif unit == '千' and suffix_unit:
        return f"{v1}~{v2}{unit}{suffix_unit}"
    else:
        v1 = v1 * value_mapper[unit]
        v2 = v2 * value_mapper[unit]
        return f"{v1}~{v2}{suffix_unit}"

def _convert_range_pattern_2(match):
    """转换模式2: 十五六 → 15~16, 四十五六万 → 45~46万, 一百六七 → 160~170"""
    groups = match.groups()
    base_part, d1, d2 = groups[0], groups[1], groups[2]
    unit = groups[3] if len(groups) > 3 and groups[3] else ''

    last_char = base_part[-1]
    
    # 计算基数值
    if last_char == '十':
        base_value = 10 if len(base_part) == 1 else _chinese_digit_to_num(base_part[0]) * 10
    elif last_char in value_mapper:
        num_part = base_part[:-1]
        base_value = _chinese_digit_to_num(num_part[0]) * value_mapper[last_char] if num_part else value_mapper[last_char]
    else:
        base_value = _parse_tens(base_part)

    num1 = _chinese_digit_to_num(d1)
    num2 = _chinese_digit_to_num(d2)
    multiplier = value_mapper.get(last_char, 10) // 10

    return f"{base_value + num1 * multiplier}~{base_value + num2 * multiplier}{unit}"

def _convert_range_pattern_3(match):
    """转换模式3: 三四 → 3~4, 五六 → 5~6"""
    d1, d2 = match.groups()
    v1 = _chinese_digit_to_num(d1)
    v2 = _chinese_digit_to_num(d2)
    return f"{v1}~{v2}"

def is_range_expression(text):
    """判断是否为范围表达式"""
    sorted_units = sorted(unit_mapping.keys(), key=len, reverse=True)
    unit_pattern = '|'.join(re.escape(u) for u in sorted_units)
    optional_unit = rf'(?:{unit_pattern})?'
    
    range_pattern = re.compile(rf'''(?x)
        (?<!点)
        (?:
            [二三四五六七八九]{{2}}(?:十|[百千万亿]){optional_unit}
            |
            [一二三四五六七八九]?十[一二三四五六七八九]{{2}}(?:[万千亿]|{optional_unit})
            |
            [一二三四五六七八九][百千][二三四五六七八九]{{2}}十
            |
            [一二三四五六七八九十]+[万千百][一二三四五六七八九]{{2}}{optional_unit}
        )
    ''')
    
    return range_pattern.search(text) is not None

def convert_range_expression(text):
    """转换范围表达式"""
    # 剥离单位（复用主文件的 strip_unit 函数）
    stripped_text = text
    mapped_unit = ''
    
    numeric_units = {'万', '亿', '千', '百', '十'}
    sorted_units = sorted(unit_mapping.keys(), key=len, reverse=True)
    
    for unit_cn in sorted_units:
        if unit_cn in numeric_units:
            continue
        if text.endswith(unit_cn):
            stripped_text = text[:-len(unit_cn)]
            mapped_unit = unit_mapping[unit_cn]
            if mapped_unit is None:
                mapped_unit = unit_cn
            break
    
    # 匹配范围表达式模式
    match = _range_pattern_2.search(stripped_text)
    if match:
        return _convert_range_pattern_2(match) + mapped_unit

    match = _range_pattern_1.search(stripped_text)
    if match:
        return _convert_range_pattern_1(match) + mapped_unit

    match = _range_pattern_3.search(stripped_text)
    if match:
        return _convert_range_pattern_3(match) + mapped_unit

    return text


# ============================================================
# 第三部分：正则表达式模式定义
# ============================================================

# 用于去除末尾单位的正则
_unit_suffix_pattern = re.compile(rf'({common_units}|[a-zA-Z]+)$')

# 总模式，筛选出可能需要替换的内容
pattern = re.compile(rf"""(?ix)
([a-z]\s*)?
(
  (
    [几零幺一二两三四五六七八九十百千万点比]
    |[零一二三四五六七八九十][ ]
    |(?<=[一二两三四五六七八九十])[年月日号分]
    |(分之)
  )+
  (
    (?<=[一二两三四五六七八九十])([a-zA-Z年月日号]|{common_units})
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

# 纯数字序号
pure_num = re.compile(f'[零幺一二三四五六七八九]+(点[零幺一二三四五六七八九]+)* *([a-zA-Z]|{common_units})?')

# 数值
value_num = re.compile(f"十?(零?[一二两三四五六七八九十][十百千万]{{1,2}})*零?十?[一二三四五六七八九]?(点[零一二三四五六七八九]+)? *([a-zA-Z]|{common_units})?")

# 连续数值检测
consecutive_tens = re.compile(rf'^((?:十[一二三四五六七八九])+)({common_units})?$')
consecutive_hundreds = re.compile(rf'^((?:[一二三四五六七八九]百零?[一二三四五六七八九])+)({common_units})?$')

# 百分值
percent_value = re.compile('(?<![一二三四五六七八九])(百分之)[零一二三四五六七八九十百千万]+(点)?(?(2)[零一二三四五六七八九]+)')

# 分数
fraction_value = re.compile('([零一二三四五六七八九十百千万]+(点)?(?(2)[零一二三四五六七八九]+))分之([零一二三四五六七八九十百千万]+(点)?(?(4)[零一二三四五六七八九]+))')

# 比值
ratio_value = re.compile('([零一二三四五六七八九十百千万]+(点)?(?(2)[零一二三四五六七八九]+))比([零一二三四五六七八九十百千万]+(点)?(?(4)[零一二三四五六七八九]+))')

# 时间
time_value = re.compile("[零一二两三四五六七八九十]+点([零一二三四五六七八九十]+分)([零一二三四五六七八九十]+秒)?")

# 日期
data_value = re.compile("([零一二三四五六七八九十]+年)?([一二三四五六七八九十]+月)?([一二三四五六七八九十]+[日号])?")


# ============================================================
# 第四部分：辅助函数
# ============================================================

def strip_trailing_unit(text):
    """用正则去除末尾的单位"""
    match = _unit_suffix_pattern.search(text)
    if match:
        return text[:match.start()]
    return text

def is_consecutive_value(text):
    """检测是否是连续数值结构"""
    return consecutive_tens.match(text) or consecutive_hundreds.match(text)

def split_consecutive_value(text):
    """分割连续数值为空格分隔的阿拉伯数字"""
    unit = ''
    for c in common_units:
        if text.endswith(c):
            unit = c
            text = text[:-1]
            break
    
    if consecutive_tens.match(text + unit):
        parts = re.findall(r'十[一二三四五六七八九]', text)
        nums = [convert_value_num(p) for p in parts]
        return ' '.join(nums) + unit
    
    if consecutive_hundreds.match(text + unit):
        parts = re.findall(r'[一二三四五六七八九]百零?[一二三四五六七八九]', text)
        nums = [convert_value_num(p) for p in parts]
        return ' '.join(nums) + unit
    
    return text + unit

def strip_unit(original):
    """把数字后面跟着的单位剥离开，并应用单位映射"""
    unit_pattern = re.compile(rf'({common_units})$')
    match = unit_pattern.search(original)
    
    if match:
        unit_cn = match.group(1)
        stripped = original[:match.start()]
        mapped_unit = unit_mapping.get(unit_cn)
        unit = mapped_unit if mapped_unit is not None else unit_cn
    else:
        stripped = original
        unit = ''
    
    if not unit and stripped:
        letter_match = re.search(r'[a-zA-Z]+$', stripped)
        if letter_match:
            unit = letter_match.group()
            stripped = stripped[:letter_match.start()]
    
    return stripped.strip(), unit


# ============================================================
# 第五部分：转换函数
# ============================================================

def convert_pure_num(original, strict=False):
    """把中文数字转为对应的阿拉伯数字"""
    stripped, unit = strip_unit(original)
    if stripped in ['一'] and not strict:
        return original
    converted = [num_mapper[c] for c in stripped]
    return ''.join(converted) + unit

def convert_value_num(original):
    """把中文数值转为阿拉伯数字"""
    stripped, unit = strip_unit(original)
    if '点' not in stripped: 
        stripped += '点'
    int_part, decimal_part = stripped.split("点")
    if not int_part: 
        return original

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
    value += temp * base
    final = str(value)
    
    # 小数部分
    decimal_str = convert_pure_num(decimal_part, strict=True)
    if decimal_str: 
        final += '.' + decimal_str
    final += unit
    
    return final

def convert_fraction_value(original):
    """转换分数"""
    denominator, numerator = original.split('分之')
    return convert_value_num(numerator) + '/' + convert_value_num(denominator)

def convert_percent_value(original):
    """转换百分数"""
    return convert_value_num(original[3:]) + '%'

def convert_ratio_value(original):
    """转换比值"""
    num1, num2 = original.split("比")
    return convert_value_num(num1) + ':' + convert_value_num(num2)

def convert_time_value(original):
    """转换时间"""
    res = [x for x in re.split('[点分秒]', original) if x]
    final = ''
    hour = convert_value_num(res[0])
    final += hour.zfill(2)
    minute = convert_value_num(res[1])
    final += ':' + minute.zfill(2)
    if len(res) > 2: 
        second = convert_value_num(res[2])
        final += ':' + second.zfill(2)
    if len(res) > 3: 
        final += '.' + convert_pure_num(res[3])
    return final

def convert_date_value(original):
    """转换日期"""
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


# ============================================================
# 第六部分：主替换逻辑
# ============================================================

def replace(original):
    """主替换函数"""
    string = original.string
    l_pos, r_pos = original.regs[2]
    l_pos = max(l_pos-2, 0)
    head = original.group(1)
    original_text = original.group(2)
    original = original_text
    
    DEBUG = False
    
    try:
        # 成语/习语检测
        if idioms and any([string.find(idiom) in range(l_pos, r_pos) for idiom in idioms]):
            num_type = '成语/习语'
            final = original

        # 模糊表达检测
        elif fuzzy_regex.search(original):
            num_type = '模糊表达'
            final = original

        # 范围表达式
        elif is_range_expression(original):
            num_type = '范围表达式'
            final = convert_range_expression(original)

        # 时间
        elif time_value.fullmatch(original):
            num_type = '时间'
            final = convert_time_value(original)

        # 纯数字
        elif pure_num.fullmatch(strip_trailing_unit(original)):
            num_type = '纯数字'
            final = convert_pure_num(original)

        # 连续数值
        elif is_consecutive_value(original):
            num_type = '连续数值'
            final = split_consecutive_value(original)

        # 数值
        elif value_num.fullmatch(strip_trailing_unit(original)):
            num_type = '数值'
            final = convert_value_num(original)

        # 百分数
        elif percent_value.fullmatch(original):
            num_type = '百分之数值'
            final = convert_percent_value(original)

        # 分数
        elif fraction_value.fullmatch(original):
            num_type = '分数'
            final = convert_fraction_value(original)

        # 比值
        elif ratio_value.fullmatch(original):
            num_type = '比值'
            final = convert_ratio_value(original)

        # 日期
        elif data_value.fullmatch(original):
            num_type = '日期'
            final = convert_date_value(original)

        else:
            num_type = '未匹配'
            final = original

        # print(f'{num_type}：{original}')

        if head:
            final = head + final
        
        if DEBUG and original_text != final:
            print(f"[{num_type}] {original_text} → {final}")
            
    except Exception as e:
        num_type = '错误'
        final = original
        if DEBUG:
            print(f"[错误] {original_text}: {e}")
    
    return final


# ============================================================
# 第七部分：主函数
# ============================================================


def chinese_to_num(original):
    """主函数：将中文数字转换为阿拉伯数字"""
    # print(f'\n\n原始文本：{original}')
    result = pattern.sub(replace, original)
    return result


# ============================================================
# 测试代码
# ============================================================

if __name__ == "__main__":
    print(chinese_to_num('二零二五年十月'))
