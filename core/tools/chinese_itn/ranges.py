"""
范围表达式处理

将 "三五百→300~500", "十五六→15~16", "三四→3~4" 等范围表达转为波浪线格式。
"""

from .mappings import value_mapper, unit_mapping
from .sequence_parser import tokenize, parse_tokens


def _strip_physical_unit(text):
    """剥离物理单位 (如人, 米, 克等)"""
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
    return stripped_text, mapped_unit


def parse_range(text):
    """
    解析范围表达式的核心函数。
    如果解析成功，返回转换后的波浪线字符串 (如 300~500, 15~16)；
    如果解析失败，返回 None。
    """
    # 范围表达式中不应该包含小数点
    if '点' in text:
        return None

    # 1. 剥离尾部物理单位
    stripped_text, mapped_unit = _strip_physical_unit(text)
    if not stripped_text:
        return None

    # 2. 词法分析与安全防卫
    tokens = tokenize(stripped_text)
    if not tokens:
        return None
    
    # 剥离单位后的核心文本必须纯净，只能含有基础数字 Token，绝不能掺杂百分之、分之、比或其它 OTHER 字符
    _ALLOWED_RANGE_TYPES = {'DIGIT', 'TEN', 'HUNDRED', 'THOUSAND', 'TEN_THOUSAND', 'HUNDRED_MILLION', 'ZERO'}
    if not all(t.type in _ALLOWED_RANGE_TYPES for t in tokens):
        return None

    # 3. 寻找所有的 DIGIT 连续片段
    runs = []
    current_run = []
    start_idx = -1
    for idx, token in enumerate(tokens):
        if token.type == 'DIGIT':
            if not current_run:
                start_idx = idx
            current_run.append(token)
        else:
            if current_run:
                runs.append((start_idx, idx, current_run))
                current_run = []
    if current_run:
        runs.append((start_idx, len(tokens), current_run))

    # 4. 范围核心的强约束过滤
    #    - 必须有且仅有一个长度为 2 的 DIGIT run (即范围核心 d1, d2)
    #    - 不能有长度大于 2 的 DIGIT run (防止把 五六七八九 误判)
    len2_runs = [run for run in runs if len(run[2]) == 2]
    large_runs = [run for run in runs if len(run[2]) > 2]
    
    if len(len2_runs) != 1 or len(large_runs) > 0:
        return None

    # 提取范围核心
    core_start_idx, core_end_idx, core_tokens = len2_runs[0]
    d1, d2 = core_tokens[0], core_tokens[1]
    v1, v2 = d1.value, d2.value

    # 验证核心的递增和差值关系 (v1 < v2 且 差值为 1，或 v1=3, v2=5)
    if not (v1 < v2 and (v2 - v1 == 1 or (v1 == 3 and v2 == 5))):
        return None

    # 切分 Token 序列为 Base, Core, Suffix
    base_tokens = tokens[:core_start_idx]
    suffix_tokens = tokens[core_end_idx:]

    # 5. 执行具体的转换分支
    if not base_tokens:
        # Case A: 基数为空 (Pattern 1 & Pattern 3)
        if not suffix_tokens:
            # Pattern 3: 三四 -> 3~4
            return f"{v1}~{v2}{mapped_unit}"
        else:
            # Pattern 1: 三五百 -> 300~500, 三四十万 -> 30~40万
            # 第一个后缀必须是单位
            unit_token = suffix_tokens[0]
            if unit_token.type not in ('TEN', 'HUNDRED', 'THOUSAND', 'TEN_THOUSAND', 'HUNDRED_MILLION'):
                return None
            
            # 后续后缀必须是 万 或 亿
            suffix_unit_tokens = suffix_tokens[1:]
            if not all(t.type in ('TEN_THOUSAND', 'HUNDRED_MILLION') for t in suffix_unit_tokens):
                return None
            
            unit = unit_token.char
            suffix_unit = "".join(t.char for t in suffix_unit_tokens)

            if unit == '十':
                return f"{v1 * 10}~{v2 * 10}{suffix_unit}{mapped_unit}"
            elif unit in ('万', '亿'):
                return f"{v1}~{v2}{unit}{suffix_unit}{mapped_unit}"
            elif unit == '千' and suffix_unit:
                return f"{v1}~{v2}{unit}{suffix_unit}{mapped_unit}"
            else:
                mult = unit_token.value
                return f"{v1 * mult}~{v2 * mult}{suffix_unit}{mapped_unit}"
    else:
        # Case B: 基数不为空 (Pattern 2: 十五六 -> 15~16, 一百二三十 -> 120~130)
        base_str = "".join(t.char for t in base_tokens)
        
        # 尝试使用 parse_tokens 解析 base_tokens 得到 base_value
        try:
            base_vals = parse_tokens(base_tokens)
            if not base_vals or len(base_vals) != 1:
                return None
            base_value = int(base_vals[0])
        except Exception:
            return None

        # 后缀解析
        if suffix_tokens and suffix_tokens[0].type == 'TEN':
            # 类似 一百二三十 -> suffix_tokens 是 [十]
            # 或者是 一百二三十万 -> suffix_tokens 是 [十, 万]
            suffix_unit_tokens = suffix_tokens[1:]
            if not all(t.type in ('TEN_THOUSAND', 'HUNDRED_MILLION') for t in suffix_unit_tokens):
                return None
            
            multiplier = 10
            suffix_str = "".join(t.char for t in suffix_unit_tokens)
        else:
            # 类似 十五六 -> suffix_tokens 是 []
            # 或者是 四十五六万 -> suffix_tokens 是 [万]
            if not all(t.type in ('TEN_THOUSAND', 'HUNDRED_MILLION') for t in suffix_tokens):
                return None
            
            last_char = base_str[-1]
            if last_char not in value_mapper:
                return None
            multiplier = value_mapper.get(last_char, 10) // 10
            suffix_str = "".join(t.char for t in suffix_tokens)

        val1 = base_value + v1 * multiplier
        val2 = base_value + v2 * multiplier
        return f"{val1}~{val2}{suffix_str}{mapped_unit}"


def is_range_expression(text):
    """判断是否为范围表达式"""
    return parse_range(text) is not None


def convert_range_expression(text):
    """转换范围表达式"""
    res = parse_range(text)
    return res if res is not None else text
