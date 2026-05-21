# coding: utf-8
"""
Tokenizer+Parser 架构的中文数字序列解析器 (统一 Lexer 版)
"""

import re
from dataclasses import dataclass

# ============================================================
# Token 定义
# ============================================================

@dataclass
class Token:
    type: str     # 'DIGIT' | 'TEN' | 'HUNDRED' | ...
    value: int    # 对应的数值
    char: str     # 原始字符
    pos: int      # 在源文本中的起始位置


# ============================================================
# 通用词法分析器 (Lexer)
# ============================================================

_TOKEN_RULES = [
    ('PERCENT_PREFIX', r'百分之|千分之'),
    ('FRACTION_SEP',   r'分之'),
    ('RATIO_SEP',      r'比'),
    ('DOT',            r'点'),
    ('YEAR_SUF',       r'年'),
    ('MONTH_SUF',      r'月'),
    ('DAY_SUF',        r'日|号'),
    ('MINUTE_SUF',     r'分(?=[零幺一二三四五六七八九十]|秒|$)'), # 防冲突前瞻
    ('SECOND_SUF',     r'秒'),
    ('ZERO',           r'零'),
    ('DIGIT',          r'[一二两三四五六七八九幺]'),
    ('TEN',            r'十'),
    ('HUNDRED',        r'百'),
    ('THOUSAND',       r'千'),
    ('TEN_THOUSAND',   r'万'),
    ('HUNDRED_MILLION',r'亿'),
    ('WHITESPACE',     r'\s+'),
    ('OTHER',          r'.'),
]

_lex_regex = re.compile('|'.join(f'(?P<{name}>{pattern})' for name, pattern in _TOKEN_RULES))

_CHAR_VALUE_MAP = {
    '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '幺': 1,
    '十': 10, '百': 100, '千': 1000, '万': 10000, '亿': 100000000
}

def tokenize(text):
    """通用词法分析，生成 Token 序列。"""
    tokens = []
    for match in _lex_regex.finditer(text):
        token_type = match.lastgroup
        token_char = match.group(token_type)
        token_pos = match.start()
        
        # 忽略空白 Token
        if token_type == 'WHITESPACE':
            continue
            
        token_value = _CHAR_VALUE_MAP.get(token_char, 0)
        tokens.append(Token(type=token_type, value=token_value, char=token_char, pos=token_pos))
    return tokens


# ============================================================
# 语法分析器 (Parser)
# ============================================================

# 基础数字 Token 集合
_BASIC_NUMERIC_TYPES = {
    'DIGIT', 'TEN', 'HUNDRED', 'THOUSAND', 'TEN_THOUSAND', 'HUNDRED_MILLION', 'ZERO', 'DOT'
}

def _parse_atomic(tokens, i):
    """从位置 i 解析一个原子数值，返回 (值, 消耗_token数) 或 None"""
    n = len(tokens)
    if i >= n:
        return None

    t = tokens[i]

    # === DIGIT 开头 ===
    if t.type == 'DIGIT':
        d = t.value

        # DIGIT + 亿 → d * 10^8
        if i + 1 < n and tokens[i+1].type == 'HUNDRED_MILLION':
            return (d * 100000000, 2)

        # DIGIT + 万 → d * 10000
        if i + 1 < n and tokens[i+1].type == 'TEN_THOUSAND':
            return (d * 10000, 2)

        # DIGIT + 千
        if i + 1 < n and tokens[i+1].type == 'THOUSAND':
            return (d * 1000, 2)

        # DIGIT + 百
        if i + 1 < n and tokens[i+1].type == 'HUNDRED':
            base = d * 100
            consumed = 2
            j = i + 2
            if j < n and tokens[j].type == 'ZERO':
                if j + 1 < n and tokens[j+1].type == 'DIGIT':
                    base += tokens[j+1].value
                    consumed += 2
            elif j < n and tokens[j].type == 'DIGIT':
                tens_d = tokens[j].value
                if j + 1 < n and tokens[j+1].type == 'TEN':
                    base += tens_d * 10
                    consumed += 2
                    j += 2
                    if j < n and tokens[j].type == 'DIGIT':
                        base += tokens[j].value
                        consumed += 1
                else:
                    base += tens_d * 10
                    consumed += 1
            return (base, consumed)

        # DIGIT + TEN + DIGIT → d*10 + d2
        if (i + 2 < n
            and tokens[i+1].type == 'TEN'
            and tokens[i+2].type == 'DIGIT'):
            if i + 3 < n and tokens[i+3].type == 'TEN':
                pass  # 后跟 TEN → 倾向拆开
            else:
                return (10 * d + tokens[i+2].value, 3)

        # DIGIT + TEN → d*10（前方是 DIGIT run 时不组合）
        if i + 1 < n and tokens[i+1].type == 'TEN':
            if i > 0 and tokens[i-1].type == 'DIGIT':
                pass
            else:
                return (10 * d, 2)

        return (d, 1)

    # === TEN 开头 ===
    if t.type == 'TEN':
        if (i + 2 < n
            and tokens[i+1].type == 'DIGIT'
            and tokens[i+2].type == 'HUNDRED_MILLION'):
            return ((10 + tokens[i+1].value) * 100000000, 3)
        if i + 1 < n and tokens[i+1].type == 'HUNDRED_MILLION':
            return (10 * 100000000, 2)
        if i + 1 < n and tokens[i+1].type == 'DIGIT':
            return (10 + tokens[i+1].value, 2)
        return (10, 1)

    # === ZERO ===
    if t.type == 'ZERO':
        return (0, 1)

    # 百千万亿 单独
    if t.type in ('HUNDRED', 'THOUSAND', 'TEN_THOUSAND', 'HUNDRED_MILLION'):
        return (t.value, 1)

    return None


def _build_number(tokens, i):
    """从位置 i 尝试解析一个完整数值，返回 (值, 消耗_token数) 或 None。"""
    result = _parse_atomic(tokens, i)
    if result is None:
        return None
    value, consumed = result
    n = len(tokens)
    j = i + consumed

    # 值后跟 万/亿 → 倍增
    if j < n:
        nxt = tokens[j]
        if nxt.type == 'TEN_THOUSAND' and isinstance(value, int) and 0 < value < 10000:
            value *= 10000
            consumed += 1
            j += 1
        elif nxt.type == 'HUNDRED_MILLION' and isinstance(value, int) and 0 < value < 100000000:
            value *= 100000000
            consumed += 1
            j += 1

    # 万/亿/千 后累加低位
    if value >= 10000:
        limit = 10000
    elif value >= 1000:
        limit = 1000
    else:
        limit = None

    if limit:
        while j < n:
            if tokens[j].type == 'ZERO':
                consumed += 1
                j += 1
                continue
            chunk = _parse_atomic(tokens, j)
            if chunk is None:
                break
            chunk_val, chunk_con = chunk
            if chunk_val >= limit:
                break
            value += chunk_val
            consumed += chunk_con
            j += chunk_con

    # 累加后再倍增
    if j < n:
        nxt = tokens[j]
        if nxt.type == 'TEN_THOUSAND' and isinstance(value, int) and 0 < value < 10000:
            value *= 10000
            consumed += 1
        elif nxt.type == 'HUNDRED_MILLION' and isinstance(value, int) and 0 < value < 100000000:
            value *= 100000000
            consumed += 1

    return (value, consumed)


def parse_tokens(tokens):
    """
    规约 Token 序列，解析为阿拉伯数字列表。
    防卫：若序列中包含任何非基本数字 Token，则安全退回并返回 None。
    """
    if not tokens:
        return None
        
    # 执行基本数字 Token 防卫
    if not all(t.type in _BASIC_NUMERIC_TYPES for t in tokens):
        return None

    numbers = []
    i = 0
    n = len(tokens)

    while i < n:
        result = _build_number(tokens, i)
        if result is None:
            return None
        value, consumed = result

        # 小数点规约
        if i + consumed < n and tokens[i + consumed].type == 'DOT':
            dot_idx = i + consumed
            k = dot_idx + 1
            decimal_digits = []
            while k < n and tokens[k].type in ('DIGIT', 'ZERO'):
                decimal_digits.append(str(tokens[k].value))
                k += 1
            if decimal_digits:
                value = f"{value}.{''.join(decimal_digits)}"
                consumed = k - i
            else:
                value = f"{value}."
                consumed += 1

        numbers.append(value)
        i += consumed

    return numbers


# ============================================================
# 对外接口
# ============================================================

def parse_sequence(text):
    """
    统一编译接口：尝试用大数 Parser 解析文本，成功返回 ' ' 分隔的数字串，失败返回 None。
    自动剥离末尾单位字符（含映射），解析后还原。
    """
    from .utils import strip_unit
    stripped, unit = strip_unit(text)

    # 排除 万/亿 作为物理单位剥离（它们是数值乘数）
    if unit in ('万', '亿'):
        stripped = text
        unit = ''

    if not stripped:
        return None

    tokens = tokenize(stripped)
    if not tokens:
        return None

    # tokenize 不识别的字符作为 OTHER 处理。如果末尾被切分成 OTHER Token，
    # 尝试递归缩减，从末尾剥离 OTHER 以支持不合法的未知单位。
    # 这与以前在 tokenize 返回 None 时从尾部缩短的逻辑对齐。
    if tokens[-1].type == 'OTHER':
        end_idx = len(tokens)
        while end_idx > 0 and tokens[end_idx - 1].type == 'OTHER':
            end_idx -= 1
        
        # 剥离出 OTHER 作为后缀单位
        other_tokens = tokens[end_idx:]
        unit_from_other = "".join(t.char for t in other_tokens)
        tokens = tokens[:end_idx]
        unit = unit_from_other + unit

    if not tokens:
        return None

    # 如果 token 序列末尾是 万/亿，且显示模式判定它们作为物理显示后缀
    if tokens and tokens[-1].type in ('TEN_THOUSAND', 'HUNDRED_MILLION'):
        display_unit = tokens[-1].char
        numbers = parse_tokens(tokens[:-1])
        if numbers is not None:
            result = ' '.join(str(n) for n in numbers) + display_unit
            if unit:
                result += unit
            return result

    numbers = parse_tokens(tokens)
    if numbers is None:
        return None

    result = ' '.join(str(n) for n in numbers)
    if unit:
        result += unit
    return result
