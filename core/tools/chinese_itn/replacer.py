# coding: utf-8
"""
主替换逻辑和入口函数
"""

from .mappings import idioms, fuzzy_regex
from .patterns import pattern
from .utils import convert_pure_num, strip_unit
from .sequence_parser import parse_sequence, tokenize, parse_tokens, _BASIC_NUMERIC_TYPES
from .ranges import is_range_expression, convert_range_expression


# ============================================================
# 辅助工具
# ============================================================

def _all_numeric(tokens):
    """检查所有 Token 是否为基础数值类型"""
    return all(t.type in _BASIC_NUMERIC_TYPES for t in tokens)


def _reduce_binary_op(tokens, sep_type, fmt):
    """规约二元分隔表达式（分数、比值共用）"""
    indices = [i for i, t in enumerate(tokens) if t.type == sep_type]
    if len(indices) != 1:
        return None
    idx = indices[0]
    left, right = tokens[:idx], tokens[idx+1:]
    if not left or not right or not _all_numeric(left) or not _all_numeric(right):
        return None
    left_vals = parse_tokens(left)
    right_vals = parse_tokens(right)
    if left_vals and len(left_vals) == 1 and right_vals and len(right_vals) == 1:
        return fmt.format(left=left_vals[0], right=right_vals[0])
    return None


# ============================================================
# Token 规约子模块 (Grammar Reducers)
# ============================================================

def try_reduce_percent(tokens, original):
    """规约百分数和千分比：百分之三十 -> 30%"""
    if not tokens or tokens[0].type != 'PERCENT_PREFIX':
        return None
    val_tokens = tokens[1:]
    if not val_tokens or not _all_numeric(val_tokens):
        return None
    vals = parse_tokens(val_tokens)
    if vals is not None and len(vals) == 1:
        suffix = '%' if tokens[0].char == '百分之' else '‰'
        return f"{vals[0]}{suffix}"
    return None


def try_reduce_fraction(tokens, original):
    """规约分数：三分之二 -> 2/3"""
    return _reduce_binary_op(tokens, 'FRACTION_SEP', '{right}/{left}')


def try_reduce_ratio(tokens, original):
    """规约比值：一比三 -> 1:3"""
    return _reduce_binary_op(tokens, 'RATIO_SEP', '{left}:{right}')


def try_reduce_time(tokens, original):
    """规约时间：十二点三十分五秒 -> 12:30:05"""
    dot_indices = [idx for idx, t in enumerate(tokens) if t.type == 'DOT']
    min_indices = [idx for idx, t in enumerate(tokens) if t.type == 'MINUTE_SUF']
    if len(dot_indices) != 1 or len(min_indices) != 1:
        return None

    dot_idx, min_idx = dot_indices[0], min_indices[0]
    if dot_idx >= min_idx:
        return None

    hour_tokens = tokens[:dot_idx]
    minute_tokens = tokens[dot_idx+1:min_idx]
    second_tokens = tokens[min_idx+1:]

    if not hour_tokens or not minute_tokens or not _all_numeric(hour_tokens) or not _all_numeric(minute_tokens):
        return None

    # 秒处理
    has_second = False
    sec_str = ""
    if second_tokens:
        if second_tokens[-1].type != 'SECOND_SUF':
            return None
        sec_val_tokens = second_tokens[:-1]
        if not sec_val_tokens or not _all_numeric(sec_val_tokens):
            return None
        sec_vals = parse_tokens(sec_val_tokens)
        if not sec_vals or len(sec_vals) not in (1, 2):
            return None
        if len(sec_vals) == 2 and sec_vals[0] in (0, '0'):
            sec_vals = [sec_vals[1]]
        if len(sec_vals) != 1:
            return None

        val = sec_vals[0]
        if isinstance(val, float):
            int_part, dec_part = str(val).split('.')
            sec_str = f"{int_part.zfill(2)}.{dec_part}"
        else:
            sec_str = str(val).zfill(2)
        has_second = True

    hour_vals = parse_tokens(hour_tokens)
    min_vals = parse_tokens(minute_tokens)
    if min_vals and len(min_vals) == 2 and min_vals[0] in (0, '0'):
        min_vals = [min_vals[1]]
    if hour_vals and len(hour_vals) == 1 and min_vals and len(min_vals) == 1:
        h_str = str(hour_vals[0]).zfill(2)
        m_str = str(min_vals[0]).zfill(2)
        if has_second:
            return f"{h_str}:{m_str}:{sec_str}"
        return f"{h_str}:{m_str}"
    return None


def try_reduce_date(tokens, original):
    """规约日期：二零二五年十月三日 -> 2025年10月3日"""
    year_indices = [idx for idx, t in enumerate(tokens) if t.type == 'YEAR_SUF']
    month_indices = [idx for idx, t in enumerate(tokens) if t.type == 'MONTH_SUF']
    day_indices = [idx for idx, t in enumerate(tokens) if t.type == 'DAY_SUF']

    if len(year_indices) > 1 or len(month_indices) > 1 or len(day_indices) > 1:
        return None
    if not year_indices and not month_indices and not day_indices:
        return None

    y_idx = year_indices[0] if year_indices else -1
    m_idx = month_indices[0] if month_indices else -1
    d_idx = day_indices[0] if day_indices else -1

    # 严格的年月日单位顺序校验
    indices = [i for i in (y_idx, m_idx, d_idx) if i != -1]
    if indices != sorted(indices):
        return None

    def _parse_part(start, end):
        """解析 [start, end) 区间的 Token 为数值字符串"""
        part = tokens[start:end]
        if not part or not _all_numeric(part):
            return None
        vals = parse_tokens(part)
        if not vals or len(vals) != 1:
            return None
        return str(vals[0])

    last_idx = 0
    res_str = ""

    if y_idx != -1:
        y_tokens = tokens[last_idx:y_idx]
        if not y_tokens or not _all_numeric(y_tokens):
            return None
        if all(t.type in ('DIGIT', 'ZERO') for t in y_tokens):
            y_str = convert_pure_num("".join(t.char for t in y_tokens), strict=True)
        else:
            y_str = _parse_part(last_idx, y_idx)
            if y_str is None:
                return None
        res_str += y_str + "年"
        last_idx = y_idx + 1

    if m_idx != -1:
        m_str = _parse_part(last_idx, m_idx)
        if m_str is None:
            return None
        res_str += m_str + "月"
        last_idx = m_idx + 1

    if d_idx != -1:
        d_str = _parse_part(last_idx, d_idx)
        if d_str is None:
            return None
        res_str += d_str + tokens[d_idx].char
        last_idx = d_idx + 1

    if last_idx != len(tokens):
        return None
    return res_str


def try_reduce_date_time(tokens, original):
    """规约日期、时间以及它们的复合体"""
    idxs = [i for i, t in enumerate(tokens) if t.type in ('DAY_SUF', 'MONTH_SUF', 'YEAR_SUF')]
    split_idx = idxs[-1] if idxs else -1

    date_res = try_reduce_date(tokens[:split_idx+1], None) if split_idx != -1 else ""
    time_res = try_reduce_time(tokens[split_idx+1:], None) if split_idx + 1 < len(tokens) else ""

    return date_res + time_res if (date_res is not None and time_res is not None) else None


def try_reduce_numerical(tokens, original_text):
    """规约常规数值、数字序列以及纯数字"""
    stripped_text, unit = strip_unit(original_text)

    # 万/亿不作为物理后缀剥离
    if unit in ('万', '亿'):
        stripped_text = original_text

    if not stripped_text or stripped_text.endswith('点'):
        return None

    stripped_tokens = tokenize(stripped_text)
    if not stripped_tokens or not _all_numeric(stripped_tokens):
        return None

    # 纯数字解析 (不含十百千万亿的大数流)
    if all(t.type in ('DIGIT', 'ZERO', 'DOT') for t in stripped_tokens):
        return convert_pure_num(original_text)

    # 通用 parse_sequence 规约
    return parse_sequence(original_text)


def try_reduce_range(tokens, original):
    """规约范围表达式：十五到二十 -> 15-20"""
    return convert_range_expression(original) if is_range_expression(original) else None


# ============================================================
# 主替换入口 (Pipeline Entry)
# ============================================================

def replace(match):
    """主替换函数 (AST 规约入口)"""
    string = match.string
    l_pos, r_pos = match.regs[2]
    l_pos = max(l_pos - 2, 0)
    head = match.group(1)
    original = match.group(2)

    if idioms and any(
        string.find(idiom) in range(l_pos, r_pos) and len(original) <= len(idiom)
        for idiom in idioms
    ):
        final = original

    elif fuzzy_regex.search(original):
        final = original

    else:
        tokens = tokenize(original)

        for reducer in [
            try_reduce_percent,    # 百分比
            try_reduce_fraction,   # 分数
            try_reduce_ratio,      # 比值
            try_reduce_date_time,  # 日期时间
            try_reduce_range,      # 范围表达式
            try_reduce_numerical,  # 数值解析
        ]:
            res = reducer(tokens, original)
            if res is not None:
                final = res
                break
        else:
            final = original

    if head:
        final = head + final

    return final


def chinese_to_num(original):
    """主函数：将中文数字转换为阿拉伯数字"""
    return pattern.sub(replace, original)
