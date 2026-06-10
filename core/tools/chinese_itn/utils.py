# coding: utf-8
"""
底层字符与物理单位剥离等基础辅助工具
"""

import re
from .mappings import unit_mapping, common_units, num_mapper

# 预编译正则（均为模块级常量，不会变化）
_UNIT_PATTERN = re.compile(rf'({common_units})$')
_LETTER_PATTERN = re.compile(r'[a-zA-Z]+$')

def strip_unit(original):
    """把数字后面跟着的单位剥离开，并应用单位映射"""
    match = _UNIT_PATTERN.search(original)

    if match:
        unit_cn = match.group(1)
        stripped = original[:match.start()]
        mapped_unit = unit_mapping.get(unit_cn)
        unit = mapped_unit if mapped_unit is not None else unit_cn
    else:
        stripped = original
        unit = ''

    if not unit and stripped:
        letter_match = _LETTER_PATTERN.search(stripped)
        if letter_match:
            unit = letter_match.group()
            stripped = stripped[:letter_match.start()]

    return stripped.strip(), unit


def convert_pure_num(original, strict=False):
    """把中文数字转为对应的阿拉伯数字"""
    stripped, unit = strip_unit(original)
    if stripped == '一' and not strict:
        return original
    converted = [num_mapper[c] for c in stripped]
    return ''.join(converted) + unit
